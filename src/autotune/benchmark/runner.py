"""
Abstract PerformanceRunner base interface.
"""

from abc import ABC, abstractmethod
from typing import Optional
from autotune.benchmark.models import BenchmarkResult


class PerformanceRunner(ABC):
    """Abstract base class for platform performance measurement runners."""

    @abstractmethod
    def run_benchmark(
        self,
        binary_path: str,
        workload_path: Optional[str] = None,
        repetitions: int = 10,
        timeout_seconds: float = 5.0,
    ) -> BenchmarkResult:
        """Run the binary and collect performance metrics and metadata."""
        pass
