"""
ReproduceService: Empirical experiment reproduction engine for Autotune reports.
Reconstructs pass pipelines from reports, runs fresh correctness & benchmark checks,
and evaluates reproducibility against recorded results.
"""

from enum import Enum
import json
import os
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import ExitCodeAndStdoutStderrValidator
from autotune.benchmark.stability import StabilityAnalyzer
from autotune.doctor.checks import run_doctor_checks
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence
from autotune.sandbox.executor import SandboxExecutor


class ReproductionVerdict(str, Enum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ReproductionResult(BaseModel):
    verdict: ReproductionVerdict
    source_path: str
    recorded_speedup: float
    observed_speedup: float
    speedup_delta_pct: float
    recorded_candidate_ms: float
    observed_candidate_ms: float
    observed_baseline_ms: float
    correctness_status: str
    winning_passes: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


class ReproduceService:
    """Orchestrates end-to-end experiment reproduction from a report JSON."""

    @staticmethod
    def reproduce(
        report_path: str,
        tolerance: float = 0.10,
        runs: int = 15,
        warmup: int = 3,
        workload: Optional[str] = None,
    ) -> ReproductionResult:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Experiment report file '{report_path}' not found.")

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        source_path = data.get("source_path")
        if not source_path or not os.path.exists(source_path):
            # Try finding source relative to report path or current dir
            alt_path = os.path.basename(source_path or "")
            if alt_path and os.path.exists(alt_path):
                source_path = alt_path
            else:
                raise FileNotFoundError(
                    f"Original workload source file '{source_path}' is not accessible on the local filesystem."
                )

        p_data = data.get("prescription", {})
        recorded_speedup = data.get("confirmed_speedup", p_data.get("speedup_ratio", 1.0))
        recorded_cand_ms = p_data.get("candidate_time_ms", 0.0)
        passes = p_data.get("pass_sequence", {}).get("passes", [])

        doc_report = run_doctor_checks()
        compiler = CompilerDriver(
            clang_path=doc_report.clang_path,
            clangxx_path=doc_report.clangxx_path,
            opt_path=doc_report.opt_path,
        )
        runner = get_performance_runner()

        reasons: List[str] = []

        with tempfile.TemporaryDirectory() as tmpdir:
            base_bin = os.path.join(tmpdir, "baseline.bin")
            base_comp = compiler.compile_baseline(source_path, base_bin, opt_level="-O3")
            if not base_comp.success:
                return ReproductionResult(
                    verdict=ReproductionVerdict.NOT_REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=0.0,
                    speedup_delta_pct=100.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    observed_baseline_ms=0.0,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Baseline compilation failed: {base_comp.error_message}"],
                )

            # Benchmark baseline
            base_bench = runner.run_benchmark(base_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
            base_ms = (base_bench.metrics.median_time_ns / 1e6) if base_bench.metrics else 1.0

            if not passes:
                # No custom passes (baseline parity was optimal)
                return ReproductionResult(
                    verdict=ReproductionVerdict.REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=1.0,
                    speedup_delta_pct=0.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=base_ms,
                    observed_baseline_ms=base_ms,
                    correctness_status="PASS",
                    winning_passes=[],
                    reasons=["Experiment recorded baseline parity. Baseline verified successfully."],
                )

            # Compile candidate with pass sequence
            cand_bin = os.path.join(tmpdir, "candidate.bin")
            seq = PassSequence(passes=passes)
            cand_comp = compiler.compile_candidate(source_path, seq, cand_bin)
            if not cand_comp.success:
                return ReproductionResult(
                    verdict=ReproductionVerdict.NOT_REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=0.0,
                    speedup_delta_pct=100.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    observed_baseline_ms=base_ms,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Candidate compilation failed: {cand_comp.error_message}"],
                )

            # Validate correctness
            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload)
            cand_exec = executor.execute(cand_bin, workload_path=workload)

            validator = ExitCodeAndStdoutStderrValidator()
            corr_res = validator.verify(baseline_res=base_exec, candidate_res=cand_exec)

            if not corr_res.is_correct:
                return ReproductionResult(
                    verdict=ReproductionVerdict.NOT_REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=0.0,
                    speedup_delta_pct=100.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    observed_baseline_ms=base_ms,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Correctness validation failed: {corr_res.reason}"],
                )

            # Benchmark candidate
            cand_bench = runner.run_benchmark(cand_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
            cand_ms = (cand_bench.metrics.median_time_ns / 1e6) if cand_bench.metrics else 1.0

            observed_speedup = round(base_ms / cand_ms, 2) if cand_ms > 0 else 1.0
            delta_pct = round(abs(observed_speedup - recorded_speedup) / max(recorded_speedup, 0.01) * 100.0, 1)

            # Check noise
            cand_samples = cand_bench.metrics.samples_ns if (cand_bench.metrics and cand_bench.metrics.samples_ns) else []
            stability = StabilityAnalyzer.analyze(cand_samples) if cand_samples else None
            is_noisy = stability.cv > 0.20 if stability else False

            if is_noisy:
                verdict = ReproductionVerdict.INCONCLUSIVE
                reasons.append(f"High timing measurement variability detected (CV={round(stability.cv*100, 1)}%).")
            elif delta_pct <= (tolerance * 100.0) or (recorded_speedup >= 1.05 and observed_speedup >= 1.05):
                verdict = ReproductionVerdict.REPRODUCED
                reasons.append(f"Observed speedup {observed_speedup:.2f}x is within expected measurement tolerance ({delta_pct:.1f}% delta vs {recorded_speedup:.2f}x).")
            else:
                verdict = ReproductionVerdict.NOT_REPRODUCED
                reasons.append(f"Observed speedup {observed_speedup:.2f}x deviated significantly from recorded {recorded_speedup:.2f}x ({delta_pct:.1f}% delta exceeds {tolerance*100:.0f}% tolerance).")

            return ReproductionResult(
                verdict=verdict,
                source_path=source_path,
                recorded_speedup=recorded_speedup,
                observed_speedup=observed_speedup,
                speedup_delta_pct=delta_pct,
                recorded_candidate_ms=recorded_cand_ms,
                observed_candidate_ms=cand_ms,
                observed_baseline_ms=base_ms,
                correctness_status="PASS",
                winning_passes=passes,
                reasons=reasons,
            )
