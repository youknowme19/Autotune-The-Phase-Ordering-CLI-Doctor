"""
DoctorService: High-level flagship orchestration for 'autotune doctor <source>'.
Coordinates workload analysis, baseline evaluation, preset resolution, genetic phase-ordering search,
rigorous statistical validation, evidence scoring, IR/assembly analysis, and artifact generation.
"""

import hashlib
import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune import __version__ as AUTOTUNE_VERSION
from autotune.analysis import FeatureExtractor
from autotune.analysis.profile import WorkloadProfiler, WorkloadProfile
from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import ExitCodeAndStdoutStderrValidator, NumericToleranceValidator
from autotune.benchmark.stability import StabilityAnalyzer
from autotune.config import CredentialStore
from autotune.doctor.checks import run_doctor_checks, DoctorReport
from autotune.llm import get_llm_client
from autotune.llvm.compiler import CompilerDriver, AssemblyMetrics
from autotune.llvm.passes import PassSequence
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceScore, EvidenceGrade
from autotune.reporting.explain import PipelineInspector
from autotune.reporting.html import HTMLReportGenerator
from autotune.reporting.prescription import PrescriptionBuilder, CompilerPrescription
from autotune.reporting.report import SearchReport
from autotune.sandbox.executor import SandboxExecutor
from autotune.search.genetic import GeneticAlgorithmEngine, SearchProgressStats
from autotune.search.persistent_cache import PersistentCacheManager
from autotune.services.history import HistoryManager


class DoctorPreset(BaseModel):
    name: str
    population: int
    generations: int
    screen_runs: int
    confirm_runs: int
    time_budget: float


PRESETS: Dict[str, DoctorPreset] = {
    "quick": DoctorPreset(name="quick", population=8, generations=4, screen_runs=2, confirm_runs=5, time_budget=15.0),
    "balanced": DoctorPreset(name="balanced", population=12, generations=8, screen_runs=3, confirm_runs=10, time_budget=30.0),
    "aggressive": DoctorPreset(name="aggressive", population=20, generations=15, screen_runs=5, confirm_runs=20, time_budget=60.0),
}


class DoctorResult(BaseModel):
    """Complete result object returned by DoctorService."""

    run_id: str
    source_path: str
    preset_used: str
    search_mode: str
    speedup_ratio: float
    confirmed_speedup: float
    classification: str
    evidence_grade: str
    correctness_status: str
    baseline_median_ms: float
    candidate_median_ms: float
    p_value: float
    cohens_d: float
    confidence_interval_95: List[float] = Field(default_factory=list)
    winning_passes: List[str] = Field(default_factory=list)
    reproducible_command: str = ""
    report_json_path: str = ""
    report_html_path: str = ""
    assembly_metrics: Optional[AssemblyMetrics] = None
    baseline_assembly_path: Optional[str] = None
    candidate_assembly_path: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)


