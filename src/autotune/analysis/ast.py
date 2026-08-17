"""
C/C++ AST and structural source code analyzer.
"""

import re
from typing import Dict, List
from pydantic import BaseModel


class ASTNodeSummary(BaseModel):
    lines_of_code: int
    loop_count: int
    nested_loop_max_depth: int
    function_count: int
    has_arrays_or_pointers: bool
    has_math_lib: bool
    estimated_memory_intensity: float
    estimated_compute_intensity: float


class SourceAnalyzer:
    """Parses and analyzes C/C++ source code to build a structural representation."""

    def analyze_source(self, source_code: str) -> ASTNodeSummary:
        lines = [line.strip() for line in source_code.splitlines() if line.strip() and not line.strip().startswith("//")]
        loc = len(lines)

        # Basic structural pattern matching
        for_loops = len(re.findall(r"\bfor\s*\(", source_code))
        while_loops = len(re.findall(r"\bwhile\s*\(", source_code))
        total_loops = for_loops + while_loops

        # Max nesting heuristic
        current_nesting = 0
        max_nesting = 0
        for line in lines:
            if "for" in line or "while" in line:
                current_nesting += 1
                if current_nesting > max_nesting:
                    max_nesting = current_nesting
            if "}" in line and current_nesting > 0:
                current_nesting -= 1

        functions = len(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s+[a-zA-Z_][a-zA-Z0-9_]*\s*\([^)]*\)\s*\{", source_code))
        has_ptrs = bool(re.search(r"(\*|\[\s*\])", source_code))
        has_math = "#include <math.h>" in source_code or "sqrt" in source_code or "pow" in source_code

        # Operations count heuristics
        arith_ops = len(re.findall(r"[\+\-\*/%]", source_code))
        mem_ops = len(re.findall(r"(\[\s*[^\]]+\s*\]|\*|\-\>)", source_code))

        mem_intensity = mem_ops / max(loc, 1)
        compute_intensity = arith_ops / max(loc, 1)

        return ASTNodeSummary(
            lines_of_code=loc,
            loop_count=total_loops,
            nested_loop_max_depth=max_nesting,
            function_count=max(functions, 1),
            has_arrays_or_pointers=has_ptrs,
            has_math_lib=has_math,
            estimated_memory_intensity=round(mem_intensity, 2),
            estimated_compute_intensity=round(compute_intensity, 2),
        )
