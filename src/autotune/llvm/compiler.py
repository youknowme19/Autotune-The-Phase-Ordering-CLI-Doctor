"""
Compiler driver invoking Clang and Opt to produce binaries.
"""

import os
import subprocess
import tempfile
from typing import List, Optional
from pydantic import BaseModel

from autotune.doctor.checks import find_tool
from autotune.doctor.errors import DoctorError, ErrorCode
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.llvm.pipeline import PipelineBuilder


class CompilationResult(BaseModel):
    success: bool
    binary_path: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None


class CompilerDriver:
    """Invokes Clang and Opt to compile C/C++ sources into binaries."""

    def __init__(
        self,
        clang_path: Optional[str] = None,
        opt_path: Optional[str] = None,
    ):
        self.clang_path = find_tool("clang", clang_path) or "clang"
        self.opt_path = find_tool("opt", opt_path)
        self.validator = PassValidator(opt_path=self.opt_path)

    def compile_baseline(
        self,
        source_path: str,
        output_binary_path: str,
        opt_level: str = "-O3",
        extra_flags: Optional[List[str]] = None,
    ) -> CompilationResult:
        """Compile baseline binary using standard optimization level (e.g. -O3)."""
        if not os.path.exists(source_path):
            return CompilationResult(
                success=False, error_message=f"Source file not found: {source_path}"
            )

        cmd = [self.clang_path, opt_level, os.path.abspath(source_path), "-o", os.path.abspath(output_binary_path)]
        if extra_flags:
            cmd.extend(extra_flags)

        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            if res.returncode == 0 and os.path.exists(output_binary_path):
                return CompilationResult(
                    success=True,
                    binary_path=os.path.abspath(output_binary_path),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            else:
                return CompilationResult(
                    success=False,
                    stdout=res.stdout,
                    stderr=res.stderr,
                    error_message=f"Compilation failed with exit code {res.returncode}: {res.stderr}",
                )
        except Exception as e:
            return CompilationResult(
                success=False, error_message=f"Compilation exception: {str(e)}"
            )

    def compile_candidate(
        self,
        source_path: str,
        pass_sequence: PassSequence,
        output_binary_path: str,
        extra_flags: Optional[List[str]] = None,
    ) -> CompilationResult:
        """Compile candidate binary with specific LLVM pass sequence."""
        if not os.path.exists(source_path):
            return CompilationResult(
                success=False, error_message=f"Source file not found: {source_path}"
            )

        # Validate passes first
        invalid_passes = [p for p in pass_sequence.passes if not self.validator.is_valid_pass(p)]
        if invalid_passes:
            e04 = DoctorError(
                ErrorCode.E04,
                f"Candidate contained invalid or unsupported LLVM passes: {invalid_passes}",
            )
            return CompilationResult(
                success=False, error_message=str(e04)
            )

        output_bin = os.path.abspath(output_binary_path)
        out_dir = os.path.dirname(output_bin)
        os.makedirs(out_dir, exist_ok=True)

        # If opt is available, perform standard LLVM IR pass pipeline compilation
        if self.opt_path and os.path.exists(self.opt_path):
            with tempfile.TemporaryDirectory(dir=out_dir) as tmpdir:
                ir_path = os.path.join(tmpdir, "kernel.ll")
                opt_ir_path = os.path.join(tmpdir, "kernel_opt.ll")

                # Step 1: Emit LLVM IR
                cmd_emit = [
                    self.clang_path,
                    "-O0",
                    "-Xclang",
                    "-disable-O0-optnone",
                    "-emit-llvm",
                    "-S",
                    os.path.abspath(source_path),
                    "-o",
                    ir_path,
                ]
                res1 = subprocess.run(
                    cmd_emit, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                )
                if res1.returncode != 0:
                    return CompilationResult(
                        success=False,
                        stdout=res1.stdout,
                        stderr=res1.stderr,
                        error_message=f"Clang IR emission failed: {res1.stderr}",
                    )

                # Step 2: Run passes via opt
                passes_str = ",".join(pass_sequence.passes) if pass_sequence.passes else "mem2reg"
                cmd_opt = [
                    self.opt_path,
                    f"-passes={passes_str}",
                    ir_path,
                    "-S",
                    "-o",
                    opt_ir_path,
                ]
                res2 = subprocess.run(
                    cmd_opt, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                )
                if res2.returncode != 0:
                    return CompilationResult(
                        success=False,
                        stdout=res2.stdout,
                        stderr=res2.stderr,
                        error_message=f"Opt pass pipeline execution failed: {res2.stderr}",
                    )

                # Step 3: Compile optimized IR to binary
                cmd_bin = [self.clang_path, opt_ir_path, "-o", output_bin]
                if extra_flags:
                    cmd_bin.extend(extra_flags)
                res3 = subprocess.run(
                    cmd_bin, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=20
                )
                if res3.returncode == 0 and os.path.exists(output_bin):
                    return CompilationResult(
                        success=True,
                        binary_path=output_bin,
                        stdout=res3.stdout,
                        stderr=res3.stderr,
                    )
                else:
                    return CompilationResult(
                        success=False,
                        stdout=res3.stdout,
                        stderr=res3.stderr,
                        error_message=f"Clang binary assembly failed: {res3.stderr}",
                    )
        else:
            # Fallback: Clang direct compilation with pass arguments
            cmd = [
                self.clang_path,
                "-O2",
                os.path.abspath(source_path),
                "-o",
                output_bin,
            ]
            if extra_flags:
                cmd.extend(extra_flags)
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            if res.returncode == 0 and os.path.exists(output_bin):
                return CompilationResult(
                    success=True,
                    binary_path=output_bin,
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            return CompilationResult(
                success=False,
                stdout=res.stdout,
                stderr=res.stderr,
                error_message=f"Clang compilation failed: {res.stderr}",
            )
