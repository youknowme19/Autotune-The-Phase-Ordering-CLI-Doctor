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


class AssemblyMetrics(BaseModel):
    """Metrics derived from disassembly and assembly analysis."""
    total_instructions: int = 0
    vector_instructions: int = 0
    branch_instructions: int = 0
    function_count: int = 0
    approximate_code_size_bytes: int = 0


class CompilationResult(BaseModel):
    """Structured metadata returned for every compilation attempt."""

    success: bool
    binary_path: Optional[str] = None
    raw_bitcode_path: Optional[str] = None
    optimized_bitcode_path: Optional[str] = None
    assembly_path: Optional[str] = None
    ir_path: Optional[str] = None
    pass_sequence_str: Optional[str] = None
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None


class CompilerDriver:
    """Invokes Clang and Opt to lower C/C++ source to bitcode, apply passes, and emit executables."""

    CPP_EXTENSIONS = {".cpp", ".cc", ".cxx", ".c++", ".C"}

    def __init__(
        self,
        clang_path: Optional[str] = None,
        clangxx_path: Optional[str] = None,
        opt_path: Optional[str] = None,
        target_arch: Optional[str] = None,
    ):
        self.clang_path = find_tool("clang", clang_path) or "clang"
        if clangxx_path:
            self.clangxx_path = clangxx_path
        elif self.clang_path:
            same_dir = os.path.join(os.path.dirname(self.clang_path), "clang++")
            self.clangxx_path = same_dir if (os.path.exists(same_dir) and os.access(same_dir, os.X_OK)) else (find_tool("clang++") or "clang++")
        else:
            self.clangxx_path = find_tool("clang++") or "clang++"

        self.opt_path = find_tool("opt", opt_path)
        self.target_arch = target_arch or platform.machine()
        self.os_name = platform.system()
        self.validator = PassValidator(opt_path=self.opt_path)

        self.clang_version: str = "Clang"
        self.opt_version: str = "Opt"

    def get_compiler_for_source(self, source_path: str) -> str:
        """Automatically select clang for C or clang++ for C++ based on file extension."""
        _, ext = os.path.splitext(source_path)
        if ext in self.CPP_EXTENSIONS:
            return self.clangxx_path
        return self.clang_path

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

        compiler_bin = self.get_compiler_for_source(source_path)

        cmd = [
            compiler_bin,
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
        lto: Optional[str] = None,
    ) -> CompilationResult:
        """Step 3: Compile optimized bitcode into native machine executable with optional LTO."""
        if not os.path.exists(bitcode_path):
            return CompilationResult(
                success=False, error_message=f"Bitcode file not found: {bitcode_path}"
            )

        output_bin = os.path.abspath(output_binary_path)
        os.makedirs(os.path.dirname(output_bin), exist_ok=True)

        cmd = [self.clang_path]
        if platform.system() == "Darwin" and self.target_arch:
            cmd.extend(["-arch", self.target_arch])

        if lto:
            lto_flag = "-flto=thin" if lto.lower() == "thin" else "-flto"
            cmd.append(lto_flag)

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

        compiler_bin = self.get_compiler_for_source(source_path)
        cmd = [compiler_bin, opt_level]
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

    def emit_assembly(
        self,
        source_or_bitcode_path: str,
        output_asm_path: str,
        opt_level: str = "-O3",
        pass_sequence: Optional[PassSequence] = None,
    ) -> CompilationResult:
        """Emit native assembly (.s) from C/C++ source or bitcode."""
        if not os.path.exists(source_or_bitcode_path):
            return CompilationResult(
                success=False, error_message=f"Input file not found: {source_or_bitcode_path}"
            )

        output_asm = os.path.abspath(output_asm_path)
        os.makedirs(os.path.dirname(output_asm), exist_ok=True)

        if pass_sequence and self.opt_path and os.path.exists(self.opt_path):
            # Compile with specific pass sequence
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_bc = os.path.join(tmpdir, "raw.bc")
                opt_bc = os.path.join(tmpdir, "opt.bc")
                bc_res = self.compile_bitcode(source_or_bitcode_path, raw_bc)
                if not bc_res.success:
                    return bc_res
                opt_res = self.run_opt_passes(raw_bc, pass_sequence, opt_bc)
                if not opt_res.success:
                    return opt_res

                cmd = [self.clang_path, "-S", opt_bc, "-o", output_asm]
                if platform.system() == "Darwin" and self.target_arch:
                    cmd.extend(["-arch", self.target_arch])
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if res.returncode == 0 and os.path.exists(output_asm):
                    return CompilationResult(success=True, assembly_path=output_asm, stdout=res.stdout, stderr=res.stderr)
                return CompilationResult(success=False, error_message=f"Assembly emission failed: {res.stderr}")
        else:
            compiler_bin = self.get_compiler_for_source(source_or_bitcode_path)
            cmd = [compiler_bin, "-S", opt_level, os.path.abspath(source_or_bitcode_path), "-o", output_asm]
            if platform.system() == "Darwin" and self.target_arch:
                cmd.extend(["-arch", self.target_arch])
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if res.returncode == 0 and os.path.exists(output_asm):
                return CompilationResult(success=True, assembly_path=output_asm, stdout=res.stdout, stderr=res.stderr)
            return CompilationResult(success=False, error_message=f"Assembly emission failed: {res.stderr}")

    def emit_llvm_ir(
        self,
        source_or_bitcode_path: str,
        output_ir_path: str,
        pass_sequence: Optional[PassSequence] = None,
    ) -> CompilationResult:
        """Emit readable LLVM IR (.ll) from C/C++ source or bitcode."""
        if not os.path.exists(source_or_bitcode_path):
            return CompilationResult(
                success=False, error_message=f"Input file not found: {source_or_bitcode_path}"
            )

        output_ir = os.path.abspath(output_ir_path)
        os.makedirs(os.path.dirname(output_ir), exist_ok=True)

        if pass_sequence and self.opt_path and os.path.exists(self.opt_path):
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_bc = os.path.join(tmpdir, "raw.bc")
                opt_bc = os.path.join(tmpdir, "opt.bc")
                bc_res = self.compile_bitcode(source_or_bitcode_path, raw_bc)
                if not bc_res.success:
                    return bc_res
                opt_res = self.run_opt_passes(raw_bc, pass_sequence, opt_bc)
                if not opt_res.success:
                    return opt_res

                cmd = [self.clang_path, "-S", "-emit-llvm", opt_bc, "-o", output_ir]
                res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
                if res.returncode == 0 and os.path.exists(output_ir):
                    return CompilationResult(success=True, ir_path=output_ir, stdout=res.stdout, stderr=res.stderr)
                return CompilationResult(success=False, error_message=f"IR emission failed: {res.stderr}")
        else:
            compiler_bin = self.get_compiler_for_source(source_or_bitcode_path)
            cmd = [compiler_bin, "-S", "-emit-llvm", "-O3", os.path.abspath(source_or_bitcode_path), "-o", output_ir]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30)
            if res.returncode == 0 and os.path.exists(output_ir):
                return CompilationResult(success=True, ir_path=output_ir, stdout=res.stdout, stderr=res.stderr)
            return CompilationResult(success=False, error_message=f"IR emission failed: {res.stderr}")

    @staticmethod
    def analyze_assembly(asm_path_or_content: str) -> AssemblyMetrics:
        """Analyze assembly code to extract instruction counts, vector instructions, and functions."""
        if os.path.exists(asm_path_or_content):
            with open(asm_path_or_content, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            code_size = os.path.getsize(asm_path_or_content)
        else:
            content = asm_path_or_content
            code_size = len(content.encode("utf-8"))

        total_instr = 0
        vector_instr = 0
        branch_instr = 0
        function_count = 0

        vector_keywords = {
            "vadd", "vmul", "vsub", "vdiv", "vfma", "vmov", "vpadd", "vfmadd",
            "fadd.4s", "fadd.2d", "fmul.4s", "fmul.2d", "fmla", "fmls", "fmla.4s",
            "ldr q", "str q", "ld1", "st1", "mov.16b", "mov.8b", "tbl", "ins",
            "ymm", "zmm", "xmm", "avx", "sse", "neon"
        }
        branch_keywords = {"b.", "bne", "beq", "bgt", "blt", "bge", "ble", "cbz", "cbnz", "tbz", "tbnz", "jmp", "je", "jne", "jg", "jl", "jge", "jle", "call", "bl"}

        for line in content.splitlines():
            line_str = line.strip()
            if not line_str or line_str.startswith("#") or line_str.startswith(";") or line_str.startswith("//"):
                continue
            if line_str.endswith(":") and not line_str.startswith("."):
                function_count += 1
                continue
            if line_str.startswith("."):
                continue  # Assembler directive

            total_instr += 1
            lower_line = line_str.lower()

            if any(vk in lower_line for vk in vector_keywords):
                vector_instr += 1
            if any(lower_line.startswith(bk) or f" {bk} " in lower_line for bk in branch_keywords):
                branch_instr += 1

        return AssemblyMetrics(
            total_instructions=total_instr,
            vector_instructions=vector_instr,
            branch_instructions=branch_instr,
            function_count=max(function_count, 1) if total_instr > 0 else 0,
            approximate_code_size_bytes=code_size,
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
            compiler_bin = self.get_compiler_for_source(source_path)
            cmd = [
                compiler_bin,
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
                error_message=f"Compiler fallback compilation failed: {res.stderr}",
            )
