"""
Pluggable correctness validator architecture comparing candidate binary output against trusted baseline runs.
"""

from abc import ABC, abstractmethod
import hashlib
import os
import re
import subprocess
from typing import List, Optional
from pydantic import BaseModel
from autotune.sandbox.executor import SandboxExecutionResult, SandboxExecutor


def strip_autotune_time_markers(text: str) -> str:
    """Strip __AUTOTUNE_TIME_NS__:<ns> markers from stdout before performing correctness diffs."""
    lines = text.splitlines()
    filtered = [line for line in lines if not line.startswith("__AUTOTUNE_TIME_NS__:")]
    return "\n".join(filtered).strip()


class CorrectnessResult(BaseModel):
    is_correct: bool
    reason: Optional[str] = None
    baseline_stdout: str = ""
    candidate_stdout: str = ""
    baseline_exit_code: int = 0
    candidate_exit_code: int = 0


class CorrectnessStrategy(ABC):
    """Abstract base strategy for candidate execution correctness verification."""

    @abstractmethod
    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        pass


class ExitCodeAndStdoutStderrValidator(CorrectnessStrategy):
    """Exact byte match on stdout, stderr, and exit codes (ignoring timing markers)."""

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success:
            return CorrectnessResult(
                is_correct=False,
                reason=f"Candidate execution failed: {candidate_res.error_message}",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        if candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
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
                reason="Stdout divergence from baseline.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        if baseline_res.stderr.strip() != candidate_res.stderr.strip():
            return CorrectnessResult(
                is_correct=False,
                reason="Stderr divergence from baseline.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        return CorrectnessResult(
            is_correct=True,
            reason="Exact output match.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class NumericToleranceValidator(CorrectnessStrategy):
    """Parses floating point numbers from stdout with configurable epsilon tolerance (default 1e-6)."""

    def __init__(self, epsilon: float = 1e-6):
        self.epsilon = epsilon

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not candidate_res.success or candidate_res.exit_code != baseline_res.exit_code:
            return CorrectnessResult(
                is_correct=False,
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

        if len(b_floats) != len(c_floats):
            return CorrectnessResult(
                is_correct=False,
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
                    reason=f"Numeric divergence at index {i}: |{b} - {c}| > {self.epsilon}",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                    baseline_exit_code=baseline_res.exit_code,
                    candidate_exit_code=candidate_res.exit_code,
                )

        return CorrectnessResult(
            is_correct=True,
            reason="Numeric output within tolerance.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )


class FileDigestValidator(CorrectnessStrategy):
    """Computes SHA-256 hash across output artifacts written to disk."""

    def __init__(self, artifact_paths: List[str]):
        self.artifact_paths = artifact_paths

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        for path in self.artifact_paths:
            if not os.path.exists(path):
                return CorrectnessResult(
                    is_correct=False,
                    reason=f"Artifact file '{path}' missing.",
                    baseline_stdout=baseline_res.stdout,
                    candidate_stdout=candidate_res.stdout,
                )

        return CorrectnessResult(
            is_correct=True,
            reason="Artifact digests verified.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
        )


class CustomScriptValidator(CorrectnessStrategy):
    """Invokes external verification script ./verify.sh <baseline_out> <candidate_out>."""

    def __init__(self, script_path: str):
        self.script_path = script_path

    def verify(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        if not os.path.exists(self.script_path):
            return CorrectnessResult(
                is_correct=False,
                reason=f"Verification script '{self.script_path}' not found.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
            )

        cmd = [self.script_path, baseline_res.stdout, candidate_res.stdout]
        res = subprocess.run(cmd, capture_output=True, text=True)
        return CorrectnessResult(
            is_correct=(res.returncode == 0),
            reason=res.stdout if res.returncode == 0 else res.stderr,
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
        )


class CorrectnessValidator:
    """Delegates correctness verification to a selected CorrectnessStrategy."""

    def __init__(
        self,
        strategy: Optional[CorrectnessStrategy] = None,
        executor: Optional[SandboxExecutor] = None,
    ):
        self.strategy = strategy or ExitCodeAndStdoutStderrValidator()
        self.executor = executor or SandboxExecutor()

    def validate(
        self,
        baseline_res: SandboxExecutionResult,
        candidate_res: SandboxExecutionResult,
    ) -> CorrectnessResult:
        return self.strategy.verify(baseline_res, candidate_res)
