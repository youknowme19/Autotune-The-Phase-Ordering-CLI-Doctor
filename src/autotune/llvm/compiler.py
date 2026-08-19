"""
Compiler driver invoking Clang and Opt to produce binaries from C/C++ source code.
"""

import os
import platform
import subprocess
import tempfile
import time
from typing import List, Optional
from pydantic import BaseModel, Field

from autotune.doctor.checks import find_tool
from autotune.doctor.errors import DoctorError, ErrorCode
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.llvm.pipeline import PipelineBuilder


class CompilationResult(BaseModel):
    """Structured metadata returned for every compilation attempt."""

    success: bool
    binary_path: Optional[str] = None
    raw_bitcode_path: Optional[str] = None
    optimized_bitcode_path: Optional[str] = None
    pass_sequence_str: Optional[str] = None
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None


class CompilerDriver:
    """Invokes Clang and Opt to lower C/C++ source to bitcode, apply passes, and emit executables."""

    def __init__(
        self,
        clang_path: Optional[str] = None,
        opt_path: Optional[str] = None,
        target_arch: Optional[str] = None,
    ):
        self.clang_path = find_tool("clang", clang_path) or "clang"
        self.opt_path = find_tool("opt", opt_path)
        self.target_arch = target_arch or platform.machine()
        self.validator = PassValidator(opt_path=self.opt_path)

        self.clang_version: str = "Clang 22.1"
        self.opt_version: str = "Opt 22.1"


    def compile_bitcode(
        self,
        source_path: str,
        output_bitcode_path: str,
        timeout_seconds: float = 20.0,
    ) -> CompilationResult:
        """Step 1: Compile C/C++ source to unoptimized LLVM bitcode without optnone attribute."""
        if not os.path.exists(source_path):
            return CompilationResult(
                success=False, error_message=f"Source file not found: {source_path}"
            )

        output_bc = os.path.abspath(output_bitcode_path)
        os.makedirs(os.path.dirname(output_bc), exist_ok=True)

        cmd = [
            self.clang_path,
            "-O0",
            "-Xclang",
            "-disable-O0-optnone",
            "-emit-llvm",
            "-c",
            os.path.abspath(source_path),
            "-o",
            output_bc,
        ]

        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if res.returncode == 0 and os.path.exists(output_bc):
                return CompilationResult(
                    success=True,
                    raw_bitcode_path=output_bc,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            else:
                return CompilationResult(
                    success=False,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                    error_message=f"Bitcode generation failed with exit code {res.returncode}: {res.stderr}",
                )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                error_message=f"Bitcode generation timed out after {timeout_seconds} seconds.",
            )
        except Exception as e:
            return CompilationResult(
                success=False, error_message=f"Bitcode generation exception: {str(e)}"
            )

    def run_opt_passes(
        self,
        input_bitcode_path: str,
        pass_sequence: PassSequence,
        output_bitcode_path: str,
        timeout_seconds: float = 20.0,
    ) -> CompilationResult:
        """Step 2: Transform bitcode via opt using modern pass sequence syntax."""
        if not os.path.exists(input_bitcode_path):
            return CompilationResult(
                success=False, error_message=f"Input bitcode not found: {input_bitcode_path}"
            )

        if not self.opt_path or not os.path.exists(self.opt_path):
            return CompilationResult(
                success=False, error_message="LLVM 'opt' binary not found on local system."
            )

        # Validate passes first to ensure invalid/hallucinated passes do not reach opt
        invalid_passes = [
            p for p in pass_sequence.passes if not self.validator.is_valid_pass(p)
        ]
        if invalid_passes:
            e04 = DoctorError(
                ErrorCode.E04,
                f"Candidate contained invalid or unsupported LLVM passes: {invalid_passes}",
            )
            return CompilationResult(
                success=False, error_message=str(e04)
            )

        output_opt_bc = os.path.abspath(output_bitcode_path)
        os.makedirs(os.path.dirname(output_opt_bc), exist_ok=True)
        pass_str = pass_sequence.to_opt_string()

        cmd = [
            self.opt_path,
            f"-passes={pass_str}",
            os.path.abspath(input_bitcode_path),
            "-o",
            output_opt_bc,
        ]

        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if res.returncode == 0 and os.path.exists(output_opt_bc):
                return CompilationResult(
                    success=True,
                    raw_bitcode_path=os.path.abspath(input_bitcode_path),
                    optimized_bitcode_path=output_opt_bc,
                    pass_sequence_str=pass_str,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            else:
                return CompilationResult(
                    success=False,
                    pass_sequence_str=pass_str,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                    error_message=f"Opt pass execution failed with exit code {res.returncode}: {res.stderr}",
                )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                pass_sequence_str=pass_str,
                error_message=f"Opt pass execution timed out after {timeout_seconds} seconds.",
            )
        except Exception as e:
            return CompilationResult(
                success=False,
                pass_sequence_str=pass_str,
                error_message=f"Opt execution exception: {str(e)}",
            )

    def emit_executable(
        self,
        bitcode_path: str,
        output_binary_path: str,
        extra_flags: Optional[List[str]] = None,
        timeout_seconds: float = 20.0,
    ) -> CompilationResult:
        """Step 3: Compile optimized bitcode into native machine executable."""
        if not os.path.exists(bitcode_path):
            return CompilationResult(
                success=False, error_message=f"Bitcode file not found: {bitcode_path}"
            )

        output_bin = os.path.abspath(output_binary_path)
        os.makedirs(os.path.dirname(output_bin), exist_ok=True)

        cmd = [self.clang_path]
        if platform.system() == "Darwin" and self.target_arch:
            cmd.extend(["-arch", self.target_arch])

        cmd.extend([os.path.abspath(bitcode_path), "-o", output_bin])
        if extra_flags:
            cmd.extend(extra_flags)

        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if res.returncode == 0 and os.path.exists(output_bin):
                return CompilationResult(
                    success=True,
                    binary_path=output_bin,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            else:
                return CompilationResult(
                    success=False,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                    error_message=f"Native binary emission failed: {res.stderr}",
                )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False,
                error_message=f"Executable emission timed out after {timeout_seconds} seconds.",
            )
        except Exception as e:
            return CompilationResult(
                success=False, error_message=f"Executable emission exception: {str(e)}"
            )

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

        output_bin = os.path.abspath(output_binary_path)
        os.makedirs(os.path.dirname(output_bin), exist_ok=True)

        cmd = [self.clang_path, opt_level]
        if platform.system() == "Darwin" and self.target_arch:
            cmd.extend(["-arch", self.target_arch])

        cmd.extend([os.path.abspath(source_path), "-o", output_bin])
        if extra_flags:
            cmd.extend(extra_flags)

        start_t = time.perf_counter()
        try:
            res = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30
            )
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if res.returncode == 0 and os.path.exists(output_bin):
                return CompilationResult(
                    success=True,
                    binary_path=output_bin,
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            else:
                return CompilationResult(
                    success=False,
                    duration_ms=round(elapsed_ms, 2),
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
        """Complete 3-step LLVM pipeline: source -> raw.bc -> opt -> opt.bc -> candidate.bin."""
        if not os.path.exists(source_path):
            return CompilationResult(
                success=False, error_message=f"Source file not found: {source_path}"
            )

        # Validate passes first
        invalid_passes = [
            p for p in pass_sequence.passes if not self.validator.is_valid_pass(p)
        ]
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

        start_t = time.perf_counter()

        # If opt is available, perform full 3-step LLVM pipeline compilation
        if self.opt_path and os.path.exists(self.opt_path):
            with tempfile.TemporaryDirectory(dir=out_dir) as tmpdir:
                raw_bc = os.path.join(tmpdir, "raw.bc")
                opt_bc = os.path.join(tmpdir, "opt.bc")

                # Step 1: Lower C/C++ to raw bitcode (-disable-O0-optnone)
                step1 = self.compile_bitcode(source_path, raw_bc)
                if not step1.success:
                    return step1

                # Step 2: Run pass sequence using opt -passes="..."
                step2 = self.run_opt_passes(raw_bc, pass_sequence, opt_bc)
                if not step2.success:
                    return step2

                # Step 3: Emit native machine executable
                step3 = self.emit_executable(opt_bc, output_bin, extra_flags=extra_flags)
                elapsed_ms = (time.perf_counter() - start_t) * 1000.0

                if step3.success:
                    return CompilationResult(
                        success=True,
                        binary_path=output_bin,
                        raw_bitcode_path=raw_bc,
                        optimized_bitcode_path=opt_bc,
                        pass_sequence_str=pass_sequence.to_opt_string(),
                        duration_ms=round(elapsed_ms, 2),
                        stdout=step3.stdout,
                        stderr=step3.stderr,
                    )
                else:
                    return step3
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
            elapsed_ms = (time.perf_counter() - start_t) * 1000.0

            if res.returncode == 0 and os.path.exists(output_bin):
                return CompilationResult(
                    success=True,
                    binary_path=output_bin,
                    pass_sequence_str=pass_sequence.to_opt_string(),
                    duration_ms=round(elapsed_ms, 2),
                    stdout=res.stdout,
                    stderr=res.stderr,
                )
            return CompilationResult(
                success=False,
                duration_ms=round(elapsed_ms, 2),
                stdout=res.stdout,
                stderr=res.stderr,
                error_message=f"Clang fallback compilation failed: {res.stderr}",
            )
