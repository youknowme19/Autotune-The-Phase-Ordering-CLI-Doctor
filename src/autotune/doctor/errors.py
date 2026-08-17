"""
Doctor error codes and structured diagnostic error classes.
"""

from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    E01 = "E-01"  # Performance counter unavailable
    E02 = "E-02"  # Candidate timeout
    E03 = "E-03"  # Correctness divergence
    E04 = "E-04"  # LLVM / toolchain mismatch or missing tool
    E05 = "E-05"  # Measurement noise excessive


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
