"""
Unit tests for Phase 2 Optimization Engine Deep Upgrades.
"""

import time
import pytest
from autotune.benchmark.models import ExecutionMetrics
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence
from autotune.sandbox.executor import SandboxExecutionResult
from autotune.search.genetic import GeneticAlgorithmEngine, SearchProgressStats
from autotune.search.individual import Individual
from autotune.search.persistent_cache import PersistentCacheManager
from autotune.benchmark import get_performance_runner


def test_individual_provenance_tracking():
    seq = PassSequence(passes=["mem2reg", "gvn"])
    ind1 = Individual(sequence=seq, origin="heuristic")
    ind2 = Individual(sequence=seq, origin="llm")
    ind3 = Individual(sequence=seq, origin="crossover")

    assert ind1.origin == "heuristic"
    assert ind2.origin == "llm"
    assert ind3.origin == "crossover"


def test_search_progress_stats_diversity_ratio():
    stats = SearchProgressStats(
        generation=1,
        total_generations=5,
        best_fitness_ns=50.0,
        baseline_fitness_ns=70.0,
        speedup_factor=1.4,
        valid_candidates_count=8,
        unique_candidates_count=8,
        diversity_ratio=0.8,
    )
    assert stats.diversity_ratio == 0.8
    assert stats.unique_candidates_count == 8


def test_execution_metrics_95_confidence_interval():
    runner = get_performance_runner()
    # Mock samples
    samples = [50000000, 52000000, 49000000, 51000000, 50500000]
    import statistics
    med = float(statistics.median(samples))
    mean = float(statistics.mean(samples))
    std = float(statistics.stdev(samples))

    ci_margin = 1.96 * (std / (5 ** 0.5))
    lower = mean - ci_margin
    upper = mean + ci_margin

    metrics = ExecutionMetrics(
        samples_ns=samples,
        median_time_ns=med,
        mean_time_ns=mean,
        min_time_ns=min(samples),
        max_time_ns=max(samples),
        stddev_time_ns=std,
        noise_ratio=std / med,
        ci95_lower_time_ns=lower,
        ci95_upper_time_ns=upper,
    )

    assert metrics.ci95_lower_time_ns is not None
    assert metrics.ci95_upper_time_ns is not None
    assert metrics.ci95_lower_time_ns <= metrics.mean_time_ns <= metrics.ci95_upper_time_ns


def test_genetic_engine_time_budget_termination(tmp_path):
    cache_mgr = PersistentCacheManager(cache_dir=str(tmp_path / "cache"))
    engine = GeneticAlgorithmEngine(
        compiler=CompilerDriver(),
        runner=get_performance_runner(),
        generations=100,
        population_size=10,
        max_search_time_seconds=0.1,  # 100ms time budget
        cache_manager=cache_mgr,
    )

    src_file = tmp_path / "test.c"
    src_file.write_text("int main() { return 0; }")

    b_res = SandboxExecutionResult(success=True, stdout="OK", stderr="", exit_code=0)

    start_t = time.perf_counter()
    pop = engine.evolve(
        source_path=str(src_file),
        workload_path=None,
        baseline_res=b_res,
        baseline_time_ns=100000000.0,
    )
    elapsed = time.perf_counter() - start_t

    # Search should stop early due to 0.1s time budget
    assert pop.generation < 100
    assert elapsed < 5.0  # Stopped within reasonable margin
