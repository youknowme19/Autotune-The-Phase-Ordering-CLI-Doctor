"""
Unit tests for Phase 6 / Phase 18: PersistentCacheManager Cache Key Completeness & Non-Collision.
Verifies that cache keys include compilation, workload, repetitions, and backend parameters to prevent collision between screening and confirmation runs.
"""

import pytest
from autotune.search.persistent_cache import PersistentCacheManager


def test_performance_cache_key_repetition_isolation():
    cache_mgr = PersistentCacheManager(enabled=False)

    comp_key = cache_mgr.compute_compilation_key(
        source_content="int main() { return 0; }",
        canonical_pipeline="function(mem2reg)",
        compiler_path="/usr/bin/clang",
        compiler_version="clang 18.0",
        opt_version="opt 18.0",
        target_arch="x86_64",
        os_name="Linux",
    )

    # 3 repetitions (screening)
    key_screen = cache_mgr.compute_performance_key(
        compilation_key=comp_key,
        workload_content="sample input",
        measurement_backend="inprocess_monotonic",
        warmup_runs=5,
        repetitions=3,
    )

    # 20 repetitions (confirmation)
    key_confirm = cache_mgr.compute_performance_key(
        compilation_key=comp_key,
        workload_content="sample input",
        measurement_backend="inprocess_monotonic",
        warmup_runs=5,
        repetitions=20,
    )

    # Screening key and confirmation key MUST be distinct
    assert key_screen != key_confirm


def test_compilation_cache_key_parameter_completeness():
    cache_mgr = PersistentCacheManager(enabled=False)

    key_base = cache_mgr.compute_compilation_key(
        source_content="int main() { return 0; }",
        canonical_pipeline="function(gvn)",
        compiler_path="/usr/bin/clang",
        compiler_version="clang 18.0",
        opt_version="opt 18.0",
        target_arch="x86_64",
        os_name="Linux",
    )

    key_different_flags = cache_mgr.compute_compilation_key(
        source_content="int main() { return 0; }",
        canonical_pipeline="function(gvn)",
        compiler_path="/usr/bin/clang",
        compiler_version="clang 18.0",
        opt_version="opt 18.0",
        target_arch="x86_64",
        os_name="Linux",
        compilation_flags=["-march=native"],
    )

    assert key_base != key_different_flags
