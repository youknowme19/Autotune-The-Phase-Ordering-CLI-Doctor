"""
Benchmark module exports.
"""

import platform
from autotune.benchmark.correctness import CorrectnessResult, CorrectnessValidator
from autotune.benchmark.linux import LinuxPerformanceRunner
from autotune.benchmark.macos import MacOSPerformanceRunner
from autotune.benchmark.models import (
    BenchmarkEnvironmentMetadata,
    BenchmarkResult,
    ExecutionMetrics,
)
from autotune.benchmark.runner import PerformanceRunner


def get_performance_runner(
    platform_name: str = platform.system(),
    architecture: str = platform.machine(),
    compiler_version: str = "Clang",
    cpu_info: str = "Host CPU",
) -> PerformanceRunner:
    """Factory creating appropriate performance runner for local host platform."""
    if platform_name == "Darwin":
        return MacOSPerformanceRunner(
            platform_name=platform_name,
            architecture=architecture,
            compiler_version=compiler_version,
            cpu_info=cpu_info,
        )
    elif platform_name == "Linux":
        return LinuxPerformanceRunner(
            platform_name=platform_name,
            architecture=architecture,
            compiler_version=compiler_version,
            cpu_info=cpu_info,
        )
    else:
        return MacOSPerformanceRunner(
            platform_name=platform_name,
            architecture=architecture,
            compiler_version=compiler_version,
            cpu_info=cpu_info,
        )


__all__ = [
    "PerformanceRunner",
    "MacOSPerformanceRunner",
    "LinuxPerformanceRunner",
    "CorrectnessValidator",
    "CorrectnessResult",
    "BenchmarkResult",
    "BenchmarkEnvironmentMetadata",
    "ExecutionMetrics",
    "get_performance_runner",
]
