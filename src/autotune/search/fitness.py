"""
Fitness evaluation enforcing baseline-normalized speed and strict candidate ordering.
"""

from typing import Optional
from autotune.benchmark.correctness import CorrectnessResult
from autotune.benchmark.models import BenchmarkResult
from autotune.llvm.compiler import CompilationResult
from autotune.search.individual import Individual


class FitnessEvaluator:
    """Evaluates candidates enforcing strict priority: compilation > correctness > baseline-normalized speed."""

    @staticmethod
    def evaluate(
        individual: Individual,
        compilation_res: CompilationResult,
        correctness_res: Optional[CorrectnessResult],
        benchmark_res: Optional[BenchmarkResult],
        baseline_time_ns: Optional[float] = None,
    ) -> Individual:
        if not compilation_res.success:
            individual.compilation_success = False
            individual.fitness = float("-inf")
            individual.normalized_speed = 0.0
            individual.error_message = compilation_res.error_message or "Compilation failed"
            return individual

        individual.compilation_success = True

        if correctness_res and not correctness_res.is_correct:
            individual.correctness_success = False
            individual.fitness = float("-inf")
            individual.normalized_speed = 0.0
            individual.error_message = correctness_res.reason or "Correctness check failed"
            return individual

        individual.correctness_success = True

        if benchmark_res and benchmark_res.success and benchmark_res.metrics:
            cand_time = benchmark_res.metrics.median_time_ns
            individual.raw_time_ns = cand_time

            if baseline_time_ns and baseline_time_ns > 0:
                individual.normalized_speed = round(baseline_time_ns / max(cand_time, 1.0), 4)
                # Parsimony pressure: prefer shorter pass sequences when speedup is tied (Occam's razor)
                pass_count = len(individual.sequence.passes) if individual.sequence else 0
                length_penalty = (pass_count * 1e-5)
                individual.fitness = individual.normalized_speed - length_penalty
            else:
                individual.fitness = cand_time
                individual.normalized_speed = 1.0

            individual.error_message = None
        else:
            individual.fitness = float("-inf")
            individual.normalized_speed = 0.0
            individual.error_message = (
                benchmark_res.error_message if benchmark_res else "Benchmark failed"
            )

        return individual
