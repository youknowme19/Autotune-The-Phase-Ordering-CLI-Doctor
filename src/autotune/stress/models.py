"""
Data models and failure mode categorization for batch offline stress testing.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class FailureCategory(str, Enum):
    COMPILER_CRASH = "COMPILER_CRASH"
    INFINITE_COMPILE_TIME = "INFINITE_COMPILE_TIME"
    SILENT_MISCOMPILATION = "SILENT_MISCOMPILATION"
    RUNTIME_TIMEOUT = "RUNTIME_TIMEOUT"
    STATISTICAL_REGRESSION = "STATISTICAL_REGRESSION"
    SUCCESSFUL_SPEEDUP = "SUCCESSFUL_SPEEDUP"
    PARITY = "PARITY"


class KernelStressResult(BaseModel):
    kernel_name: str
    source_path: str
    workload_path: Optional[str] = None
    category: FailureCategory
    baseline_time_ms: float = 0.0
    best_candidate_time_ms: float = 0.0
    speedup_ratio: float = 1.0
    p_value: float = 1.0
    winning_passes: List[str] = Field(default_factory=list)
    miscompilation_count: int = 0
    crash_count: int = 0
    timeout_count: int = 0
    details: Optional[str] = None


class StressTestReport(BaseModel):
    timestamp: str
    total_workloads: int = 0
    successful_speedups: int = 0
    statistical_regressions: int = 0
    compiler_crashes: int = 0
    infinite_compile_timeouts: int = 0
    silent_miscompilations: int = 0
    runtime_timeouts: int = 0
    parities: int = 0
    overall_suite_speedup: float = 1.0
    results: List[KernelStressResult] = Field(default_factory=list)

    def export_json(self, output_path: str) -> None:
        """Export stress test report to JSON file."""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
