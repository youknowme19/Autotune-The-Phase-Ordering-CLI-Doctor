"""
Unit tests for Phase 5 Intelligent Optimization Engine, Taxonomy, Bandit, and KnowledgeStore.
"""

import pytest
from typer.testing import CliRunner

from autotune.analysis.profile import WorkloadProfile
from autotune.cli import app
from autotune.knowledge.store import KnowledgeStore, KnowledgeRecord
from autotune.llvm.taxonomy import PassFamily, PassTaxonomyRegistry
from autotune.search.bandit import UCB1PassFamilyBandit
from autotune.search.strategy import SearchSpacePolicy, OptimizationStrategy

runner = CliRunner()


def test_pass_taxonomy_registry():
    family_loop = PassTaxonomyRegistry.get_pass_family("licm")
    family_vec = PassTaxonomyRegistry.get_pass_family("loop-vectorize")
    family_ssa = PassTaxonomyRegistry.get_pass_family("mem2reg")

    assert family_loop == PassFamily.LOOP_OPTIMIZATION
    assert family_vec == PassFamily.VECTORIZATION
    assert family_ssa == PassFamily.SSA_SCALAR

    siblings = PassTaxonomyRegistry.get_compatible_siblings("sroa")
    assert "mem2reg" in siblings or "gvn" in siblings


def test_search_space_policy_derivation():
    profile = WorkloadProfile(
        source_hash="test1234",
        source_filename="kernel.c",
        lines_of_code=50,
        architecture="arm64",
        compiler_version="Clang 22.1",
        loop_count=3,
        max_loop_depth=2,
        function_count=1,
        call_count=0,
        int_ops=10,
        float_ops=15,
        bitwise_ops=0,
        array_accesses=8,
        pointer_derefs=2,
        memory_intensity=0.6,
        compute_intensity=0.5,
        has_arrays_or_pointers=True,
        has_math_lib=False,
    )

    strat = SearchSpacePolicy.derive_strategy(profile)

    assert isinstance(strat, OptimizationStrategy)
    assert strat.family_weights[PassFamily.LOOP_OPTIMIZATION.value] > 0
    assert strat.pass_weights["loop-vectorize"] > 0


def test_ucb1_pass_family_bandit():
    bandit = UCB1PassFamilyBandit(exploration_constant=0.5)

    # Initial selection visits unexplored arms first
    first_arm = bandit.select_arm()
    assert first_arm is not None

    # Reward Loop Optimization arm
    bandit.update(PassFamily.LOOP_OPTIMIZATION.value, speedup=1.35)
    bandit.update(PassFamily.LOOP_OPTIMIZATION.value, speedup=1.40)

    stats = bandit.arms[PassFamily.LOOP_OPTIMIZATION.value]
    assert stats.pulls == 2
    assert stats.mean_reward == pytest.approx(0.375, rel=1e-2)


def test_knowledge_store_sqlite_crud(tmp_path):
    db_file = tmp_path / "knowledge.db"
    store = KnowledgeStore(db_path=str(db_file))

    profile1 = WorkloadProfile(
        source_hash="hash1",
        source_filename="mat.c",
        lines_of_code=30,
        architecture="arm64",
        compiler_version="Clang 22.1",
        loop_count=2,
        max_loop_depth=2,
        function_count=1,
        call_count=0,
        int_ops=10,
        float_ops=20,
        bitwise_ops=0,
        array_accesses=6,
        pointer_derefs=2,
        memory_intensity=0.5,
        compute_intensity=0.8,
        has_arrays_or_pointers=True,
        has_math_lib=False,
    )

    store.save_knowledge(profile1, winning_pipeline=["mem2reg", "sroa", "gvn"], speedup_ratio=1.28)

    records = store.list_records()
    assert len(records) == 1
    assert records[0].source_filename == "mat.c"
    assert records[0].speedup_ratio == 1.28
    assert records[0].winning_pipeline == ["mem2reg", "sroa", "gvn"]

    # Test similarity lookup
    similar_pipes = store.find_similar_workloads(profile1, limit=1)
    assert len(similar_pipes) == 1
    assert similar_pipes[0] == ["mem2reg", "sroa", "gvn"]


def test_cli_knowledge_command():
    res = runner.invoke(app, ["knowledge", "list"])
    assert res.exit_code == 0
