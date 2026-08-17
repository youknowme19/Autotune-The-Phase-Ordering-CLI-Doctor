"""
Correctness validator comparing candidate binary output against trusted baseline runs.
"""

from typing import Optional
from pydantic import BaseModel
from autotune.sandbox.executor import SandboxExecutionResult, SandboxExecutor


class CorrectnessResult(BaseModel):
    is_correct: bool
    reason: Optional[str] = None
    baseline_stdout: str = ""
    candidate_stdout: str = ""
    baseline_exit_code: int = 0
    candidate_exit_code: int = 0


class CorrectnessValidator:
    """Validates candidate outputs against trusted baseline output."""

    def __init__(self, executor: Optional[SandboxExecutor] = None):
        self.executor = executor or SandboxExecutor()

    def validate(
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
                reason=(
                    f"Exit code divergence: candidate returned {candidate_res.exit_code}, "
                    f"baseline returned {baseline_res.exit_code}"
                ),
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        # Check stdout equality
        baseline_norm = baseline_res.stdout.strip()
        candidate_norm = candidate_res.stdout.strip()

        if baseline_norm != candidate_norm:
            return CorrectnessResult(
                is_correct=False,
                reason="Stdout output divergence from baseline.",
                baseline_stdout=baseline_res.stdout,
                candidate_stdout=candidate_res.stdout,
                baseline_exit_code=baseline_res.exit_code,
                candidate_exit_code=candidate_res.exit_code,
            )

        return CorrectnessResult(
            is_correct=True,
            reason="Output matches baseline.",
            baseline_stdout=baseline_res.stdout,
            candidate_stdout=candidate_res.stdout,
            baseline_exit_code=baseline_res.exit_code,
            candidate_exit_code=candidate_res.exit_code,
        )
