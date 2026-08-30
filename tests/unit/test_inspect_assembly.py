"""
Unit tests for InspectService, assembly analysis, and C++ compiler detection.
"""

import os
import pytest

from autotune.llvm.compiler import CompilerDriver
from autotune.services.inspect import InspectService


def test_compiler_driver_cpp_detection():
    driver = CompilerDriver()
    c_bin = driver.get_compiler_for_source("kernel.c")
    cpp_bin = driver.get_compiler_for_source("kernel.cpp")
    cc_bin = driver.get_compiler_for_source("kernel.cc")

    assert "clang" in c_bin.lower()
    assert "clang++" in cpp_bin.lower() or "clang" in cpp_bin.lower()
    assert "clang++" in cc_bin.lower() or "clang" in cc_bin.lower()


def test_assembly_analysis_parsing():
    sample_asm = """
    .section __TEXT,__text,regular,pure_instructions
    _main:
        pushq %rbp
        movq %rsp, %rbp
        vaddps %xmm0, %xmm1, %xmm2
        fadd.4s v0.4s, v1.4s, v2.4s
        b.ne LBB0_2
        jmp LBB0_3
    LBB0_2:
        retq
    LBB0_3:
        retq
    """
    metrics = CompilerDriver.analyze_assembly(sample_asm)
    assert metrics.total_instructions > 0
    assert metrics.vector_instructions >= 2
    assert metrics.branch_instructions >= 2
    assert metrics.function_count >= 1


def test_inspect_service_workload():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    res = InspectService.inspect_workload(
        source="examples/matrix_transpose/kernel.c",
        pass_sequence_str="mem2reg,instcombine",
    )
    assert res.source_path == "examples/matrix_transpose/kernel.c"
    assert len(res.pass_sequence) == 2
    assert res.baseline_assembly_metrics.total_instructions > 0
    assert res.candidate_assembly_metrics.total_instructions > 0
