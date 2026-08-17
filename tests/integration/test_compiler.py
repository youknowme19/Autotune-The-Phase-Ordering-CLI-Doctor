"""
Integration tests compiling C source code and running benchmarks.
"""

import os
import tempfile
import pytest
from autotune.benchmark import get_performance_runner
from autotune.doctor import run_doctor_checks
from autotune.llvm import CompilerDriver, PassSequence
from autotune.sandbox import SandboxExecutor


def test_compiler_driver_baseline_and_candidate():
    doc_report = run_doctor_checks()
    assert doc_report.clang_ok

    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    kernel_path = os.path.abspath("examples/simple_loop/kernel.c")
    workload_path = os.path.abspath("examples/simple_loop/input.txt")

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "base_O3.bin")
        cand_bin = os.path.join(tmpdir, "cand.bin")

        res_base = compiler.compile_baseline(kernel_path, base_bin, opt_level="-O3")
        assert res_base.success
        assert os.path.exists(base_bin)

        seq = PassSequence(passes=["mem2reg", "gvn"])
        res_cand = compiler.compile_candidate(kernel_path, seq, cand_bin)
        assert res_cand.success
        assert os.path.exists(cand_bin)

        executor = SandboxExecutor()
        exec_base = executor.execute(base_bin, workload_path=workload_path)
        assert exec_base.success
        assert "Result:" in exec_base.stdout

        exec_cand = executor.execute(cand_bin, workload_path=workload_path)
        assert exec_cand.success
        assert exec_cand.stdout == exec_base.stdout
