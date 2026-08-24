"""
Workload-Aware Search Space Policy and Adaptive Optimization Strategy.
Controls weighted pass selection, sequence bounds, and population composition derived from WorkloadProfile.
"""

from typing import Dict, List, Tuple
from pydantic import BaseModel, Field

from autotune.analysis.profile import WorkloadProfile
from autotune.llvm.taxonomy import PassFamily, PassTaxonomyRegistry, PASS_TAXONOMY


class PassWeight(BaseModel):
    pass_name: str
    family: PassFamily
    weight: float


class OptimizationStrategy(BaseModel):
    """Dynamic, profile-guided strategy controlling search space and population composition."""

    strategy_name: str
    target_architecture: str
    pass_weights: Dict[str, float] = Field(default_factory=dict)
    family_weights: Dict[str, float] = Field(default_factory=dict)
    min_sequence_length: int = 3
    max_sequence_length: int = 15
    profile_composition_pct: float = 0.25
    baseline_composition_pct: float = 0.25
    family_composition_pct: float = 0.20
    history_composition_pct: float = 0.15
    random_composition_pct: float = 0.15


class SearchSpacePolicy:
    """Derives Workload-Aware Optimization Strategy from WorkloadProfile signals."""

    @staticmethod
    def derive_strategy(profile: WorkloadProfile) -> OptimizationStrategy:
        pass_w: Dict[str, float] = {p: 1.0 for p in PASS_TAXONOMY}
        family_w: Dict[str, float] = {f.value: 1.0 for f in PassFamily}

        # Loop-heavy workload boost
        if profile.loop_count > 0 or profile.max_loop_depth > 1:
            family_w[PassFamily.LOOP_OPTIMIZATION.value] += 2.5
            family_w[PassFamily.VECTORIZATION.value] += 2.0
            for p in ["loop-rotate", "licm", "loop-unroll", "loop-vectorize", "slp-vectorize"]:
                if p in pass_w:
                    pass_w[p] += 2.0

        # Floating-point / SIMD compute boost
        if profile.float_ops > 0 or profile.compute_intensity > 0.5:
            family_w[PassFamily.VECTORIZATION.value] += 2.0
            family_w[PassFamily.SSA_SCALAR.value] += 1.5
            for p in ["slp-vectorize", "reassociate", "instcombine", "gvn"]:
                if p in pass_w:
                    pass_w[p] += 1.5

        # Memory / pointer intensity boost
        if profile.memory_intensity > 0.4 or profile.has_arrays_or_pointers:
            family_w[PassFamily.MEMORY.value] += 2.0
            family_w[PassFamily.SSA_SCALAR.value] += 1.5
            for p in ["mem2reg", "sroa", "gvn", "memcpyopt"]:
                if p in pass_w:
                    pass_w[p] += 1.8

        # Function / call complexity boost
        if profile.function_count > 1 or profile.call_count > 0:
            family_w[PassFamily.INTERPROCEDURAL.value] += 2.0
            family_w[PassFamily.CFG_CLEANUP.value] += 1.5
            for p in ["inline", "simplifycfg"]:
                if p in pass_w:
                    pass_w[p] += 1.8

        # Normalize weights
        total_p = sum(pass_w.values())
        norm_pass_w = {k: round(v / total_p, 4) for k, v in pass_w.items()}

        total_f = sum(family_w.values())
        norm_fam_w = {k: round(v / total_f, 4) for k, v in family_w.items()}

        strat_name = f"ProfileGuided_{profile.architecture}_{profile.source_hash[:8]}"

        return OptimizationStrategy(
            strategy_name=strat_name,
            target_architecture=profile.architecture,
            pass_weights=norm_pass_w,
            family_weights=norm_fam_w,
            min_sequence_length=3,
            max_sequence_length=16,
        )
