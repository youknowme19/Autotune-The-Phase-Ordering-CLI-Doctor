"""
Unit tests for baseline-normalized fitness, multi-fidelity screening, final confirmation protocol, seed archive, and regression guard.
"""

import os
import tempfile
import pytest

from autotune.llvm.passes import PassSequence
from autotune.search import Individual, FitnessEvaluator, PersistentCacheManager
from autotune.search.seeds import SeedArchiveManager, SeedRecord
from autotune.llvm.compiler import CompilationResult
from autotune.benchmark.models import BenchmarkResult, ExecutionMetrics, BenchmarkEnvironmentMetadata


def dummy_meta():
    return BenchmarkEnvironmentMetadata(
        platform="Darwin",
        architecture="arm64",
        compiler_version="clang",
        measurement_backend="timing",
        cpu_info="Apple",
        sample_count=10,
        noise_ratio=0.0,
    )


def test_baseline_normalized_fitness():
    ind_fast = Individual(sequence=PassSequence(passes=["mem2reg"]))
    ind_slow = Individual(sequence=PassSequence(passes=["inline"]))

    b_res_fast = BenchmarkResult(success=True, metrics=ExecutionMetrics(median_time_ns=50.0, mean_time_ns=50.0, min_time_ns=50.0, max_time_ns=50.0, stddev_time_ns=0.0, noise_ratio=0.0), metadata=dummy_meta())
    b_res_slow = BenchmarkResult(success=True, metrics=ExecutionMetrics(median_time_ns=200.0, mean_time_ns=200.0, min_time_ns=200.0, max_time_ns=200.0, stddev_time_ns=0.0, noise_ratio=0.0), metadata=dummy_meta())

    # Baseline is 100.0 ns
    FitnessEvaluator.evaluate(ind_fast, CompilationResult(success=True), None, b_res_fast, baseline_time_ns=100.0)
    FitnessEvaluator.evaluate(ind_slow, CompilationResult(success=True), None, b_res_slow, baseline_time_ns=100.0)

    assert ind_fast.normalized_speed == 2.0, "Faster candidate must have normalized_speed 2.0"
    assert ind_slow.normalized_speed == 0.5, "Slower candidate must have normalized_speed 0.5"
    assert ind_fast < ind_slow, "Faster candidate must sort before slower candidate"


def test_incorrect_candidate_negative_fitness():
    ind_bad = Individual(sequence=PassSequence(passes=["badpass"]))
    FitnessEvaluator.evaluate(ind_bad, CompilationResult(success=False, error_message="Failed"), None, None, baseline_time_ns=100.0)

    assert not ind_bad.is_valid
    assert ind_bad.fitness == float("-inf")
    assert ind_bad.normalized_speed == 0.0


def test_seed_archive_manager():
    with tempfile.TemporaryDirectory() as tmpdir:
        seed_mgr = SeedArchiveManager(seeds_dir=tmpdir)
        seed_mgr.save_seed(
            pipeline=["mem2reg", "instcombine"],
            source_workload_id="kernel.c",
            compiler_id="clang",
            llvm_version="22.1",
            architecture="arm64",
            target_info="macOS arm64",
            observed_normalized_speed=1.25,
        )

        valid_seeds = seed_mgr.load_valid_seeds(target_architecture="arm64", compiler_id="clang")
        assert len(valid_seeds) == 1
        assert valid_seeds[0] == ["mem2reg", "instcombine"]


def test_atomic_cache_corruption_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        cache_mgr = PersistentCacheManager(cache_dir=tmpdir)
        comp_key = "corrupt_key"

        meta_path = os.path.join(cache_mgr.compilation_dir, f"{comp_key}.json")
        bin_path = os.path.join(cache_mgr.compilation_dir, f"{comp_key}.bin")

        with open(meta_path, "w") as f:
            f.write("{invalid json")
        with open(bin_path, "w") as f:
            f.write("data")

        res = cache_mgr.get_compilation(comp_key)
        assert res is None, "Corrupt cache lookup must return None"
        assert cache_mgr.metrics.cache_corruption_recovered is True, "Corruption recovery flag must be set"
        assert not os.path.exists(meta_path), "Corrupt metadata must be quarantined/removed"


def test_search_dashboard_rendering_none_best_fitness():
    from autotune.search.genetic import SearchProgressStats
    from autotune.ui.terminal import SearchDashboard

    dashboard = SearchDashboard(total_generations=5, source_filename="test.c")
    stats = SearchProgressStats(
        generation=1,
        total_generations=5,
        best_fitness_ns=None,
        baseline_fitness_ns=497679000.0,
        speedup_factor=None,
        valid_candidates_count=0,
    )
    panel = dashboard.render_panel(stats)
    panel_str = str(panel.renderable)
    assert "0.0 ms" not in panel_str
    assert "Current Best:" in panel_str
    assert "N/A" in panel_str


def test_search_dashboard_rendering_no_llm_skipped():
    from autotune.search.genetic import SearchProgressStats
    from autotune.ui.terminal import SearchDashboard

    dashboard = SearchDashboard(total_generations=5, source_filename="test.c", use_llm=False)
    stats = SearchProgressStats(
        generation=1,
        total_generations=5,
        best_fitness_ns=None,
        baseline_fitness_ns=497679000.0,
        speedup_factor=None,
        valid_candidates_count=0,
    )
    panel = dashboard.render_panel(stats)
    panel_str = str(panel.renderable)
    assert "Skipped (--no-llm)" in panel_str
