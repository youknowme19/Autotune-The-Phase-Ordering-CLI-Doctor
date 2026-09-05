"""
ApplyService: Reconstructs winning optimization pipelines and exports standalone
production compiler artifacts (.ll, .optimized.ll, .s, binary executable, manifest.json).
Never overwrites original source code.
"""

import datetime
import hashlib
import json
import os
import subprocess
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.doctor.checks import run_doctor_checks
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence


class ApplyResult(BaseModel):
    success: bool
    source_path: str
    output_dir: str
    raw_ir_path: Optional[str] = None
    optimized_ir_path: Optional[str] = None
    assembly_path: Optional[str] = None
    binary_path: Optional[str] = None
    manifest_path: Optional[str] = None
    pass_sequence: List[str] = Field(default_factory=list)
    reproducible_command: str = ""
    error_message: Optional[str] = None


class ApplyService:
    """Applies discovered optimization to produce standalone compiler artifacts."""

    @staticmethod
    def apply_report(
        report_path: str,
        output_dir: Optional[str] = None,
    ) -> ApplyResult:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Optimization report '{report_path}' not found.")

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        source_path = data.get("source_path")
        if not source_path or not os.path.exists(source_path):
            # Check relative to report
            alt = os.path.basename(source_path or "")
            if alt and os.path.exists(alt):
                source_path = alt
            else:
                raise FileNotFoundError(f"Source file '{source_path}' referenced in report is not accessible.")

        p_data = data.get("prescription", {})
        passes = p_data.get("pass_sequence", {}).get("passes", [])
        run_id = data.get("run_id") or "run_latest"

        # Determine target artifact directory
        target_dir = output_dir or os.path.join(".autotune", "artifacts", run_id)
        os.makedirs(target_dir, exist_ok=True)

        doc = run_doctor_checks()
        compiler = CompilerDriver(
            clang_path=doc.clang_path,
            clangxx_path=doc.clangxx_path,
            opt_path=doc.opt_path,
        )

        stem = os.path.splitext(os.path.basename(source_path))[0]
        raw_ir = os.path.join(target_dir, f"{stem}.ll")
        opt_ir = os.path.join(target_dir, f"{stem}.optimized.ll")
        asm_out = os.path.join(target_dir, f"{stem}.s")
        bin_out = os.path.join(target_dir, f"{stem}.bin")
        manifest_path = os.path.join(target_dir, "manifest.json")

        try:
            # 1. Emit unoptimized LLVM IR
            compiler.emit_llvm_ir(source_path, raw_ir)

            # 2. Run opt pass pipeline to produce optimized LLVM IR
            seq = PassSequence(passes=passes)
            opt_bin = doc.opt_path or "opt"
            passes_str = seq.to_opt_string() if passes else ""
            if passes_str:
                cmd_opt = [opt_bin, f"-passes={passes_str}", raw_ir, "-S", "-o", opt_ir]
            else:
                cmd_opt = [opt_bin, "-passes=default<O3>", raw_ir, "-S", "-o", opt_ir]
            res_opt = subprocess.run(cmd_opt, capture_output=True, text=True)
            if res_opt.returncode != 0:
                raise RuntimeError(
                    f"LLVM opt pipeline failed with exit code {res_opt.returncode}: {res_opt.stderr.strip() or res_opt.stdout.strip()}"
                )

            # 3. Emit assembly from optimized IR
            compiler.emit_assembly(source_path, asm_out, pass_sequence=seq if passes else None)

            # 4. Compile native executable binary
            cand_comp = compiler.compile_candidate(source_path, seq, bin_out)
            if not cand_comp.success:
                raise RuntimeError(f"Binary compilation failed: {cand_comp.error_message}")

            # 5. Build manifest.json
            with open(source_path, "rb") as f:
                src_hash = hashlib.sha256(f.read()).hexdigest()

            manifest_data = {
                "run_id": run_id,
                "source_path": os.path.abspath(source_path),
                "source_hash": src_hash,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "toolchain": {
                    "clang": doc.clang_version,
                    "opt": doc.opt_version,
                    "target_triple": doc.target_triple,
                    "arch": doc.arch,
                },
                "pass_sequence": passes,
                "artifacts": {
                    "unoptimized_ir": os.path.abspath(raw_ir),
                    "optimized_ir": os.path.abspath(opt_ir),
                    "assembly": os.path.abspath(asm_out),
                    "binary": os.path.abspath(bin_out),
                },
                "reproducible_command": p_data.get("reproducible_clang_command", ""),
            }

            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f, indent=2)

            return ApplyResult(
                success=True,
                source_path=source_path,
                output_dir=target_dir,
                raw_ir_path=raw_ir,
                optimized_ir_path=opt_ir,
                assembly_path=asm_out,
                binary_path=bin_out,
                manifest_path=manifest_path,
                pass_sequence=passes,
                reproducible_command=p_data.get("reproducible_clang_command", ""),
            )

        except Exception as e:
            return ApplyResult(
                success=False,
                source_path=source_path,
                output_dir=target_dir,
                error_message=str(e),
                pass_sequence=passes,
            )
