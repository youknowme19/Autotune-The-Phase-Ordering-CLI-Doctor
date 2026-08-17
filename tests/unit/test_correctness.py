"""
Unit tests for CorrectnessValidator.
"""

from autotune.benchmark.correctness import CorrectnessValidator
from autotune.sandbox.executor import SandboxExecutionResult


def test_correctness_matching():
    validator = CorrectnessValidator()
    base = SandboxExecutionResult(success=True, stdout="Result: 42\n", exit_code=0)
    cand = SandboxExecutionResult(success=True, stdout="Result: 42\n", exit_code=0)

    res = validator.validate(base, cand)
    assert res.is_correct


def test_correctness_divergence():
    validator = CorrectnessValidator()
    base = SandboxExecutionResult(success=True, stdout="Result: 42\n", exit_code=0)
    cand = SandboxExecutionResult(success=True, stdout="Result: 999\n", exit_code=0)

    res = validator.validate(base, cand)
    assert not res.is_correct
    assert "divergence" in res.reason.lower()


def test_correctness_failed_execution():
    validator = CorrectnessValidator()
    base = SandboxExecutionResult(success=True, stdout="Result: 42\n", exit_code=0)
    cand = SandboxExecutionResult(
        success=False, stdout="", exit_code=-1, error_message="Segmentation fault"
    )

    res = validator.validate(base, cand)
    assert not res.is_correct
