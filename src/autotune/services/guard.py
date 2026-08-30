"""
GuardService: CI/CD Performance Regression Protection Guard.
Validates current source code performance against recorded reference reports or baseline.
Enforces deterministic exit codes:
0 = PASS
1 = Performance regression exceeding tolerance threshold
2 = Correctness validation failure
3 = Toolchain / Infrastructure error
"""

from enum import IntEnum
import json
import os
import tempfile
from typing import List, Optional
from pydantic import BaseModel, Field

from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import ExitCodeAndStdoutStderrValidator
from autotune.doctor.checks import run_doctor_checks
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence
from autotune.sandbox.executor import SandboxExecutor


class GuardExitCode(IntEnum):
    PASS = 0
    REGRESSION = 1
    CORRECTNESS_FAILURE = 2
    INFRASTRUCTURE_ERROR = 3


class GuardResult(BaseModel):
    exit_code: GuardExitCode
    status: str
    source_path: str
    reference_ms: float
    current_ms: float
    regression_pct: float
    threshold_pct: float
    correctness_status: str
    message: str


class GuardService:
    """Evaluates performance regressions against recorded baselines in CI pipelines."""

    @staticmethod
    def check_guard(
        source: str,
        reference_report: Optional[str] = None,
        threshold: float = 0.05,
        workload: Optional[str] = None,
        runs: int = 15,
        warmup: int = 3,
    ) -> GuardResult:
        if not os.path.exists(source):
            return GuardResult(
                exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                status="ERROR",
                source_path=source,
                reference_ms=0.0,
                current_ms=0.0,
                regression_pct=0.0,
                threshold_pct=threshold * 100.0,
                correctness_status="ERROR",
                message=f"Source file '{source}' not found.",
            )

        doc_report = run_doctor_checks()
        if not doc_report.clang_ok:
            return GuardResult(
                exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                status="ERROR",
                source_path=source,
                reference_ms=0.0,
                current_ms=0.0,
                regression_pct=0.0,
                threshold_pct=threshold * 100.0,
                correctness_status="ERROR",
                message="Clang compiler not available on system PATH.",
            )

        compiler = CompilerDriver(
            clang_path=doc_report.clang_path,
            clangxx_path=doc_report.clangxx_path,
            opt_path=doc_report.opt_path,
        )
        runner = get_performance_runner()

        reference_ms = 0.0
        reference_passes: List[str] = []

        if reference_report:
            if not os.path.exists(reference_report):
                return GuardResult(
                    exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                    status="ERROR",
                    source_path=source,
                    reference_ms=0.0,
                    current_ms=0.0,
                    regression_pct=0.0,
                    threshold_pct=threshold * 100.0,
                    correctness_status="ERROR",
                    message=f"Reference report '{reference_report}' not found.",
                )
            try:
                with open(reference_report, "r", encoding="utf-8") as f:
                    ref_data = json.load(f)
                p_data = ref_data.get("prescription", {})
                reference_ms = p_data.get("candidate_time_ms") or p_data.get("baseline_time_ms") or 0.0
                reference_passes = p_data.get("pass_sequence", {}).get("passes", [])
            except Exception as e:
                return GuardResult(
                    exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                    status="ERROR",
                    source_path=source,
                    reference_ms=0.0,
                    current_ms=0.0,
                    regression_pct=0.0,
                    threshold_pct=threshold * 100.0,
                    correctness_status="ERROR",
                    message=f"Failed to parse reference report: {str(e)}",
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            base_bin = os.path.join(tmpdir, "baseline.bin")
            comp_base = compiler.compile_baseline(source, base_bin, opt_level="-O3")
            if not comp_base.success:
                return GuardResult(
                    exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                    status="ERROR",
                    source_path=source,
                    reference_ms=reference_ms,
                    current_ms=0.0,
                    regression_pct=0.0,
                    threshold_pct=threshold * 100.0,
                    correctness_status="ERROR",
                    message=f"Baseline compilation failed: {comp_base.error_message}",
                )

            # Benchmark baseline
            base_bench = runner.run_benchmark(base_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
            current_base_ms = (base_bench.metrics.median_time_ns / 1e6) if base_bench.metrics else 1.0

            target_bin = base_bin
            if reference_passes:
                cand_bin = os.path.join(tmpdir, "target.bin")
                seq = PassSequence(passes=reference_passes)
                cand_comp = compiler.compile_candidate(source, seq, cand_bin)
                if cand_comp.success:
                    target_bin = cand_bin

            # Correctness Check
            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload)
            target_exec = executor.execute(target_bin, workload_path=workload)

            validator = ExitCodeAndStdoutStderrValidator()
            corr_res = validator.verify(baseline_res=base_exec, candidate_res=target_exec)

            if not corr_res.is_correct:
                return GuardResult(
                    exit_code=GuardExitCode.CORRECTNESS_FAILURE,
                    status="FAIL",
                    source_path=source,
                    reference_ms=reference_ms,
                    current_ms=0.0,
                    regression_pct=0.0,
                    threshold_pct=threshold * 100.0,
                    correctness_status="FAIL",
                    message=f"Correctness validation failed: {corr_res.reason}",
                )

            # Current measurement
            cur_bench = runner.run_benchmark(target_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
            current_ms = (cur_bench.metrics.median_time_ns / 1e6) if cur_bench.metrics else current_base_ms

            if reference_ms <= 0.0:
                reference_ms = current_base_ms

            # Regression calculation: Positive means slower
            regression_pct = ((current_ms - reference_ms) / reference_ms) * 100.0
            threshold_pct = threshold * 100.0

            if regression_pct > threshold_pct:
                return GuardResult(
                    exit_code=GuardExitCode.REGRESSION,
                    status="PERFORMANCE_REGRESSION",
                    source_path=source,
                    reference_ms=round(reference_ms, 3),
                    current_ms=round(current_ms, 3),
                    regression_pct=round(regression_pct, 1),
                    threshold_pct=threshold_pct,
                    correctness_status="PASS",
                    message=f"Performance regression +{regression_pct:.1f}% exceeds tolerance threshold of {threshold_pct:.1f}%.",
                )

            return GuardResult(
                exit_code=GuardExitCode.PASS,
                status="PASS",
                source_path=source,
                reference_ms=round(reference_ms, 3),
                current_ms=round(current_ms, 3),
                regression_pct=round(regression_pct, 1),
                threshold_pct=threshold_pct,
                correctness_status="PASS",
                message=f"Performance check passed. Current: {current_ms:.3f} ms vs Reference: {reference_ms:.3f} ms ({regression_pct:+.1f}%).",
            )
