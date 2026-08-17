"""
Unit tests for CorrectnessValidator and fitness gating rejection.
"""

from autotune.benchmark.correctness import CorrectnessValidator
from autotune.benchmark.models import BenchmarkResult, BenchmarkEnvironmentMetadata, ExecutionMetrics
from autotune.llvm.compiler import CompilationResult
from autotune.llvm.passes import PassSequence
from autotune.sandbox.executor import SandboxExecutionResult
from autotune.search.fitness import FitnessEvaluator
from autotune.search.individual import Individual


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


def test_correctness_failed_execution_rejection():
    validator = CorrectnessValidator()
    base = SandboxExecutionResult(success=True, stdout="Result: 42\n", exit_code=0)
    cand = SandboxExecutionResult(
        success=False, stdout="", exit_code=-1, error_message="Segmentation fault"
    )

    res = validator.validate(base, cand)
    assert not res.is_correct

    ind = Individual(sequence=PassSequence(passes=["mem2reg"]))
    comp_res = CompilationResult(success=True)
    evaluated = FitnessEvaluator.evaluate(ind, comp_res, res, None)

    assert not evaluated.is_valid
    assert evaluated.fitness == float("inf")
    assert evaluated.error_message is not None


def test_correctness_diff_assigned_infinite_fitness():
    validator = CorrectnessValidator()
    base = SandboxExecutionResult(success=True, stdout="Expected Output: 100\n", exit_code=0)
    cand = SandboxExecutionResult(success=True, stdout="Incorrect Output: 555\n", exit_code=0)

    res = validator.validate(base, cand)
    assert not res.is_correct

    ind = Individual(sequence=PassSequence(passes=["mem2reg", "gvn"]))
    comp_res = CompilationResult(success=True)
    evaluated = FitnessEvaluator.evaluate(ind, comp_res, res, None)

    assert evaluated.fitness == float("inf")
    assert not evaluated.correctness_success
    assert not evaluated.is_valid
