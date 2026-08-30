"""
Doctor error codes and structured diagnostic failure classifications.
Provides standard failure categorizations:
COMPILER_CRASH, COMPILATION_TIMEOUT, RUNTIME_TIMEOUT, SILENT_MISCOMPILATION,
STATISTICAL_REGRESSION, PARITY, SUCCESSFUL_SPEEDUP, INCONCLUSIVE, and TOOL_FAILURE.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel


class ErrorCode(str, Enum):
    E01 = "E-01"  # Performance counter unavailable
    E02 = "E-02"  # Candidate timeout
    E03 = "E-03"  # Correctness divergence
    E04 = "E-04"  # LLVM / toolchain mismatch or missing tool
    E05 = "E-05"  # Measurement noise excessive


class FailureCategory(str, Enum):
    COMPILER_CRASH = "COMPILER_CRASH"
    COMPILATION_TIMEOUT = "COMPILATION_TIMEOUT"
    RUNTIME_TIMEOUT = "RUNTIME_TIMEOUT"
    SILENT_MISCOMPILATION = "SILENT_MISCOMPILATION"
    STATISTICAL_REGRESSION = "STATISTICAL_REGRESSION"
    PARITY = "PARITY"
    SUCCESSFUL_SPEEDUP = "SUCCESSFUL_SPEEDUP"
    INCONCLUSIVE = "INCONCLUSIVE"
    TOOL_FAILURE = "TOOL_FAILURE"


class FailureDiagnostic(BaseModel):
    category: FailureCategory
    stage: str
    reason: str
    pipeline: Optional[str] = None
    recommendation: str


class DoctorError(Exception):
    """Base diagnostic error for Autotune doctor checks."""

    def __init__(self, code: ErrorCode, message: str, detail: Optional[str] = None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(f"[{code.value}] {message}")

    def format_warning(self) -> str:
        res = f"[WARN] {self.code.value}\n{self.message}"
        if self.detail:
            res += f"\n\n{self.detail}"
        return res
