"""
OptimizeService: Core workload optimization orchestration service.
"""

import json
import os
import tempfile
import time
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.analysis.profile import WorkloadProfiler, WorkloadProfile
from autotune.doctor.checks import run_doctor_checks, DoctorReport
from autotune.llvm.compiler import CompilerDriver
from autotune.benchmark import get_performance_runner
from autotune.benchmark.stability import StabilityAnalyzer
from autotune.sandbox.executor import SandboxExecutor
from autotune.search.genetic import GeneticAlgorithmEngine, SearchProgressStats
from autotune.search.cache import CandidateCache
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceScore, EvidenceGrade
from autotune.reporting.prescription import PrescriptionBuilder, CompilerPrescription
from autotune.reporting.html import HTMLReportGenerator
from autotune.knowledge.store import KnowledgeStore, KnowledgeRecord


class OptimizeResult(BaseModel):
    """Encapsulates the complete structured outcome of an optimization run."""

    run_id: str
    source_path: str
    baseline_opt: str = "-O3"
    speedup_ratio: float
    search_speedup: float = 1.0
    confirmed_speedup: float = 1.0
    classification: str
    evidence_grade: str
    baseline_time_ms: float
    candidate_time_ms: float
    cv_pct: float = 0.0
    p_value: float = 1.0
    cohens_d: float = 0.0
    winning_passes: List[str] = Field(default_factory=list)
    reproducible_command: str = ""
    run_dir: str
    report_json_path: str = ""
    report_html_path: str = ""


OptimizationResult = OptimizeResult


