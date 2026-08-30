"""
C/C++ AST and structural source code analyzer using Clang AST JSON dumps.
"""

import json
import os
import re
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autotune.doctor.checks import find_tool


class ASTNodeSummary(BaseModel):
    lines_of_code: int
    loop_count: int
    nested_loop_max_depth: int
    function_count: int
    call_count: int
    int_ops: int
    float_ops: int
    bitwise_ops: int
    array_accesses: int
    pointer_derefs: int
    has_arrays_or_pointers: bool
    has_math_lib: bool
    estimated_memory_intensity: float
    estimated_compute_intensity: float


class SourceAnalyzer:
    """Parses and analyzes C/C++ source code via Clang AST JSON dumps and regex analysis."""

    def __init__(self, clang_path: Optional[str] = None):
        self.clang_path = find_tool("clang", clang_path) or "clang"

    def analyze_source_file(self, source_path: str) -> ASTNodeSummary:
        """Run clang -Xclang -ast-dump=json to extract structural AST details."""
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Source file not found: {source_path}")

        with open(source_path, "r", encoding="utf-8") as f:
            content = f.read()

        loc = len([line for line in content.splitlines() if line.strip() and not line.strip().startswith("//")])

        # Attempt Clang JSON AST dump first
        cmd = [self.clang_path, "-Xclang", "-ast-dump=json", "-fsyntax-only", os.path.abspath(source_path)]
        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10
            )
            if res.returncode == 0 and res.stdout:
                ast_json = json.loads(res.stdout)
                return self._parse_ast_json(ast_json, loc, content)
        except Exception:
            pass

        # Fallback regex parsing
        return self._parse_fallback(content, loc)

    def analyze_source(self, source_code: str) -> ASTNodeSummary:
        """Analyze source string via fallback parser."""
        lines = [line.strip() for line in source_code.splitlines() if line.strip() and not line.strip().startswith("//")]
        return self._parse_fallback(source_code, len(lines))

    def _parse_ast_json(self, ast: Dict[str, Any], loc: int, raw_source: str) -> ASTNodeSummary:
        """Recursively traverse Clang AST JSON structure to count nodes."""
        loop_count = 0
        max_depth = 0
        function_count = 0
        call_count = 0
        int_ops = 0
        float_ops = 0
        bitwise_ops = 0
        array_accesses = 0
        pointer_derefs = 0

        def traverse(node: Any, current_depth: int = 0) -> None:
            nonlocal loop_count, max_depth, function_count, call_count
            nonlocal int_ops, float_ops, bitwise_ops, array_accesses, pointer_derefs

            if not isinstance(node, dict):
                return

            kind = node.get("kind", "")

            if kind in ("ForStmt", "WhileStmt", "DoStmt"):
                loop_count += 1
                current_depth += 1
                if current_depth > max_depth:
                    max_depth = current_depth

            elif kind == "FunctionDecl" and node.get("isReferenced", False) or node.get("name") == "main":
                function_count += 1

            elif kind == "CallExpr":
                call_count += 1

            elif kind == "ArraySubscriptExpr":
                array_accesses += 1

            elif kind == "UnaryOperator" and node.get("opcode") == "*":
                pointer_derefs += 1

            elif kind == "BinaryOperator":
                opcode = node.get("opcode", "")
                if opcode in ("^", "&", "|", "<<", ">>"):
                    bitwise_ops += 1
                elif opcode in ("+", "-", "*", "/", "%"):
                    # Check type if available
                    type_str = str(node.get("type", {}).get("qualType", ""))
                    if "double" in type_str or "float" in type_str:
                        float_ops += 1
                    else:
                        int_ops += 1

            # Recurse children
            for key, val in node.items():
                if key == "inner" and isinstance(val, list):
                    for child in val:
                        traverse(child, current_depth)

        traverse(ast)

        has_math = "#include <math.h>" in raw_source or "sqrt" in raw_source or "pow" in raw_source
        has_ptrs = array_accesses > 0 or pointer_derefs > 0 or "*" in raw_source

        mem_intensity = round((array_accesses + pointer_derefs) / max(loc, 1), 2)
        compute_intensity = round((int_ops + float_ops + bitwise_ops) / max(loc, 1), 2)

        return ASTNodeSummary(
            lines_of_code=loc,
            loop_count=loop_count,
            nested_loop_max_depth=max_depth,
            function_count=max(function_count, 1),
            call_count=call_count,
            int_ops=int_ops,
            float_ops=float_ops,
            bitwise_ops=bitwise_ops,
            array_accesses=array_accesses,
            pointer_derefs=pointer_derefs,
            has_arrays_or_pointers=has_ptrs,
            has_math_lib=has_math,
            estimated_memory_intensity=mem_intensity,
            estimated_compute_intensity=compute_intensity,
        )

    def _parse_fallback(self, source_code: str, loc: int) -> ASTNodeSummary:
        """Regex structural analyzer fallback."""
        lines = [line.strip() for line in source_code.splitlines() if line.strip() and not line.strip().startswith("//")]

        for_loops = len(re.findall(r"\bfor\s*\(", source_code))
        while_loops = len(re.findall(r"\bwhile\s*\(", source_code))
        total_loops = for_loops + while_loops

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
        call_count = len(re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\s*\(", source_code)) - functions

        int_ops = len(re.findall(r"[\+\-\*/%]", source_code))
        float_ops = len(re.findall(r"(double|float)", source_code))
        bitwise_ops = len(re.findall(r"[\^&|]", source_code)) + len(re.findall(r"(<<|>>)", source_code))

        array_accesses = len(re.findall(r"\[\s*[^\]]+\s*\]", source_code))
        pointer_derefs = len(re.findall(r"\*[a-zA-Z_]", source_code))

        has_ptrs = bool(re.search(r"(\*|\[\s*\])", source_code))
        has_math = "#include <math.h>" in source_code or "sqrt" in source_code or "pow" in source_code

        mem_intensity = round((array_accesses + pointer_derefs) / max(loc, 1), 2)
        compute_intensity = round((int_ops + float_ops + bitwise_ops) / max(loc, 1), 2)

        return ASTNodeSummary(
            lines_of_code=loc,
            loop_count=total_loops,
            nested_loop_max_depth=max_nesting,
            function_count=max(functions, 1),
            call_count=max(call_count, 0),
            int_ops=int_ops,
            float_ops=float_ops,
            bitwise_ops=bitwise_ops,
            array_accesses=array_accesses,
            pointer_derefs=pointer_derefs,
            has_arrays_or_pointers=has_ptrs,
            has_math_lib=has_math,
            estimated_memory_intensity=mem_intensity,
            estimated_compute_intensity=compute_intensity,
        )


ASTAnalyzer = SourceAnalyzer
