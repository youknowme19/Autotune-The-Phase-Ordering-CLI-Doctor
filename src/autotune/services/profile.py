"""
ProfileService: Workload AST and Structural Code Profiling.
Extracts concise workload features, language, compute vs memory characteristics,
and potential LLVM optimization areas prior to search. 100% offline.
"""

import os
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.analysis.ast import ASTAnalyzer
from autotune.analysis.profile import WorkloadProfiler, WorkloadProfile
from autotune.llvm.compiler import CompilerDriver


class ProfileFeatureSummary(BaseModel):
    source_path: str
    source_filename: str
    language: str
    lines_of_code: int
    function_count: int
    loop_count: int
    max_loop_depth: int
    loop_intensity: str
    memory_intensity: str
    branch_intensity: str
    floating_point_intensity: str
    function_calls_intensity: str
    int_ops: int
    float_ops: int
    array_accesses: int
    pointer_derefs: int
    potential_optimization_areas: List[str] = Field(default_factory=list)
    raw_profile: Dict[str, object] = Field(default_factory=dict)


class ProfileService:
    """Provides human-readable and structured workload profiling before optimization."""

    @staticmethod
    def profile_workload(source_path: str) -> ProfileFeatureSummary:
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file '{source_path}' not found.")

        # Determine language
        ext = os.path.splitext(source_path)[1].lower()
        language = "C++" if ext in (".cpp", ".cc", ".cxx", ".c++", ".c") and ext != ".c" else "C"

        w_prof = WorkloadProfiler.extract_profile(source_path)

        # Loop intensity
        if w_prof.loop_count >= 3 or w_prof.max_loop_depth >= 2:
            loop_int = "HIGH"
        elif w_prof.loop_count >= 1:
            loop_int = "MEDIUM"
        else:
            loop_int = "LOW"

        # Memory intensity
        if w_prof.memory_intensity >= 0.35 or w_prof.pointer_derefs >= 3 or w_prof.array_accesses >= 6:
            mem_int = "HIGH"
        elif w_prof.memory_intensity >= 0.15 or w_prof.array_accesses >= 2:
            mem_int = "MEDIUM"
        else:
            mem_int = "LOW"

        # Branch intensity
        branch_count = getattr(w_prof, "branch_count", 0) or getattr(w_prof, "bitwise_ops", 0)
        if branch_count >= 5 or w_prof.max_loop_depth >= 3:
            branch_int = "HIGH"
        elif branch_count >= 2 or w_prof.loop_count >= 2:
            branch_int = "MEDIUM"
        else:
            branch_int = "LOW"

        # Floating point intensity
        if w_prof.float_ops >= 3:
            fp_int = "HIGH"
        elif w_prof.float_ops >= 1:
            fp_int = "MEDIUM"
        else:
            fp_int = "LOW"

        # Function call intensity
        if w_prof.call_count >= 5:
            call_int = "HIGH"
        elif w_prof.call_count >= 1:
            call_int = "MEDIUM"
        else:
            call_int = "LOW"

        # Potential optimization areas
        opt_areas: List[str] = []
        if w_prof.loop_count > 0:
            opt_areas.append("loop transformations (loop-rotate, loop-unroll, licm)")
        if w_prof.pointer_derefs > 0 or w_prof.array_accesses > 0 or w_prof.memory_intensity > 0.2:
            opt_areas.append("scalar promotion & memory optimization (mem2reg, sroa)")
        if w_prof.int_ops + w_prof.float_ops >= 4:
            opt_areas.append("redundancy elimination (gvn, sccp, early-cse)")
        if w_prof.compute_intensity >= 0.3:
            opt_areas.append("algebraic reassociation & instruction combination (reassociate, instcombine)")
        if w_prof.loop_count > 0 and (w_prof.float_ops > 0 or w_prof.int_ops > 2):
            opt_areas.append("SIMD vectorization (loop-vectorize, slp-vectorize)")
        if w_prof.function_count > 1 or w_prof.call_count > 0:
            opt_areas.append("interprocedural inlining (inline, ipconstprop)")
        if not opt_areas:
            opt_areas.append("general control-flow simplification (simplifycfg, dce)")

        return ProfileFeatureSummary(
            source_path=source_path,
            source_filename=os.path.basename(source_path),
            language=language,
            lines_of_code=w_prof.lines_of_code,
            function_count=w_prof.function_count,
            loop_count=w_prof.loop_count,
            max_loop_depth=w_prof.max_loop_depth,
            loop_intensity=loop_int,
            memory_intensity=mem_int,
            branch_intensity=branch_int,
            floating_point_intensity=fp_int,
            function_calls_intensity=call_int,
            int_ops=w_prof.int_ops,
            float_ops=w_prof.float_ops,
            array_accesses=w_prof.array_accesses,
            pointer_derefs=w_prof.pointer_derefs,
            potential_optimization_areas=opt_areas,
            raw_profile=w_prof.model_dump(),
        )
