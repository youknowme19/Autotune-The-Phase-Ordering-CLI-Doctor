"""
Fitness evaluation and strict candidate ordering.
"""

from typing import Optional
from autotune.benchmark.correctness import CorrectnessResult
from autotune.benchmark.models import BenchmarkResult
from autotune.llvm.compiler import CompilationResult
from autotune.search.individual import Individual


class FitnessEvaluator:
    """Evaluates candidates enforcing strict priority: compilation > correctness > performance."""

    @staticmethod
    def evaluate(
        individual: Individual,
        compilation_res: CompilationResult,
        correctness_res: Optional[CorrectnessResult],
        benchmark_res: Optional[BenchmarkResult],
    ) -> Individual:
        if not compilation_res.success:
            individual.compilation_success = False
            individual.fitness = float("inf")
            individual.error_message = compilation_res.error_message or "Compilation failed"
            return individual

        individual.compilation_success = True

        if correctness_res and not correctness_res.is_correct:
            individual.correctness_success = False
            individual.fitness = float("inf")
            individual.error_message = correctness_res.reason or "Correctness check failed"
            return individual

        individual.correctness_success = True

        if benchmark_res and benchmark_res.success and benchmark_res.metrics:
            individual.fitness = benchmark_res.metrics.median_time_ns
            individual.error_message = None
        else:
            individual.fitness = float("inf")
            individual.error_message = (
                benchmark_res.error_message if benchmark_res else "Benchmark failed"
            )

        return individual
