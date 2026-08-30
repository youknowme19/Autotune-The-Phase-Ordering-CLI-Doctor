"""
GuardService: CI/CD Performance Regression Protection Guard with Environment Awareness.
Validates current source code performance against recorded reference reports or baseline.
Enforces deterministic exit codes:
0 = PASS
1 = Performance regression exceeding tolerance threshold
2 = Correctness validation failure
3 = Toolchain / Infrastructure error
"""

from enum import IntEnum
import hashlib
import json
import os
import tempfile
from typing import List, Optional
from pydantic import BaseModel, Field

from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import ExactOutputValidator
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
    environment_warnings: List[str] = Field(default_factory=list)
    environment_mismatch: bool = False
    ref_arch: Optional[str] = None
    cur_arch: Optional[str] = None
    ref_llvm: Optional[str] = None
    cur_llvm: Optional[str] = None


class GuardService:
    """Evaluates performance regressions against recorded baselines in CI pipelines with environment checks."""

    @staticmethod
    def check_guard(
        source: str,
        reference_report: Optional[str] = None,
        threshold: float = 0.05,
        workload: Optional[str] = None,
        runs: int = 15,
        warmup: int = 3,
        strict_env: bool = False,
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
        env_warnings: List[str] = []
        env_mismatch = False
        ref_arch = None
        cur_arch = doc_report.arch
        ref_llvm = None
        cur_llvm = doc_report.llvm_version

        # Compute source hash
        with open(source, "rb") as f:
            curr_src_hash = hashlib.sha256(f.read()).hexdigest()[:16]

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
                
                # Check environment metadata
                ref_doc = ref_data.get("doctor_report") or ref_data.get("environment", {})
                ref_arch = ref_doc.get("arch") or ref_doc.get("architecture")
                ref_llvm = ref_doc.get("llvm_version") or ref_doc.get("clang_version")
                ref_triple = ref_doc.get("target_triple")
                ref_src_hash = ref_data.get("source_hash")

                if ref_arch and cur_arch and (ref_arch.lower() != cur_arch.lower()):
                    env_warnings.append(
                        f"Architecture mismatch: Reference recorded on '{ref_arch}', current host is '{cur_arch}'."
                    )
                    env_mismatch = True

                if ref_triple and doc_report.target_triple and (ref_triple != doc_report.target_triple):
                    env_warnings.append(
                        f"Target triple mismatch: Reference='{ref_triple}', Current='{doc_report.target_triple}'."
                    )
                    env_mismatch = True

                if ref_llvm and cur_llvm and (ref_llvm != cur_llvm):
                    env_warnings.append(
                        f"LLVM toolchain mismatch: Reference='{ref_llvm}', Current='{cur_llvm}'."
                    )

                if ref_src_hash and (ref_src_hash != curr_src_hash) and not ref_src_hash.startswith(curr_src_hash[:8]):
                    env_warnings.append(
                        f"Source content changed since reference report (Recorded: {ref_src_hash[:8]}, Current: {curr_src_hash[:8]})."
                    )

                if strict_env and env_mismatch:
                    return GuardResult(
                        exit_code=GuardExitCode.INFRASTRUCTURE_ERROR,
                        status="ENVIRONMENT_MISMATCH",
                        source_path=source,
                        reference_ms=0.0,
                        current_ms=0.0,
                        regression_pct=0.0,
                        threshold_pct=threshold * 100.0,
                        correctness_status="ERROR",
                        message="Strict environment check failed: " + "; ".join(env_warnings),
                        environment_warnings=env_warnings,
                        environment_mismatch=True,
                        ref_arch=ref_arch,
                        cur_arch=cur_arch,
                        ref_llvm=ref_llvm,
                        cur_llvm=cur_llvm,
                    )

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
                    environment_warnings=env_warnings,
                    environment_mismatch=env_mismatch,
                    ref_arch=ref_arch,
                    cur_arch=cur_arch,
                    ref_llvm=ref_llvm,
                    cur_llvm=cur_llvm,
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

            validator = ExactOutputValidator()
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
                    environment_warnings=env_warnings,
                    environment_mismatch=env_mismatch,
                    ref_arch=ref_arch,
                    cur_arch=cur_arch,
                    ref_llvm=ref_llvm,
                    cur_llvm=cur_llvm,
                )

            # Current measurement
            if target_bin != base_bin:
                cand_bench = runner.run_benchmark(target_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
                current_target_ms = (cand_bench.metrics.median_time_ns / 1e6) if cand_bench.metrics else current_base_ms
            else:
                current_target_ms = current_base_ms

            if reference_ms <= 0.0:
                reference_ms = current_base_ms

            # Compute percentage delta
            reg_pct = ((current_target_ms - reference_ms) / reference_ms) * 100.0 if reference_ms > 0 else 0.0
            allowed_max_pct = threshold * 100.0

            if reg_pct > allowed_max_pct:
                return GuardResult(
                    exit_code=GuardExitCode.REGRESSION,
                    status="PERFORMANCE_REGRESSION",
                    source_path=source,
                    reference_ms=reference_ms,
                    current_ms=current_target_ms,
                    regression_pct=round(reg_pct, 2),
                    threshold_pct=round(allowed_max_pct, 2),
                    correctness_status="PASS",
                    message=f"Performance regression detected: latency degraded by {reg_pct:+.1f}% (threshold: {allowed_max_pct:.1f}%).",
                    environment_warnings=env_warnings,
                    environment_mismatch=env_mismatch,
                    ref_arch=ref_arch,
                    cur_arch=cur_arch,
                    ref_llvm=ref_llvm,
                    cur_llvm=cur_llvm,
                )

            return GuardResult(
                exit_code=GuardExitCode.PASS,
                status="PASS",
                source_path=source,
                reference_ms=reference_ms,
                current_ms=current_target_ms,
                regression_pct=round(reg_pct, 2),
                threshold_pct=round(allowed_max_pct, 2),
                correctness_status="PASS",
                message=f"Performance verified within threshold ({reg_pct:+.1f}% vs allowed {allowed_max_pct:.1f}%).",
                environment_warnings=env_warnings,
                environment_mismatch=env_mismatch,
                ref_arch=ref_arch,
                cur_arch=cur_arch,
                ref_llvm=ref_llvm,
                cur_llvm=cur_llvm,
            )
