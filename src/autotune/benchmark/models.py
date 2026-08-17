"""
Benchmark models and structured measurement metadata.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class BenchmarkEnvironmentMetadata(BaseModel):
    platform: str
    architecture: str
    compiler_version: str
    measurement_backend: str
    cpu_info: str
    sample_count: int
    noise_ratio: float
    is_fallback_measurement: bool = False


class ExecutionMetrics(BaseModel):
    samples_ns: List[int] = Field(default_factory=list)
    median_time_ns: float
    mean_time_ns: float
    min_time_ns: float
    max_time_ns: float
    stddev_time_ns: float
    noise_ratio: float  # stddev / median
    iqr_time_ns: Optional[float] = None  # Interquartile range (q75 - q25)
    iqr_noise_ratio: Optional[float] = None  # iqr / median
    cycles: Optional[int] = None  # Hardware counter cycles (Linux perf, None on macOS)
    instructions: Optional[int] = None


class BenchmarkResult(BaseModel):
    success: bool
    metrics: Optional[ExecutionMetrics] = None
    metadata: BenchmarkEnvironmentMetadata
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error_message: Optional[str] = None
