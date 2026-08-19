"""
Unit tests for PersistentCacheManager multi-layer content-addressed caching architecture.
"""

import os
import tempfile
import json
import pytest
from autotune.search.persistent_cache import PersistentCacheManager, CACHE_SCHEMA_VERSION


def test_compilation_key_independence_from_runs():
    mgr = PersistentCacheManager()

    # Changing repetitions or benchmark params must NOT alter compilation key
    k1 = mgr.compute_compilation_key("int main(){}", "mem2reg,gvn", "/usr/bin/clang", "22.1", "22.1", "arm64", "Darwin")
    k2 = mgr.compute_compilation_key("int main(){}", "mem2reg,gvn", "/usr/bin/clang", "22.1", "22.1", "arm64", "Darwin")

    assert k1 == k2


def test_performance_key_changes_with_runs():
    mgr = PersistentCacheManager()
    comp_k = mgr.compute_compilation_key("int main(){}", "mem2reg", "/usr/bin/clang", "22.1", "22.1", "arm64", "Darwin")

    p1 = mgr.compute_performance_key(comp_k, "workload1", "macos", warmup_runs=3, repetitions=10)
    p2 = mgr.compute_performance_key(comp_k, "workload1", "macos", warmup_runs=3, repetitions=20)

    # Changing repetitions changes performance key
    assert p1 != p2


def test_persistent_cache_immutable_put_get():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = PersistentCacheManager(cache_dir=tmpdir)

        # Create dummy file to store in compilation cache
        dummy_bin = os.path.join(tmpdir, "dummy.bin")
        with open(dummy_bin, "w") as f:
            f.write("binary_content")

        comp_key = mgr.compute_compilation_key("src", "mem2reg", "clang", "22", "22", "arm64", "Darwin")

        # Put compilation
        cached_path = mgr.put_compilation(comp_key, dummy_bin)
        assert os.path.exists(cached_path)

        # Get compilation
        retrieved_path = mgr.get_compilation(comp_key)
        assert retrieved_path == cached_path
        assert mgr.compilations_avoided == 1


def test_persistent_cache_fresh_benchmark_bypass():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = PersistentCacheManager(cache_dir=tmpdir, fresh_benchmark=True)
        comp_key = "test_comp_key"
        perf_key = mgr.compute_performance_key(comp_key, "workload", "macos", 3, 10)

        # Put performance data
        mgr.put_performance(perf_key, {"median_time_ns": 1000})

        # Fresh benchmark flag forces None retrieval
        retrieved = mgr.get_performance(perf_key)
        assert retrieved is None


def test_cache_corruption_recovery():
    with tempfile.TemporaryDirectory() as tmpdir:
        mgr = PersistentCacheManager(cache_dir=tmpdir)
        comp_key = "corrupt_key"
        meta_path = os.path.join(tmpdir, "compilation", f"{comp_key}.json")
        bin_path = os.path.join(tmpdir, "compilation", f"{comp_key}.bin")

        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w") as f:
            f.write("corrupted json content")
        with open(bin_path, "w") as f:
            f.write("data")

        # Getting corrupt key should handle recovery gracefully
        res = mgr.get_compilation(comp_key)
        assert res is None
        assert mgr.cache_corruption_recovered is True
