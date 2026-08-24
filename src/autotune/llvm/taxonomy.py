"""
LLVM Pass Taxonomy and Domain Metadata.
Classifies optimization passes into families, risk profiles, prerequisites, and workload signals.
"""

from enum import Enum
from typing import Dict, List, Set, NamedTuple, Optional


class PassFamily(str, Enum):
    SSA_SCALAR = "SSA / Scalar"
    LOOP_OPTIMIZATION = "Loop Optimization"
    VECTORIZATION = "Vectorization & SIMD"
    INTERPROCEDURAL = "Interprocedural (IPO)"
    CFG_CLEANUP = "CFG & Control Flow"
    MEMORY = "Memory Optimization"


class PassMetadata(NamedTuple):
    pass_name: str
    family: PassFamily
    prerequisites: List[str]
    compatible_passes: List[str]
    workload_signals: List[str]
    risk_level: str  # low, medium, high
    relative_compile_cost: float  # 1.0 = baseline


PASS_TAXONOMY: Dict[str, PassMetadata] = {
    "mem2reg": PassMetadata(
        pass_name="mem2reg",
        family=PassFamily.SSA_SCALAR,
        prerequisites=[],
        compatible_passes=["sroa", "gvn", "instcombine", "licm"],
        workload_signals=["pointer_derefs", "lines_of_code"],
        risk_level="low",
        relative_compile_cost=1.0,
    ),
    "sroa": PassMetadata(
        pass_name="sroa",
        family=PassFamily.SSA_SCALAR,
        prerequisites=["mem2reg"],
        compatible_passes=["mem2reg", "gvn", "early-cse", "instcombine"],
        workload_signals=["array_accesses", "pointer_derefs"],
        risk_level="low",
        relative_compile_cost=1.2,
    ),
    "gvn": PassMetadata(
        pass_name="gvn",
        family=PassFamily.SSA_SCALAR,
        prerequisites=["mem2reg", "sroa"],
        compatible_passes=["early-cse", "memcpyopt", "licm"],
        workload_signals=["memory_intensity", "compute_intensity"],
        risk_level="low",
        relative_compile_cost=1.5,
    ),
    "early-cse": PassMetadata(
        pass_name="early-cse",
        family=PassFamily.SSA_SCALAR,
        prerequisites=["mem2reg"],
        compatible_passes=["gvn", "sroa"],
        workload_signals=["compute_intensity"],
        risk_level="low",
        relative_compile_cost=1.0,
    ),
    "licm": PassMetadata(
        pass_name="licm",
        family=PassFamily.LOOP_OPTIMIZATION,
        prerequisites=["loop-rotate"],
        compatible_passes=["loop-unroll", "loop-vectorize", "indvars"],
        workload_signals=["loop_count", "max_loop_depth"],
        risk_level="low",
        relative_compile_cost=1.3,
    ),
    "loop-rotate": PassMetadata(
        pass_name="loop-rotate",
        family=PassFamily.LOOP_OPTIMIZATION,
        prerequisites=[],
        compatible_passes=["licm", "loop-unroll", "loop-vectorize"],
        workload_signals=["loop_count", "max_loop_depth"],
        risk_level="low",
        relative_compile_cost=1.1,
    ),
    "loop-unroll": PassMetadata(
        pass_name="loop-unroll",
        family=PassFamily.LOOP_OPTIMIZATION,
        prerequisites=["loop-rotate", "licm"],
        compatible_passes=["instcombine", "reassociate"],
        workload_signals=["loop_count", "int_ops"],
        risk_level="medium",
        relative_compile_cost=1.8,
    ),
    "loop-vectorize": PassMetadata(
        pass_name="loop-vectorize",
        family=PassFamily.VECTORIZATION,
        prerequisites=["loop-rotate", "licm", "indvars"],
        compatible_passes=["slp-vectorize", "instcombine"],
        workload_signals=["loop_count", "float_ops", "array_accesses"],
        risk_level="medium",
        relative_compile_cost=2.2,
    ),
    "slp-vectorize": PassMetadata(
        pass_name="slp-vectorize",
        family=PassFamily.VECTORIZATION,
        prerequisites=["sroa"],
        compatible_passes=["loop-vectorize", "reassociate"],
        workload_signals=["float_ops", "compute_intensity"],
        risk_level="medium",
        relative_compile_cost=1.7,
    ),
    "simplifycfg": PassMetadata(
        pass_name="simplifycfg",
        family=PassFamily.CFG_CLEANUP,
        prerequisites=[],
        compatible_passes=["mem2reg", "jump-threading"],
        workload_signals=["call_count", "lines_of_code"],
        risk_level="low",
        relative_compile_cost=1.0,
    ),
    "instcombine": PassMetadata(
        pass_name="instcombine",
        family=PassFamily.SSA_SCALAR,
        prerequisites=["mem2reg"],
        compatible_passes=["reassociate", "simplifycfg"],
        workload_signals=["int_ops", "float_ops"],
        risk_level="low",
        relative_compile_cost=1.3,
    ),
    "reassociate": PassMetadata(
        pass_name="reassociate",
        family=PassFamily.SSA_SCALAR,
        prerequisites=["instcombine"],
        compatible_passes=["instcombine", "slp-vectorize"],
        workload_signals=["float_ops", "compute_intensity"],
        risk_level="low",
        relative_compile_cost=1.1,
    ),
    "inline": PassMetadata(
        pass_name="inline",
        family=PassFamily.INTERPROCEDURAL,
        prerequisites=[],
        compatible_passes=["mem2reg", "sroa", "gvn"],
        workload_signals=["function_count", "call_count"],
        risk_level="medium",
        relative_compile_cost=2.0,
    ),
    "memcpyopt": PassMetadata(
        pass_name="memcpyopt",
        family=PassFamily.MEMORY,
        prerequisites=["sroa"],
        compatible_passes=["gvn", "dce"],
        workload_signals=["memory_intensity", "array_accesses"],
        risk_level="low",
        relative_compile_cost=1.2,
    ),
}


class PassTaxonomyRegistry:
    """Registry for querying LLVM pass families and metadata."""

    @staticmethod
    def get_pass_family(pass_name: str) -> PassFamily:
        meta = PASS_TAXONOMY.get(pass_name)
        return meta.family if meta else PassFamily.SSA_SCALAR

    @staticmethod
    def get_family_passes(family: PassFamily) -> List[str]:
        return [name for name, meta in PASS_TAXONOMY.items() if meta.family == family]

    @staticmethod
    def get_compatible_siblings(pass_name: str) -> List[str]:
        meta = PASS_TAXONOMY.get(pass_name)
        if meta and meta.compatible_passes:
            return meta.compatible_passes
        return []
