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


def test_performance_cache_hit_execution_metrics(tmp_path):
    from autotune.search.genetic import GeneticAlgorithmEngine
    from autotune.search.individual import Individual
    from autotune.llvm.passes import PassSequence
    from autotune.llvm.compiler import CompilerDriver
    from autotune.benchmark import get_performance_runner
    from autotune.search.persistent_cache import PersistentCacheManager
    from autotune.sandbox.executor import SandboxExecutionResult

    cache_dir = str(tmp_path / "cache")
    cache_mgr = PersistentCacheManager(cache_dir=cache_dir)
    engine = GeneticAlgorithmEngine(
        compiler=CompilerDriver(),
        runner=get_performance_runner(),
        cache_manager=cache_mgr,
    )
    seq = PassSequence(passes=["mem2reg"])
    ind = Individual(sequence=seq)

    # Pre-populate correctness cache & performance cache
    src_file = tmp_path / "test.c"
    src_file.write_text("int main() { return 0; }")

    comp_key = cache_mgr.compute_compilation_key(
        source_content="int main() { return 0; }",
        canonical_pipeline=ind.canonical_pipeline,
        compiler_path=engine.compiler.clang_path,
        compiler_version=engine.compiler.clang_version or "clang",
        opt_version=engine.compiler.opt_version or "opt",
        target_arch="arm64",
        os_name="Darwin",
    )
    corr_key = cache_mgr.compute_correctness_key(
        compilation_key=comp_key,
        correctness_strategy=engine.correctness_strategy_name,
        workload_content=None,
    )
    perf_key = cache_mgr.compute_performance_key(
        compilation_key=comp_key,
        workload_content=None,
        measurement_backend=getattr(engine.runner, "platform_name", "auto"),
        warmup_runs=2,
        repetitions=engine.screen_runs,
    )

    # Pre-populate compilation, correctness, and performance caches
    cand_bin = tmp_path / "fake_bin"
    cand_bin.write_text("#!/bin/sh\necho OK")
    cand_bin.chmod(0o755)

    dst_bin = cache_mgr.put_compilation(comp_key, str(cand_bin))
    os.chmod(dst_bin, 0o755)
    cache_mgr.put_correctness(corr_key, {"is_correct": True, "reason": "Match"})
    cache_mgr.put_performance(perf_key, {
        "samples_ns": [100.0, 105.0],
        "median_time_ns": 102.5,
    })

    b_res = SandboxExecutionResult(success=True, stdout="OK", stderr="", exit_code=0)

    # Evaluate with performance cache hit
    res = engine.evaluate_individual(
        individual=ind,
        source_path=str(src_file),
        workload_path=None,
        baseline_res=b_res,
        baseline_time_ns=200.0,
        output_dir=str(tmp_path),
    )
    assert res.compilation_success is True
    assert res.correctness_success is True
    assert res.fitness > 0

