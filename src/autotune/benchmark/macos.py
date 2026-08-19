"""
MacOS high-precision timing performance measurement backend with drift protection.
"""

import math
import statistics
import time
from typing import List, Optional

from autotune.benchmark.models import (
    BenchmarkEnvironmentMetadata,
    BenchmarkResult,
    ExecutionMetrics,
)
from autotune.benchmark.runner import PerformanceRunner
from autotune.sandbox.executor import SandboxExecutor


class MacOSPerformanceRunner(PerformanceRunner):
    """Performance runner backend for macOS using high-precision CPU monotonic timing."""

    def __init__(
        self,
        platform_name: str = "Darwin",
        architecture: str = "arm64",
        compiler_version: str = "Clang",
        cpu_info: str = "Apple Silicon",
    ):
        self.platform_name = platform_name
        self.architecture = architecture
        self.compiler_version = compiler_version
        self.cpu_info = cpu_info

    def run_benchmark(
        self,
        binary_path: str,
        workload_path: Optional[str] = None,
        repetitions: int = 10,
        timeout_seconds: float = 5.0,
        warmup_runs: int = 3,
    ) -> BenchmarkResult:
        executor = SandboxExecutor()
        samples_ns: List[int] = []
        last_stdout = ""
        last_stderr = ""

        # Perform warmup runs to stabilize CPU caches & dynamic frequency scaling
        for _ in range(max(1, warmup_runs)):
            warmup = executor.execute(
                binary_path, workload_path=workload_path, timeout_seconds=timeout_seconds
            )
            if not warmup.success:
                return BenchmarkResult(
                    success=False,
                    metadata=BenchmarkEnvironmentMetadata(
                        platform=self.platform_name,
                        architecture=self.architecture,
                        compiler_version=self.compiler_version,
                        measurement_backend="macOS high-precision timing",
                        cpu_info=self.cpu_info,
                        sample_count=0,
                        warmup_runs=warmup_runs,
                        measured_runs=repetitions,
                        noise_ratio=0.0,
                        is_fallback_measurement=True,
                    ),
                    stdout=warmup.stdout,
                    stderr=warmup.stderr,
                    exit_code=warmup.exit_code,
                    error_message=f"Warmup execution failed: {warmup.error_message}",
                )

        # Timed measurement runs
        for _ in range(repetitions):
            start = time.perf_counter_ns()
            res = executor.execute(
                binary_path, workload_path=workload_path, timeout_seconds=timeout_seconds
            )
            end = time.perf_counter_ns()

            if not res.success:
                return BenchmarkResult(
                    success=False,
                    metadata=BenchmarkEnvironmentMetadata(
                        platform=self.platform_name,
                        architecture=self.architecture,
                        compiler_version=self.compiler_version,
                        measurement_backend="macOS high-precision timing",
                        cpu_info=self.cpu_info,
                        sample_count=len(samples_ns),
                        warmup_runs=warmup_runs,
                        measured_runs=repetitions,
                        noise_ratio=0.0,
                        is_fallback_measurement=True,
                    ),
                    stdout=res.stdout,
                    stderr=res.stderr,
                    exit_code=res.exit_code,
                    error_message=f"Benchmark execution failed: {res.error_message}",
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
        cv = stddev_val / mean_val if mean_val > 0 else 0.0
        timing_warning = cv > 0.15

        # Calculate IQR noise
        if len(samples_ns) >= 4:
            sorted_s = sorted(samples_ns)
            q25 = float(statistics.quantiles(sorted_s, n=4)[0])
            q75 = float(statistics.quantiles(sorted_s, n=4)[2])
            iqr_val = q75 - q25
            iqr_ratio = iqr_val / median_val if median_val > 0 else 0.0
        else:
            iqr_val = 0.0
            iqr_ratio = 0.0

        metrics = ExecutionMetrics(
            samples_ns=samples_ns,
            median_time_ns=median_val,
            mean_time_ns=mean_val,
            min_time_ns=min_val,
            max_time_ns=max_val,
            stddev_time_ns=stddev_val,
            noise_ratio=noise_ratio,
            coefficient_of_variation=cv,
            timing_stability_warning=timing_warning,
            iqr_time_ns=iqr_val,
            iqr_noise_ratio=iqr_ratio,
        )

        metadata = BenchmarkEnvironmentMetadata(
            platform=self.platform_name,
            architecture=self.architecture,
            compiler_version=self.compiler_version,
            measurement_backend="macOS high-precision timing",
            cpu_info=self.cpu_info,
            sample_count=repetitions,
            warmup_runs=warmup_runs,
            measured_runs=repetitions,
            noise_ratio=noise_ratio,
            coefficient_of_variation=cv,
            timing_stability_warning=timing_warning,
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
