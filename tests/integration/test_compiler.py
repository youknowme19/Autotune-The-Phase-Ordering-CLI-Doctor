"""
Integration tests compiling C source code via full 3-step LLVM pipeline.
"""

import os
import tempfile
import pytest
from autotune.doctor import run_doctor_checks
from autotune.llvm import CompilerDriver, PassSequence
from autotune.sandbox import SandboxExecutor


def test_compiler_bitcode_lowering_and_opt_passes():
    doc_report = run_doctor_checks()
    assert doc_report.clang_ok

    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    kernel_path = os.path.abspath("examples/simple_loop/kernel.c")
    workload_path = os.path.abspath("examples/simple_loop/input.txt")

    with tempfile.TemporaryDirectory() as tmpdir:
        raw_bc = os.path.join(tmpdir, "raw.bc")
        opt_bc = os.path.join(tmpdir, "opt.bc")
        cand_bin = os.path.join(tmpdir, "cand.bin")

        # 1. Test bitcode lowering with -disable-O0-optnone
        step1 = compiler.compile_bitcode(kernel_path, raw_bc)
        assert step1.success
        assert os.path.exists(raw_bc)

        # 2. Test opt pass execution if opt is available
        if doc_report.opt_ok:
            seq = PassSequence(passes=["mem2reg", "instcombine"])
            step2 = compiler.run_opt_passes(raw_bc, seq, opt_bc)
            assert step2.success
            assert os.path.exists(opt_bc)
            assert step2.pass_sequence_str == "mem2reg,instcombine"

            # 3. Test native executable emission
            step3 = compiler.emit_executable(opt_bc, cand_bin)
            assert step3.success
            assert os.path.exists(cand_bin)

            executor = SandboxExecutor()
            exec_res = executor.execute(cand_bin, workload_path=workload_path)
            assert exec_res.success
            assert "Result:" in exec_res.stdout


def test_compiler_driver_full_candidate_pipeline():
    doc_report = run_doctor_checks()
    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    kernel_path = os.path.abspath("examples/simple_loop/kernel.c")
    workload_path = os.path.abspath("examples/simple_loop/input.txt")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "base_O3.bin")
        cand_bin = os.path.join(tmpdir, "cand.bin")

        res_base = compiler.compile_baseline(kernel_path, base_bin, opt_level="-O3")
        assert res_base.success
        assert os.path.exists(base_bin)

        seq = PassSequence(passes=["mem2reg", "gvn", "instcombine"])
        res_cand = compiler.compile_candidate(kernel_path, seq, cand_bin)
        assert res_cand.success
        assert os.path.exists(cand_bin)

        executor = SandboxExecutor()
        exec_base = executor.execute(base_bin, workload_path=workload_path)
        assert exec_base.success

        exec_cand = executor.execute(cand_bin, workload_path=workload_path)
        assert exec_cand.success
        assert exec_cand.stdout == exec_base.stdout
