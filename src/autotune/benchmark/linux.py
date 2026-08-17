"""
Linux performance counters measurement backend interface.
"""

import platform
from typing import Optional

from autotune.benchmark.models import (
    BenchmarkEnvironmentMetadata,
    BenchmarkResult,
)
from autotune.benchmark.runner import PerformanceRunner
from autotune.doctor.errors import DoctorError, ErrorCode


class LinuxPerformanceRunner(PerformanceRunner):
    """Performance runner using Linux perf hardware performance counters."""

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
        repetitions: int = 10,
        timeout_seconds: float = 5.0,
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

        # Linux perf implementation stub ready for perf_event_open integration
        return BenchmarkResult(
            success=False,
            metadata=BenchmarkEnvironmentMetadata(
                platform="Linux",
                architecture=self.architecture,
                compiler_version=self.compiler_version,
                measurement_backend="Linux perf",
                cpu_info=self.cpu_info,
                sample_count=0,
                noise_ratio=0.0,
                is_fallback_measurement=False,
            ),
            error_message="Linux perf_event_open reader not initialized.",
        )
