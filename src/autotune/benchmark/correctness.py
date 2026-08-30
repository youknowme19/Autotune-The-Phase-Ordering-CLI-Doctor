"""
Pluggable correctness validator architecture comparing candidate binary output against trusted baseline runs.
Supports EXACT_OUTPUT, EXIT_CODE, STDOUT, STDERR, CHECKSUM, NUMERIC_TOLERANCE, CUSTOM_VALIDATOR, and COMPOSITE.
"""

from abc import ABC, abstractmethod
from enum import Enum
import hashlib
import os
import re
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from autotune.sandbox.executor import SandboxExecutionResult, SandboxExecutor


def strip_autotune_time_markers(text: str) -> str:
    """Strip __AUTOTUNE_TIME_NS__:<ns> markers from stdout before performing correctness diffs."""
    lines = text.splitlines()
    filtered = [line for line in lines if not line.startswith("__AUTOTUNE_TIME_NS__:")]
    return "\n".join(filtered).strip()


class ValidationVerdict(str, Enum):
    CORRECT = "CORRECT"
    INCORRECT = "INCORRECT"
    INCONCLUSIVE = "INCONCLUSIVE"


class CorrectnessResult(BaseModel):
    is_correct: bool
    verdict: ValidationVerdict = ValidationVerdict.CORRECT
    strategy_name: str = "ExactOutput"
    reason: Optional[str] = None
    diff_details: Optional[str] = None
    baseline_stdout: str = ""
    candidate_stdout: str = ""
    baseline_stderr: str = ""
    candidate_stderr: str = ""
    baseline_exit_code: int = 0
    candidate_exit_code: int = 0

    @property
    def is_valid(self) -> bool:
        return self.is_correct and self.verdict == ValidationVerdict.CORRECT


class CorrectnessStrategy(ABC):
    """Abstract base strategy for candidate execution correctness verification."""

    @property
    def name(self) -> str:
        """Name of the validation strategy."""
        return self.__class__.__name__

    @abstractmethod
    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        pass


class ExitCodeValidator(CorrectnessStrategy):
    """Verifies that candidate exit code matches baseline exit code and was successful."""

    @property
    def name(self) -> str:
        return "ExitCode"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Candidate execution failed: {candidate_res.error_message or 'Non-zero exit'}",
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        if candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Exit code mismatch: candidate={candidate_res.exit_code}, baseline={baseline_res.exit_code}",
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="Exit codes match successfully.",
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class StdoutValidator(CorrectnessStrategy):
    """Verifies that candidate stdout matches baseline stdout (stripping timing markers)."""

    @property
    def name(self) -> str:
        return "Stdout"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Candidate execution failed: {candidate_res.error_message}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        b_stdout_clean = strip_autotune_time_markers(baseline_res.stdout)
        c_stdout_clean = strip_autotune_time_markers(candidate_res.stdout)

        if b_stdout_clean != c_stdout_clean:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Stdout divergence from baseline.",
                diff_details=f"Expected: {b_stdout_clean[:200]}... Got: {c_stdout_clean[:200]}...",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="Stdout matched baseline.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class ExactOutputValidator(CorrectnessStrategy):
    """Exact byte match on stdout, stderr, and exit codes (ignoring timing markers)."""

    @property
    def name(self) -> str:
        return "ExactOutput"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Candidate execution failed: {candidate_res.error_message}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        if candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Exit code divergence: candidate={candidate_res.exit_code}, baseline={baseline_res.exit_code}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        b_stdout_clean = strip_autotune_time_markers(baseline_res.stdout)
        c_stdout_clean = strip_autotune_time_markers(candidate_res.stdout)

        if b_stdout_clean != c_stdout_clean:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Stdout divergence from baseline.",
                diff_details=f"Expected: {b_stdout_clean[:200]}... Got: {c_stdout_clean[:200]}...",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        if baseline_res.stderr.strip() != candidate_res.stderr.strip():
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Stderr divergence from baseline.",
                diff_details=f"Expected: {baseline_res.stderr.strip()[:200]}... Got: {candidate_res.stderr.strip()[:200]}...",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="Exact output match.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_stderr=baseline_res.stderr,
            candidate_stderr=candidate_res.stderr,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


# Backward compatibility alias
ExitCodeAndStdoutStderrValidator = ExactOutputValidator


