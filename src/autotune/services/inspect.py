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
    cfg_diagram: str = ""
    dot_cfg: str = ""
    basic_blocks_count: int = 0


# Alias for naming consistency
InspectResult = InspectionResult


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
            b_metrics = compiler.analyze_assembly(base_asm)

            # Emit candidate IR & Assembly
            seq = PassSequence(passes=passes)
            compiler.emit_llvm_ir(source, cand_ir, pass_sequence=seq)
            compiler.emit_assembly(source, cand_asm, pass_sequence=seq)
            c_metrics = compiler.analyze_assembly(cand_asm)

            # Read previews
            b_preview = ""
            if os.path.exists(base_ir):
                with open(base_ir, "r", encoding="utf-8", errors="ignore") as f:
                    b_preview = f.read()

            c_preview = ""
            if os.path.exists(cand_ir):
                with open(cand_ir, "r", encoding="utf-8", errors="ignore") as f:
                    c_preview = f.read()

            # Structural IR Unified Diff
            diff_lines = list(difflib.unified_diff(
                b_preview.splitlines(keepends=True)[:150],
                c_preview.splitlines(keepends=True)[:150],
                fromfile="-O3 Baseline LLVM IR",
                tofile="Autotune Optimized LLVM IR",
                n=3,
            ))
            diff_str = "".join(diff_lines) if diff_lines else "No textual differences detected in preview IR."

            vec_gain = c_metrics.vector_instructions - b_metrics.vector_instructions
            instr_delta = c_metrics.total_instructions - b_metrics.total_instructions
            cfg_art, bb_count = InspectService._build_cfg_ascii(c_preview)
            dot_graph = InspectService._build_cfg_dot(c_preview)

            return InspectionResult(
                source_path=source,
                pass_sequence=passes,
                raw_ir_preview=b_preview[:1500],
                baseline_ir_preview=b_preview[:1500],
                candidate_ir_preview=c_preview[:1500],
                ir_diff_preview=diff_str,
                baseline_assembly_metrics=b_metrics,
                candidate_assembly_metrics=c_metrics,
                vector_instruction_gain=vec_gain,
                instruction_count_delta=instr_delta,
                cfg_diagram=cfg_art,
                dot_cfg=dot_graph,
                basic_blocks_count=bb_count,
            )

    @staticmethod
    def _build_cfg_ascii(llvm_ir: str) -> tuple[str, int]:
        """Generates an ASCII Control Flow Graph (CFG) from LLVM IR basic blocks."""
        blocks = []
        current_label = "entry"
        current_instrs = 0

        for line in llvm_ir.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith(";"):
                continue
            if line_str.endswith(":") and not line_str.startswith(" "):
                if current_instrs > 0:
                    blocks.append((current_label, current_instrs))
                current_label = line_str[:-1]
                current_instrs = 0
            else:
                current_instrs += 1

        if current_instrs > 0:
            blocks.append((current_label, current_instrs))

        if not blocks:
            return ("  [entry] (single basic block)", 1)

        max_instrs = max(b[1] for b in blocks) or 1
        cfg_lines = []
        for i, (label, count) in enumerate(blocks[:8]):
            bar_len = min(12, max(1, int(count / max_instrs * 12)))
            bar = "█" * bar_len + "░" * (12 - bar_len)
            box = f"┌── Basic Block: {label} [{bar}] ({count} instrs) ──┐"
            cfg_lines.append(f"  {box}")
            if i < len(blocks) - 1 and i < 7:
                cfg_lines.append("          │")
                cfg_lines.append("          ▼")
        if len(blocks) > 8:
            cfg_lines.append(f"  ... ({len(blocks) - 8} more basic blocks)")

        return ("\n".join(cfg_lines), len(blocks))

    @staticmethod
    def _build_cfg_dot(llvm_ir: str) -> str:
        """Generates Graphviz DOT representation of basic block control flow."""
        blocks = []
        current_label = "entry"
        current_instrs = 0

        for line in llvm_ir.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith(";"):
                continue
            if line_str.endswith(":") and not line_str.startswith(" "):
                if current_instrs > 0:
                    blocks.append((current_label, current_instrs))
                current_label = line_str[:-1]
                current_instrs = 0
            else:
                current_instrs += 1

        if current_instrs > 0:
            blocks.append((current_label, current_instrs))

        dot_lines = ["digraph CFG {", '  node [shape=box, style=rounded, fontname="Courier"];']
        for label, count in blocks:
            safe_label = label.replace('"', '\\"')
            dot_lines.append(f'  "{safe_label}" [label="{safe_label}\\n({count} instructions)"];')

        for i in range(len(blocks) - 1):
            dot_lines.append(f'  "{blocks[i][0]}" -> "{blocks[i+1][0]}";')

        dot_lines.append("}")
        return "\n".join(dot_lines)
