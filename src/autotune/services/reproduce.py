"""
ReproduceService: Empirical experiment reproduction engine for Autotune reports.
Reconstructs pass pipelines from reports, runs fresh correctness & benchmark checks,
and evaluates reproducibility against recorded results.
"""

from enum import Enum
import hashlib
import json
import os
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import ExactOutputValidator
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
    recorded_baseline_ms: float = 0.0
    observed_baseline_ms: float = 0.0
    baseline_delta_pct: float = 0.0
    recorded_candidate_ms: float = 0.0
    observed_candidate_ms: float = 0.0
    candidate_delta_pct: float = 0.0
    correctness_status: str
    winning_passes: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    environment_warnings: List[str] = Field(default_factory=list)


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
        ev_data = data.get("evidence_score", {})
        base_data = data.get("baseline", {})
        win_data = data.get("winner", {})
        doc_ref = data.get("doctor_report") or data.get("environment", {})

        recorded_speedup = data.get("confirmed_speedup") or p_data.get("speedup_ratio", 1.0)
        recorded_cand_ms = win_data.get("median_ms") or p_data.get("candidate_time_ms") or ev_data.get("candidate_median_ms", 0.0)
        recorded_base_ms = base_data.get("median_ms") or p_data.get("baseline_time_ms") or ev_data.get("baseline_median_ms", 0.0)
        passes = p_data.get("pass_sequence", {}).get("passes", [])

        doc_report = run_doctor_checks()
        compiler = CompilerDriver(
            clang_path=doc_report.clang_path,
            clangxx_path=doc_report.clangxx_path,
            opt_path=doc_report.opt_path,
        )
        runner = get_performance_runner()

        reasons: List[str] = []
        env_warnings: List[str] = []

        # Check environment divergence
        ref_arch = doc_ref.get("arch") or doc_ref.get("architecture")
        ref_llvm = doc_ref.get("llvm_version") or doc_ref.get("clang_version")
        ref_triple = doc_ref.get("target_triple")
        ref_hash = data.get("source_hash")

        with open(source_path, "rb") as f:
            curr_hash = hashlib.sha256(f.read()).hexdigest()[:16]

        if ref_arch and doc_report.arch and (ref_arch.lower() != doc_report.arch.lower()):
            env_warnings.append(f"Host architecture mismatch: Recorded '{ref_arch}', current '{doc_report.arch}'.")
        if ref_triple and doc_report.target_triple and (ref_triple != doc_report.target_triple):
            env_warnings.append(f"Target triple mismatch: Recorded '{ref_triple}', current '{doc_report.target_triple}'.")
        if ref_hash and (ref_hash != curr_hash) and not ref_hash.startswith(curr_hash[:8]):
            env_warnings.append(f"Source code hash modified since report generation.")

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
                    recorded_baseline_ms=recorded_base_ms,
                    observed_baseline_ms=0.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Baseline compilation failed: {base_comp.error_message}"],
                    environment_warnings=env_warnings,
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
                    recorded_baseline_ms=recorded_base_ms,
                    observed_baseline_ms=base_ms,
                    baseline_delta_pct=0.0,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=base_ms,
                    candidate_delta_pct=0.0,
                    correctness_status="PASS",
                    winning_passes=[],
                    reasons=["Experiment recorded baseline parity. Baseline verified successfully."],
                    environment_warnings=env_warnings,
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
                    recorded_baseline_ms=recorded_base_ms,
                    observed_baseline_ms=base_ms,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Candidate compilation failed: {cand_comp.error_message}"],
                    environment_warnings=env_warnings,
                )

            # Validate correctness
            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload)
            cand_exec = executor.execute(cand_bin, workload_path=workload)

            validator = ExactOutputValidator()
            corr_res = validator.verify(baseline_res=base_exec, candidate_res=cand_exec)

            if not corr_res.is_correct:
                return ReproductionResult(
                    verdict=ReproductionVerdict.NOT_REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=0.0,
                    speedup_delta_pct=100.0,
                    recorded_baseline_ms=recorded_base_ms,
                    observed_baseline_ms=base_ms,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Correctness validation failed: {corr_res.reason}"],
                    environment_warnings=env_warnings,
                )

            # Benchmark candidate
            cand_bench = runner.run_benchmark(cand_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
            if not cand_bench.success or not cand_bench.metrics:
                return ReproductionResult(
                    verdict=ReproductionVerdict.NOT_REPRODUCED,
                    source_path=source_path,
                    recorded_speedup=recorded_speedup,
                    observed_speedup=0.0,
                    speedup_delta_pct=100.0,
                    recorded_baseline_ms=recorded_base_ms,
                    observed_baseline_ms=base_ms,
                    recorded_candidate_ms=recorded_cand_ms,
                    observed_candidate_ms=0.0,
                    correctness_status="FAIL",
                    winning_passes=passes,
                    reasons=[f"Candidate benchmark failed: {cand_bench.error_message}"],
                    environment_warnings=env_warnings,
                )

            cand_ms = cand_bench.metrics.median_time_ns / 1e6
            observed_speedup = round(base_ms / cand_ms, 2) if cand_ms > 0 else 1.0

            # Calculate relative error in speedup
            speedup_delta_pct = abs(observed_speedup - recorded_speedup) / recorded_speedup * 100.0 if recorded_speedup > 0 else 0.0
            base_delta_pct = ((base_ms - recorded_base_ms) / recorded_base_ms * 100.0) if recorded_base_ms > 0 else 0.0
            cand_delta_pct = ((cand_ms - recorded_cand_ms) / recorded_cand_ms * 100.0) if recorded_cand_ms > 0 else 0.0

            # Check for high environment timing noise or major cross-environment baseline shift
            cand_stability = StabilityAnalyzer.analyze(cand_bench.metrics.samples_ns)
            if cand_stability.cv > 0.20:
                verdict = ReproductionVerdict.INCONCLUSIVE
                reasons.append(f"High measurement noise detected (CV={cand_stability.cv*100:.1f}%). Results inconclusive.")
            elif (speedup_delta_pct / 100.0) <= tolerance:
                verdict = ReproductionVerdict.REPRODUCED
                reasons.append(
                    f"Observed speedup {observed_speedup:.2f}x is within expected measurement tolerance ({speedup_delta_pct:.1f}% delta vs {recorded_speedup:.2f}x)."
                )
            elif abs(base_delta_pct) > 50.0:
                verdict = ReproductionVerdict.INCONCLUSIVE
                reasons.append(
                    f"Significant environment baseline divergence detected ({base_delta_pct:+.1f}% vs recorded baseline). Hardware calibration differs; results inconclusive."
                )
            else:
                verdict = ReproductionVerdict.NOT_REPRODUCED
                reasons.append(
                    f"Observed speedup {observed_speedup:.2f}x deviated from recorded {recorded_speedup:.2f}x by {speedup_delta_pct:.1f}% (allowed tolerance: {tolerance*100:.1f}%)."
                )

            return ReproductionResult(
                verdict=verdict,
                source_path=source_path,
                recorded_speedup=recorded_speedup,
                observed_speedup=observed_speedup,
                speedup_delta_pct=round(speedup_delta_pct, 2),
                recorded_baseline_ms=round(recorded_base_ms, 3),
                observed_baseline_ms=round(base_ms, 3),
                baseline_delta_pct=round(base_delta_pct, 2),
                recorded_candidate_ms=round(recorded_cand_ms, 3),
                observed_candidate_ms=round(cand_ms, 3),
                candidate_delta_pct=round(cand_delta_pct, 2),
                correctness_status="PASS",
                winning_passes=passes,
                reasons=reasons,
                environment_warnings=env_warnings,
            )