class OptimizeService:
    """Orchestrates end-to-end workload profiling, baseline evaluation, search, and report generation."""

    @staticmethod
    def run(
        source: str,
        workload: Optional[str] = None,
        args: Optional[str] = None,
        baseline_opt: str = "-O3",
        time_budget: int = 30,
        seed: int = 42,
        output_dir: Optional[str] = None,
        quiet: bool = False,
        resume_snapshot: Optional[str] = None,
    ) -> OptimizeResult:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source file '{source}' not found.")

        # Generate unique run_id and run directory
        short_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()[:6]
        run_id = f"run_{time.strftime('%Y%m%d_%H%M%S')}_{short_hash}"
        base_run_dir = output_dir or os.path.join(os.getcwd(), ".autotune", "runs", run_id)
        os.makedirs(base_run_dir, exist_ok=True)

        doc_report = run_doctor_checks()
        compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
        runner = get_performance_runner()

        profiler = WorkloadProfiler(clang_path=doc_report.clang_path)
        w_profile = profiler.profile_file(
            source_path=source,
            architecture=doc_report.arch,
            compiler_version=doc_report.clang_version or "Clang",
        )

        cache_mgr = CandidateCache()

        with tempfile.TemporaryDirectory() as tmpdir:
            base_bin = os.path.join(tmpdir, "baseline.bin")
            compiler.compile_baseline(source, base_bin, opt_level=baseline_opt)

            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload)
            base_bench = runner.run_benchmark(base_bin, workload_path=workload, repetitions=10, warmup_runs=3)
            base_time_ns = base_bench.metrics.median_time_ns if base_bench.metrics else 1.0
            base_samples = base_bench.metrics.samples_ns if (base_bench.metrics and base_bench.metrics.samples_ns) else [int(base_time_ns)]

            engine = GeneticAlgorithmEngine(
                compiler=compiler,
                runner=runner,
                seed=seed,
                population_size=15,
                generations=15,
                max_stagnant_generations=10,
                max_search_time_seconds=float(time_budget),
                cache_manager=cache_mgr,
                resume_exp_id=resume_snapshot,
            )

            pop = engine.evolve(
                source_path=source,
                workload_path=workload,
                baseline_res=base_exec,
                baseline_time_ns=base_time_ns,
            )

            best = pop.best_individual()
            winning_passes = best.sequence.passes if (best and best.is_valid) else []
            cand_time_ns = best.raw_time_ns if (best and best.is_valid and best.raw_time_ns) else base_time_ns
            search_speedup = round(base_time_ns / cand_time_ns, 2) if cand_time_ns > 0 else 1.0

            # Measure candidate samples if valid candidate exists
            if best and best.is_valid and best.raw_time_ns:
                cand_bin = os.path.join(tmpdir, "winning_candidate.bin")
                compiler.compile_candidate(source, best.sequence, cand_bin)
                cand_bench = runner.run_benchmark(cand_bin, workload_path=workload, repetitions=10, warmup_runs=3)
                cand_samples = cand_bench.metrics.samples_ns if (cand_bench.metrics and cand_bench.metrics.samples_ns) else [int(cand_time_ns)]
            else:
                cand_samples = [int(cand_time_ns)]

            # Calculate real scientific EvidenceScore from empirical raw timing samples
            evidence_score = EvidenceEvaluator.evaluate(
                baseline_samples_ns=base_samples,
                candidate_samples_ns=cand_samples,
                correctness_pass=(best.correctness_success if best else True),
                fresh_confirmation=True,
            )

            cand_stability = StabilityAnalyzer.analyze(cand_samples)
            real_cv_pct = round(cand_stability.cv * 100, 1)
            grade = evidence_score.grade.value if hasattr(evidence_score.grade, "value") else str(evidence_score.grade)
            confirmed_speedup = evidence_score.speedup_ratio

            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="optimized_kernel.bin",
                pass_sequence=best.sequence if (best and best.is_valid) else None,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time_ns,
                candidate_time_ns=cand_stability.median_time_ns if (cand_stability and cand_stability.median_time_ns > 0) else cand_time_ns,
                evidence_grade=grade,
            )
            prescription.evidence_grade = grade

            final_cls_str = getattr(prescription.classification, "value", str(prescription.classification))

            report_data: Dict[str, Any] = {
                "run_id": run_id,
                "source_path": source,
                "generations_searched": engine.generations,
                "population_size": 15,
                "search_speedup": search_speedup,
                "confirmed_speedup": confirmed_speedup,
                "prescription": prescription.model_dump(),
                "evidence_score": evidence_score.model_dump(),
                "workload_profile": w_profile.model_dump(),
                "doctor_report": doc_report.model_dump(),
            }

            report_json_path = os.path.join(base_run_dir, "report.json")
            report_html_path = os.path.join(base_run_dir, "report.html")

            with open(report_json_path, "w", encoding="utf-8") as f:
                json.dump(report_data, f, indent=2)

            html_content = HTMLReportGenerator.generate_html(report_data)
            with open(report_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)

            # Persist into KnowledgeStore if Grade A or B
            grade = evidence_score.grade.value if hasattr(evidence_score.grade, "value") else str(evidence_score.grade)
            if grade in ("A", "B") and prescription.classification == "IMPROVED":
                k_store = KnowledgeStore()
                k_store.save_knowledge(
                    profile=w_profile,
                    winning_pipeline=winning_passes,
                    speedup_ratio=prescription.speedup_ratio,
                    classification=prescription.classification,
                    evidence_grade=grade,
                )

            return OptimizeResult(
                run_id=run_id,
                source_path=source,
                baseline_opt=baseline_opt,
                speedup_ratio=prescription.speedup_ratio,
                search_speedup=search_speedup,
                confirmed_speedup=confirmed_speedup,
                classification=final_cls_str,
                evidence_grade=grade,
                baseline_time_ms=prescription.baseline_time_ms,
                candidate_time_ms=prescription.candidate_time_ms,
                cv_pct=real_cv_pct,
                p_value=evidence_score.p_value,
                cohens_d=evidence_score.cohens_d_effect_size,
                winning_passes=winning_passes,
                reproducible_command=prescription.reproducible_clang_command,
                run_dir=base_run_dir,
                report_json_path=report_json_path,
                report_html_path=report_html_path,
            )
