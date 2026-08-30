"""
InspectService: Deep LLVM IR and Assembly transformation inspection service.
Exposes raw IR, -O3 transformed IR, Autotune candidate IR, and compiler assembly comparisons.
"""

import difflib
import json
import os
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.doctor.checks import run_doctor_checks
from autotune.llvm.compiler import CompilerDriver, AssemblyMetrics
from autotune.llvm.passes import PassSequence


class InspectionResult(BaseModel):
    source_path: str
    pass_sequence: List[str] = Field(default_factory=list)
    raw_ir_preview: str = ""
    baseline_ir_preview: str = ""
    candidate_ir_preview: str = ""
    ir_diff_preview: str = ""
    baseline_assembly_metrics: AssemblyMetrics
    candidate_assembly_metrics: AssemblyMetrics
    vector_instruction_gain: int = 0
    instruction_count_delta: int = 0


class InspectService:
    """Inspects LLVM IR transformations and assembly metrics for C/C++ workloads."""

    @staticmethod
    def inspect_workload(
        source: str,
        pass_sequence_str: Optional[str] = None,
        report_json: Optional[str] = None,
    ) -> InspectionResult:
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source file '{source}' not found.")

        passes: List[str] = []
        if report_json and os.path.exists(report_json):
            with open(report_json, "r", encoding="utf-8") as f:
                rdata = json.load(f)
            pdata = rdata.get("prescription", {})
            passes = pdata.get("pass_sequence", {}).get("passes", [])
        elif pass_sequence_str:
            passes = [p.strip() for p in pass_sequence_str.replace(",", " ").split() if p.strip()]
        else:
            # Default representative passes if none specified
            passes = ["mem2reg", "instcombine", "loop-simplify", "loop-vectorize"]

        doc_report = run_doctor_checks()
        compiler = CompilerDriver(
            clang_path=doc_report.clang_path,
            clangxx_path=doc_report.clangxx_path,
            opt_path=doc_report.opt_path,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            base_ir = os.path.join(tmpdir, "baseline.ll")
            cand_ir = os.path.join(tmpdir, "candidate.ll")
            base_asm = os.path.join(tmpdir, "baseline.s")
            cand_asm = os.path.join(tmpdir, "candidate.s")

            # Emit baseline IR & Assembly
            compiler.emit_llvm_ir(source, base_ir)
            compiler.emit_assembly(source, base_asm, opt_level="-O3")

            # Emit candidate IR & Assembly
            seq = PassSequence(passes=passes)
            compiler.emit_llvm_ir(source, cand_ir, pass_sequence=seq)
            compiler.emit_assembly(source, cand_asm, pass_sequence=seq)

            # Analyze assembly
            b_metrics = compiler.analyze_assembly(base_asm)
            c_metrics = compiler.analyze_assembly(cand_asm)

            # Read previews
            b_ir_text = ""
            if os.path.exists(base_ir):
                with open(base_ir, "r", encoding="utf-8", errors="ignore") as f:
                    b_ir_text = f.read()

            c_ir_text = ""
            if os.path.exists(cand_ir):
                with open(cand_ir, "r", encoding="utf-8", errors="ignore") as f:
                    c_ir_text = f.read()

            # Generate unified diff of first 100 lines
            diff_lines = list(difflib.unified_diff(
                b_ir_text.splitlines()[:150],
                c_ir_text.splitlines()[:150],
                fromfile="-O3 Baseline LLVM IR",
                tofile="Autotune Optimized LLVM IR",
                lineterm="",
            ))
            diff_str = "\n".join(diff_lines[:40]) if diff_lines else "No textual differences in first 150 lines of IR."

            b_preview = "\n".join(b_ir_text.splitlines()[:25])
            c_preview = "\n".join(c_ir_text.splitlines()[:25])

            instr_delta = c_metrics.total_instructions - b_metrics.total_instructions
            vec_gain = c_metrics.vector_instructions - b_metrics.vector_instructions

            return InspectionResult(
                source_path=source,
                pass_sequence=passes,
                raw_ir_preview="",
                baseline_ir_preview=b_preview,
                candidate_ir_preview=c_preview,
                ir_diff_preview=diff_str,
                baseline_assembly_metrics=b_metrics,
                candidate_assembly_metrics=c_metrics,
                vector_instruction_gain=vec_gain,
                instruction_count_delta=instr_delta,
            )