class ChecksumValidator(CorrectnessStrategy):
    """
    Extracts and compares structured checksums or entire output checksums.
    Recognizes patterns such as:
    - PolyBench checksum markers: 'begin dump: ... end dump' or 'checksum: <val>'
    - Full-output SHA-256 digests
    """

    @property
    def name(self) -> str:
        return "Checksum"

    @staticmethod
    def extract_checksum(text: str) -> Optional[str]:
        # Look for explicit checksum / hash patterns
        patterns = [
            r"checksum\s*:\s*([0-9a-fA-FxX]+|\d+\.?\d*)",
            r"CRC32\s*:\s*([0-9a-fA-FxX]+)",
            r"SHA256\s*:\s*([0-9a-fA-Fa-f]{64})",
            r"result\s*hash\s*:\s*([0-9a-fA-FxX]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).strip().lower()
        return None

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success or candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Execution or exit code failure in checksum comparison.",
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        b_clean = strip_autotune_time_markers(baseline_res.stdout)
        c_clean = strip_autotune_time_markers(candidate_res.stdout)

        b_sum = self.extract_checksum(b_clean)
        c_sum = self.extract_checksum(c_clean)

        if b_sum is not None and c_sum is not None:
            if b_sum != c_sum:
                return CorrectnessResult(
                    is_correct=False,
                    verdict=ValidationVerdict.INCORRECT,
                    strategy_name=self.name,
                    reason=f"Checksum mismatch: baseline={b_sum}, candidate={c_sum}",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                )
            return CorrectnessResult(
                is_correct=True,
                verdict=ValidationVerdict.CORRECT,
                strategy_name=self.name,
                reason=f"Checksum verified: {b_sum}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        # Fallback: compute SHA-256 of entire cleaned output
        b_hash = hashlib.sha256(b_clean.encode("utf-8")).hexdigest()
        c_hash = hashlib.sha256(c_clean.encode("utf-8")).hexdigest()

        if b_hash != c_hash:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Output SHA-256 digest mismatch.",
                diff_details=f"Baseline SHA256: {b_hash[:16]}... Candidate SHA256: {c_hash[:16]}...",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="Output SHA-256 digest match.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
        )


class NumericToleranceValidator(CorrectnessStrategy):
    """Parses floating point numbers from stdout with configurable epsilon tolerance (default 1e-6)."""

    def __init__(self, epsilon: float = 1e-6):
        self.epsilon = epsilon

    @property
    def name(self) -> str:
        return "NumericTolerance"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success or candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason="Execution or exit code failure in numeric comparison.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        b_clean = strip_autotune_time_markers(baseline_res.stdout)
        c_clean = strip_autotune_time_markers(candidate_res.stdout)

        b_floats = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", b_clean)]
        c_floats = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", c_clean)]

        if not b_floats and not c_floats:
            # No numbers found in output; if string is identical, pass; otherwise inconclusive
            if b_clean == c_clean:
                return CorrectnessResult(
                    is_correct=True,
                    verdict=ValidationVerdict.CORRECT,
                    strategy_name=self.name,
                    reason="Outputs match verbatim (no numeric values found).",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                )
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCONCLUSIVE,
                strategy_name=self.name,
                reason="No numeric tokens found in output for tolerance comparison.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        if len(b_floats) != len(c_floats):
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCORRECT,
                strategy_name=self.name,
                reason=f"Numeric token count mismatch: baseline {len(b_floats)} vs candidate {len(c_floats)}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        for i, (b, c) in enumerate(zip(b_floats, c_floats)):
            if abs(b - c) > self.epsilon:
                return CorrectnessResult(
                    is_correct=False,
                    verdict=ValidationVerdict.INCORRECT,
                    strategy_name=self.name,
                    reason=f"Numeric divergence at index {i}: |{b} - {c}| > {self.epsilon}",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                    baseline_exit_code=baseline_res.exit_code,
                    candidate_exit_code=candidate_res.exit_code,
                )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason=f"All {len(b_floats)} numeric values match within epsilon={self.epsilon}.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class FileDigestValidator(CorrectnessStrategy):
    """Computes SHA-256 hash across output artifacts written to disk."""

    def __init__(self, artifact_paths: List[str]):
        self.artifact_paths = artifact_paths

    @property
    def name(self) -> str:
        return "FileDigest"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        for path in self.artifact_paths:
            if not os.path.exists(path):
                return CorrectnessResult(
                    is_correct=False,
                    verdict=ValidationVerdict.INCORRECT,
                    strategy_name=self.name,
                    reason=f"Artifact file '{path}' missing.",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                )

        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="Artifact digests verified.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
        )


class CustomScriptValidator(CorrectnessStrategy):
    """Invokes external verification script ./verify.sh <baseline_out> <candidate_out>."""

    def __init__(self, script_path: str):
        self.script_path = script_path

    @property
    def name(self) -> str:
        return "CustomScript"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not os.path.exists(self.script_path):
            return CorrectnessResult(
                is_correct=False,
                verdict=ValidationVerdict.INCONCLUSIVE,
                strategy_name=self.name,
                reason=f"Verification script '{self.script_path}' not found.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        cmd = [self.script_path, baseline_res.stdout, candidate_res.stdout]
        res = subprocess.run(cmd, capture_output=True, text=True)
        is_ok = (res.returncode == 0)
        return CorrectnessResult(
            is_correct=is_ok,
            verdict=ValidationVerdict.CORRECT if is_ok else ValidationVerdict.INCORRECT,
            strategy_name=self.name,
            reason=res.stdout.strip() if is_ok else res.stderr.strip() or f"Script exited with {res.returncode}",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
        )


class CompositeValidator(CorrectnessStrategy):
    """Combines multiple validation strategies in series, short-circuiting on failure."""

    def __init__(self, strategies: List[CorrectnessStrategy]):
        if not strategies:
            raise ValueError("CompositeValidator requires at least one strategy.")
        self.strategies = strategies

    @property
    def name(self) -> str:
        return f"Composite({'+'.join(s.name for s in self.strategies)})"

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        for strat in self.strategies:
            res = strat.verify(baseline_res, candidate_res)
            if not res.is_correct or res.verdict != ValidationVerdict.CORRECT:
                return res
        return CorrectnessResult(
            is_correct=True,
            verdict=ValidationVerdict.CORRECT,
            strategy_name=self.name,
            reason="All composite validation checks passed successfully.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class CorrectnessValidator:
    """Delegates correctness verification to a selected CorrectnessStrategy."""

    def __init__(
        self,
        strategy: Optional[CorrectnessStrategy] = None,
        executor: Optional[SandboxExecutor] = None,
    ):
        self.strategy = strategy or ExactOutputValidator()
        self.executor = executor or SandboxExecutor()

    def validate(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        return self.strategy.verify(baseline_res, candidate_res)

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        """Alias for validate() to ensure dual method compatibility."""
        return self.strategy.verify(baseline_res, candidate_res)
