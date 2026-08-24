"""
Linux performance measurement backend with high-precision timing fallback.
"""

import math
import platform
import statistics
import time
from typing import List, Optional

from autotune.benchmark.models import (
    BenchmarkEnvironmentMetadata,
    BenchmarkResult,
    ExecutionMetrics,
)
from autotune.benchmark.runner import PerformanceRunner
from autotune.doctor.errors import DoctorError, ErrorCode
from autotune.sandbox.executor import SandboxExecutor


class LinuxPerformanceRunner(PerformanceRunner):
    """Performance runner using Linux high-precision timing and perf counters."""

    def __init__(
        self,
        platform_name: str = "Linux",
        architecture: str = "x86_64",
        compiler_version: str = "Clang",
        cpu_info: str = "Generic x86_64",
    ):
        self.platform_name = platform_name
        self.architecture = architecture
        self.compiler_version = compiler_version
        self.cpu_info = cpu_info

    def run_benchmark(
        self,
        binary_path: str,
        workload_path: Optional[str] = None,
        binary_args: Optional[List[str]] = None,
        repetitions: int = 10,
        timeout_seconds: float = 5.0,
        warmup_runs: int = 3,
    ) -> BenchmarkResult:
        if platform.system() != "Linux":
            e01 = DoctorError(
                ErrorCode.E01,
                "LinuxPerformanceRunner invoked on non-Linux platform.",
                "Use MacOSPerformanceRunner or auto-selected backend instead.",
            )
            return BenchmarkResult(
                success=False,
                metadata=BenchmarkEnvironmentMetadata(
                    platform=platform.system(),
                    architecture=platform.machine(),
                    compiler_version=self.compiler_version,
                    measurement_backend="Linux perf (unavailable)",
                    cpu_info=self.cpu_info,
                    sample_count=0,
                    noise_ratio=0.0,
                    is_fallback_measurement=True,
                ),
                error_message=str(e01),
            )

        executor = SandboxExecutor()
        samples_ns: List[int] = []
        last_stdout = ""
        last_stderr = ""

        # Perform 3 warmup runs to stabilize CPU caches
        for _ in range(max(3, warmup_runs)):
            warmup = executor.execute(
                binary_path, workload_path=workload_path, binary_args=binary_args, timeout_seconds=timeout_seconds
            )
            if not warmup.success:
                return BenchmarkResult(
                    success=False,
                    metadata=BenchmarkEnvironmentMetadata(
                        platform=self.platform_name,
                        architecture=self.architecture,
                        compiler_version=self.compiler_version,
                        measurement_backend="Linux timing backend",
                        cpu_info=self.cpu_info,
                        sample_count=0,
                        noise_ratio=0.0,
                        is_fallback_measurement=True,
                    ),
                    stdout=warmup.stdout,
                    stderr=warmup.stderr,
                    exit_code=warmup.exit_code,
                    error_message=f"Warmup execution failed: {warmup.error_message or f'Process exited with return code {warmup.exit_code}'}",
                )

        # Timed measurement runs
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            res = executor.execute(
                binary_path, workload_path=workload_path, binary_args=binary_args, timeout_seconds=timeout_seconds
            )
            end = time.perf_counter_ns()

            if not res.success:
                return BenchmarkResult(
                    success=False,
                    metadata=BenchmarkEnvironmentMetadata(
                        platform=self.platform_name,
                        architecture=self.architecture,
                        compiler_version=self.compiler_version,
                        measurement_backend="Linux timing backend",
                        cpu_info=self.cpu_info,
                        sample_count=len(samples_ns),
                        noise_ratio=0.0,
                        is_fallback_measurement=True,
                    ),
                    stdout=res.stdout,
                    stderr=res.stderr,
                    exit_code=res.exit_code,
                    error_message=f"Benchmark execution failed: {res.error_message or f'Process exited with return code {res.exit_code}'}",
                )

            samples_ns.append(end - start)
            last_stdout = res.stdout
            last_stderr = res.stderr

        median_val = float(statistics.median(samples_ns))
        mean_val = float(statistics.mean(samples_ns))
        min_val = float(min(samples_ns))
        max_val = float(max(samples_ns))
        stddev_val = (
            float(statistics.stdev(samples_ns)) if len(samples_ns) > 1 else 0.0
        )
        noise_ratio = stddev_val / median_val if median_val > 0 else 0.0

        if len(samples_ns) >= 4:
            sorted_s = sorted(samples_ns)
            q25 = float(statistics.quantiles(sorted_s, n=4)[0])
            q75 = float(statistics.quantiles(sorted_s, n=4)[2])
            iqr_val = q75 - q25
            iqr_ratio = iqr_val / median_val if median_val > 0 else 0.0
        else:
            iqr_val = 0.0
            iqr_ratio = 0.0

        # Calculate 95% Confidence Interval
        n_samples = len(samples_ns)
        import math
        ci95_margin = 1.96 * (stddev_val / math.sqrt(n_samples)) if (n_samples > 1 and stddev_val > 0) else 0.0
        ci95_lower = max(0.0, mean_val - ci95_margin)
        ci95_upper = mean_val + ci95_margin

        metrics = ExecutionMetrics(
            samples_ns=samples_ns,
            median_time_ns=median_val,
            mean_time_ns=mean_val,
            min_time_ns=min_val,
            max_time_ns=max_val,
            stddev_time_ns=stddev_val,
            noise_ratio=noise_ratio,
            iqr_time_ns=iqr_val,
            iqr_noise_ratio=iqr_ratio,
            ci95_lower_time_ns=ci95_lower,
            ci95_upper_time_ns=ci95_upper,
            cycles=None,
            instructions=None,
        )

        metadata = BenchmarkEnvironmentMetadata(
            platform=self.platform_name,
            architecture=self.architecture,
            compiler_version=self.compiler_version,
            measurement_backend="Linux timing backend",
            cpu_info=self.cpu_info,
            sample_count=repetitions,
            noise_ratio=noise_ratio,
            is_fallback_measurement=True,
        )

        return BenchmarkResult(
            success=True,
            metrics=metrics,
            metadata=metadata,
            stdout=last_stdout,
            stderr=last_stderr,
            exit_code=0,
        )
