"""
Feature extraction producing compact JSON descriptions of C workloads.
"""

import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from autotune.analysis.ast import ASTNodeSummary, SourceAnalyzer


class CompactCodeFeatures(BaseModel):
    filename: str
    summary: ASTNodeSummary
    suggested_focus_areas: List[str]

    def to_compact_json(self) -> str:
        return self.model_dump_json(indent=2)


class FeatureExtractor:
    """Extracts compact feature summaries from C/C++ source files."""

    def __init__(self, clang_path: Optional[str] = None):
        self.analyzer = SourceAnalyzer(clang_path=clang_path)

    def extract_from_file(self, file_path: str) -> CompactCodeFeatures:
        filename = os.path.basename(file_path)
        ast_summary = self.analyzer.analyze_source_file(file_path)
        focus: List[str] = []

        if ast_summary.loop_count > 0:
            focus.append("loop_canonicalization_and_unrolling")
            if ast_summary.has_arrays_or_pointers or ast_summary.array_accesses > 0:
                focus.append("vectorization_and_licm")
        if ast_summary.float_ops > 0:
            focus.append("floating_point_reassociation_and_slp")
        if ast_summary.estimated_memory_intensity > 0.5:
            focus.append("memory_coalescing_and_gvn")
        if ast_summary.estimated_compute_intensity > 0.5:
            focus.append("instruction_combining_and_reassociation")

        if not focus:
            focus.append("scalar_optimizations")

        return CompactCodeFeatures(
            filename=filename,
            summary=ast_summary,
            suggested_focus_areas=focus,
        )
