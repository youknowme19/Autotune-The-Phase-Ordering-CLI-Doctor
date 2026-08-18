"""
Unit tests for CandidateCache hits, misses, and deterministic key hashing.
"""

import pytest
from autotune.llvm.passes import PassSequence
from autotune.search.cache import CandidateCache, CandidateStatus, CachedCandidateResult
from autotune.search.individual import Individual


def test_candidate_cache_key_computation():
    seq1 = PassSequence(passes=["mem2reg", "instcombine"])
    seq2 = PassSequence(passes=["mem2reg", "instcombine"])
    seq3 = PassSequence(passes=["mem2reg", "gvn"])

    k1 = CandidateCache.compute_key("int main(){}", "workload", "clang-21", "opt-22", "arm64", seq1)
    k2 = CandidateCache.compute_key("int main(){}", "workload", "clang-21", "opt-22", "arm64", seq2)
    k3 = CandidateCache.compute_key("int main(){}", "workload", "clang-21", "opt-22", "arm64", seq3)

    assert k1 == k2  # Same pipeline, source, workload produce identical hash
    assert k1 != k3  # Different pass sequence produces different hash


def test_candidate_cache_hit_and_miss():
    cache = CandidateCache()
    seq = PassSequence(passes=["mem2reg", "instcombine"])
    key = CandidateCache.compute_key("int main(){}", None, "clang-21", "opt-22", "arm64", seq)

    assert cache.get(key) is None
    assert cache.misses == 1
    assert cache.hits == 0

    ind = Individual(sequence=seq, fitness=120.5)
    cached_res = CachedCandidateResult(
        candidate_key=key,
        status=CandidateStatus.SUCCESSFUL_BENCHMARK,
        individual=ind,
        duration_ms=12.5,
    )

    cache.put(key, cached_res)
    retrieved = cache.get(key)

    assert retrieved is not None
    assert retrieved.individual.fitness == 120.5
    assert cache.hits == 1
    assert cache.misses == 1
    assert len(cache) == 1