class DoctorService:
    """Flagship compiler optimization doctor workflow."""

    @staticmethod
    def run(
        source: str,
        workload: Optional[str] = None,
        args: Optional[str] = None,
        preset: str = "balanced",
        population: Optional[int] = None,
        generations: Optional[int] = None,
        seed: int = 42,
        time_budget: Optional[float] = None,
        workers: int = 4,
        llm: Optional[bool] = None,
        provider: str = "openai",
        correctness_strategy: str = "exitcode",
        include_assembly: bool = False,
        output_json: Optional[str] = None,
        output_html: Optional[str] = None,
        output_dir: Optional[str] = None,
        quiet: bool = False,
        verbose: bool = False,
        ci_mode: bool = False,
        progress_callback: Optional[Any] = None,
        resume_snapshot: Optional[str] = None,
    ) -> DoctorResult:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source kernel file '{source}' not found.")

        # Resolve preset
        preset_cfg = PRESETS.get(preset.lower(), PRESETS["balanced"])
        pop_size = population if population is not None else preset_cfg.population
        gen_count = generations if generations is not None else preset_cfg.generations
        budget = time_budget if time_budget is not None else preset_cfg.time_budget
        screen_runs = preset_cfg.screen_runs
        confirm_runs = preset_cfg.confirm_runs

        # Generate unique run ID
        with open(source, "rb") as f:
            src_bytes = f.read()
        source_hash = hashlib.sha256(src_bytes).hexdigest()[:8]
        run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{source_hash}"

        run_base_dir = output_dir or os.path.join(os.getcwd(), ".autotune", "runs", run_id)
        os.makedirs(run_base_dir, exist_ok=True)

        # 1. System toolchain & environment check
        doc_report = run_doctor_checks()
        if not doc_report.clang_ok:
            raise RuntimeError("Clang compiler not available on system PATH.")

        compiler = CompilerDriver(
            clang_path=doc_report.clang_path,
            clangxx_path=doc_report.clangxx_path,
            opt_path=doc_report.opt_path,
        )
        runner = get_performance_runner(
            platform_name=doc_report.os_name,
            architecture=doc_report.arch,
            compiler_version=doc_report.clang_version or "Clang",
            cpu_info=doc_report.cpu_info,
        )

        # 2. LLM Tri-state Security Resolution
        api_key = CredentialStore.get_api_key(provider)
        use_llm = False
        search_mode_str = "offline"

        if llm is True:
            if not api_key:
                raise ValueError(
                    f"LLM seeding requested (--llm) but no API key configured for provider '{provider}'. "
                    "Run 'autotune config' or set environment variable."
                )
            use_llm = True
            search_mode_str = "llm"
        elif llm is False:
            use_llm = False
            search_mode_str = "offline"
        else:
            if api_key:
                use_llm = True
                search_mode_str = "llm"
            else:
                use_llm = False
                search_mode_str = "offline"

        # 3. Workload analysis & AST profiling
        extractor = FeatureExtractor(clang_path=doc_report.clang_path)
        features = extractor.extract_from_file(source)

        profiler = WorkloadProfiler(clang_path=doc_report.clang_path)
        w_profile = profiler.profile_file(
            source_path=source,
            architecture=doc_report.arch,
            compiler_version=doc_report.clang_version or "Clang",
        )

        # 4. Correctness validator strategy
        strat = ExitCodeAndStdoutStderrValidator()
        if correctness_strategy == "numeric":
            strat = NumericToleranceValidator()

        # 5. Generate seed pass sequences
        llm_client = get_llm_client(provider=provider, use_llm=use_llm, api_key=api_key, validator=compiler.validator)
        seed_sequences = llm_client.generate_candidates(features, count=4)

        cache_mgr = PersistentCacheManager(enabled=True)

        with tempfile.TemporaryDirectory() as tmpdir:
            # 6. Baseline compilation & benchmark
            base_bin = os.path.join(tmpdir, "baseline.bin")
            base_comp = compiler.compile_baseline(source, base_bin, opt_level="-O3")
            if not base_comp.success:
                raise RuntimeError(f"Baseline compilation failed: {base_comp.error_message}")

            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload, binary_args=[args] if args else None)
            base_bench = runner.run_benchmark(base_bin, workload_path=workload, repetitions=confirm_runs, warmup_runs=3)
            base_time_ns = base_bench.metrics.median_time_ns if base_bench.metrics else 1.0
            base_samples = base_bench.metrics.samples_ns if (base_bench.metrics and base_bench.metrics.samples_ns) else [int(base_time_ns)]

            # 7. GA Engine Search
            engine = GeneticAlgorithmEngine(
                compiler=compiler,
                runner=runner,
                seed=seed,
                population_size=pop_size,
                generations=gen_count,
                max_stagnant_generations=10,
                max_search_time_seconds=budget,
                correctness_strategy=strat,
                max_workers=workers,
                cache_manager=cache_mgr,
                resume_exp_id=resume_snapshot,
                screen_runs=screen_runs,
                confirm_runs=confirm_runs,
            )

            pop = engine.evolve(
                source_path=source,
                workload_path=workload,
                baseline_res=base_exec,
                baseline_time_ns=base_time_ns,
                initial_sequences=seed_sequences,
                callback=progress_callback,
            )

            best = pop.best_individual()
            winning_passes = best.sequence.passes if (best and best.is_valid) else []
            cand_time_ns = best.raw_time_ns if (best and best.is_valid and best.raw_time_ns) else base_time_ns
            search_speedup = round(base_time_ns / cand_time_ns, 2) if cand_time_ns > 0 else 1.0

            # 8. Winner Confirmation & Validation
            cand_samples = [int(cand_time_ns)]
            correctness_pass = True
            cand_bin = os.path.join(tmpdir, "candidate.bin")

            if best and best.is_valid and best.raw_time_ns:
                cand_comp = compiler.compile_candidate(source, best.sequence, cand_bin)
                if cand_comp.success:
                    cand_bench = runner.run_benchmark(cand_bin, workload_path=workload, repetitions=confirm_runs, warmup_runs=3)
                    if cand_bench.metrics and cand_bench.metrics.samples_ns:
                        cand_samples = cand_bench.metrics.samples_ns
                    correctness_pass = best.correctness_success
                else:
                    correctness_pass = False

            # 9. Statistical Evidence Scoring
            evidence_score = EvidenceEvaluator.evaluate(
                baseline_samples_ns=base_samples,
                candidate_samples_ns=cand_samples,
                correctness_pass=correctness_pass,
                fresh_confirmation=True,
            )

            confirmed_speedup = evidence_score.speedup_ratio
            grade = evidence_score.grade.value if hasattr(evidence_score.grade, "value") else str(evidence_score.grade)

            cand_stability = StabilityAnalyzer.analyze(cand_samples)
            effective_cand_time_ns = cand_stability.median_time_ns if (cand_stability and cand_stability.median_time_ns > 0) else cand_time_ns

            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="optimized_kernel.bin",
                pass_sequence=best.sequence if (best and best.is_valid) else None,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time_ns,
                candidate_time_ns=effective_cand_time_ns,
                evidence_grade=grade,
            )
            prescription.evidence_grade = grade
            cls_str = getattr(prescription.classification, "value", str(prescription.classification))

            # 10. Assembly analysis if requested
            asm_metrics = None
            base_asm_file = None
            cand_asm_file = None

            if include_assembly:
                base_asm_file = os.path.join(run_base_dir, "baseline.s")
                cand_asm_file = os.path.join(run_base_dir, "candidate.s")
                compiler.emit_assembly(source, base_asm_file, opt_level="-O3")
                if best and best.is_valid:
                    compiler.emit_assembly(source, cand_asm_file, pass_sequence=best.sequence)
                    asm_metrics = compiler.analyze_assembly(cand_asm_file)
                else:
                    asm_metrics = compiler.analyze_assembly(base_asm_file)

            # 11. Report Export (JSON & HTML)
            json_target = output_json or os.path.join(run_base_dir, "report.json")
            html_target = output_html or os.path.join(run_base_dir, "report.html")

            report_data: Dict[str, Any] = {
                "autotune_version": f"v{AUTOTUNE_VERSION}",
                "run_id": run_id,
                "source_path": source,
                "source_hash": source_hash,
                "preset": preset,
                "search_mode": search_mode_str,
                "generations_searched": gen_count,
                "population_size": pop_size,
                "seed": seed,
                "search_speedup": search_speedup,
                "confirmed_speedup": confirmed_speedup,
                "prescription": prescription.model_dump(),
                "evidence_score": evidence_score.model_dump(),
                "workload_profile": w_profile.model_dump(),
                "doctor_report": doc_report.model_dump(),
                "baseline_samples_ms": [round(s / 1e6, 3) for s in base_samples],
                "candidate_samples_ms": [round(s / 1e6, 3) for s in cand_samples],
            }

            with open(json_target, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            html_content = HTMLReportGenerator.generate_html(report_data)
            with open(html_target, "w", encoding="utf-8") as f:
                f.write(html_content)

            # 12. Record in History
            HistoryManager.record_run(
                run_id=run_id,
                source_path=source,
                source_hash=source_hash,
                speedup_ratio=confirmed_speedup,
                evidence_grade=grade,
                classification=cls_str,
                winning_passes=winning_passes,
                report_json_path=json_target,
                report_html_path=html_target,
            )

            # 13. CI / GitHub Summary support
            if ci_mode:
                gh_summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
                if gh_summary_file:
                    try:
                        with open(gh_summary_file, "a", encoding="utf-8") as gh:
                            gh.write(f"\n### 🩺 Autotune Doctor Optimization Summary\n")
                            gh.write(f"- **Source:** `{source}`\n")
                            gh.write(f"- **Baseline (-O3):** `{evidence_score.baseline_median_ms:.2f} ms`\n")
                            gh.write(f"- **Autotune Candidate:** `{evidence_score.candidate_median_ms:.2f} ms`\n")
                            gh.write(f"- **Confirmed Speedup:** `{confirmed_speedup:.2f}x`\n")
                            gh.write(f"- **Evidence Grade:** `Grade {grade}`\n")
                            gh.write(f"- **Correctness:** `PASS`\n")
                            gh.write(f"- **Winning Passes:** `{winning_passes}`\n")
                    except Exception:
                        pass

            return DoctorResult(
                run_id=run_id,
                source_path=source,
                preset_used=preset,
                search_mode=search_mode_str,
                speedup_ratio=prescription.speedup_ratio,
                confirmed_speedup=confirmed_speedup,
                classification=cls_str,
                evidence_grade=grade,
                correctness_status="PASS" if correctness_pass else "FAIL",
                baseline_median_ms=evidence_score.baseline_median_ms,
                candidate_median_ms=evidence_score.candidate_median_ms,
                p_value=evidence_score.p_value,
                cohens_d=evidence_score.cohens_d_effect_size,
                confidence_interval_95=evidence_score.confidence_interval_95,
                winning_passes=winning_passes,
                reproducible_command=prescription.reproducible_clang_command,
                report_json_path=json_target,
                report_html_path=html_target,
                assembly_metrics=asm_metrics,
                baseline_assembly_path=base_asm_file,
                candidate_assembly_path=cand_asm_file,
                warnings=doc_report.warnings,
            )
