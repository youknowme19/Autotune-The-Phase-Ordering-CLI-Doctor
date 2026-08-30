"""
Structured Workload Profiler unifying AST features, hardware target, and optimization recommendations.
"""

import hashlib
import os
from typing import List, Optional
from pydantic import BaseModel, Field

from autotune.analysis.ast import ASTNodeSummary, SourceAnalyzer


class WorkloadProfile(BaseModel):
    """Unified structural and computational profile of a C/C++ workload."""

    source_hash: str
    source_filename: str
    lines_of_code: int
    architecture: str
    compiler_version: str
    loop_count: int
    max_loop_depth: int
    function_count: int
    call_count: int
    int_ops: int
    float_ops: int
    bitwise_ops: int
    array_accesses: int
    pointer_derefs: int
    memory_intensity: float
    compute_intensity: float
    has_arrays_or_pointers: bool
    has_math_lib: bool
    recommended_passes: List[str] = Field(default_factory=list)


class WorkloadProfiler:
    """Produces structured WorkloadProfile for workload-informed search space construction."""

    def __init__(self, clang_path: Optional[str] = None):
        self.analyzer = SourceAnalyzer(clang_path=clang_path)

    @classmethod
    def extract_profile(cls, source_path: str) -> WorkloadProfile:
        profiler = cls()
        return profiler.profile_file(source_path)

    def profile_file(
        self,
        source_path: str,
        architecture: str = "arm64",
        compiler_version: str = "Clang",
    ) -> WorkloadProfile:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()

        src_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]
        summary: ASTNodeSummary = self.analyzer.analyze_source_file(source_path)

        rec_passes: List[str] = ["mem2reg", "sroa"]

        if summary.loop_count > 0:
            rec_passes.extend(["loop-rotate", "licm", "loop-unroll"])
            if summary.has_arrays_or_pointers or summary.array_accesses > 0:
                rec_passes.extend(["loop-vectorize", "slp-vectorize"])

        if summary.float_ops > 0:
            rec_passes.extend(["reassociate", "instcombine"])

        if summary.estimated_memory_intensity > 0.5:
            rec_passes.extend(["gvn", "early-cse", "memcpyopt"])

        if summary.function_count > 1 or summary.call_count > 0:
            rec_passes.extend(["inline", "simplifycfg"])

        # Deduplicate recommendations preserving order
        unique_recs: List[str] = []
        for p in rec_passes:
            if p not in unique_recs:
                unique_recs.append(p)

        return WorkloadProfile(
            source_hash=src_hash,
            source_filename=os.path.basename(source_path),
            lines_of_code=summary.lines_of_code,
            architecture=architecture,
            compiler_version=compiler_version,
            loop_count=summary.loop_count,
            max_loop_depth=summary.nested_loop_max_depth,
            function_count=summary.function_count,
            call_count=summary.call_count,
            int_ops=summary.int_ops,
            float_ops=summary.float_ops,
            bitwise_ops=summary.bitwise_ops,
            array_accesses=summary.array_accesses,
            pointer_derefs=summary.pointer_derefs,
            memory_intensity=summary.estimated_memory_intensity,
            compute_intensity=summary.estimated_compute_intensity,
            has_arrays_or_pointers=summary.has_arrays_or_pointers,
            has_math_lib=summary.has_math_lib,
            recommended_passes=unique_recs,
        )
