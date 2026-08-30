"""
Unit tests for full validation strategies abstraction (Phase 1).
"""

import os
import tempfile
import pytest
from autotune.benchmark.correctness import (
    CorrectnessValidator,
    ExactOutputValidator,
    ExitCodeValidator,
    StdoutValidator,
    ChecksumValidator,
    NumericToleranceValidator,
    FileDigestValidator,
    CustomScriptValidator,
    CompositeValidator,
    ValidationVerdict,
)
from autotune.sandbox.executor import SandboxExecutionResult


def make_exec_res(success=True, exit_code=0, stdout="", stderr=""):
    return SandboxExecutionResult(
        success=success,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        execution_time_ns=1000000,
    )


def test_exit_code_validator():
    val = ExitCodeValidator()
    base = make_exec_res(exit_code=0)
    cand_ok = make_exec_res(exit_code=0)
    cand_fail = make_exec_res(exit_code=1)

    assert val.verify(base, cand_ok).is_correct is True
    assert val.verify(base, cand_ok).verdict == ValidationVerdict.CORRECT

    res_fail = val.verify(base, cand_fail)
    assert res_fail.is_correct is False
    assert res_fail.verdict == ValidationVerdict.INCORRECT


def test_exact_output_validator_and_timing_strip():
    val = ExactOutputValidator()
    base = make_exec_res(stdout="Result: 42\n__AUTOTUNE_TIME_NS__:123456\n")
    cand = make_exec_res(stdout="Result: 42\n__AUTOTUNE_TIME_NS__:987654\n")
    cand_diff = make_exec_res(stdout="Result: 99\n")

    assert val.verify(base, cand).is_correct is True
    assert val.verify(base, cand_diff).is_correct is False


def test_checksum_validator_explicit_and_hash():
    val = ChecksumValidator()
    base_chk = make_exec_res(stdout="Compute complete. Checksum: 0xDEADBEEF\n")
    cand_chk = make_exec_res(stdout="Compute complete. Checksum: 0xDEADBEEF\n")
    cand_bad = make_exec_res(stdout="Compute complete. Checksum: 0xBAADF00D\n")

    assert val.verify(base_chk, cand_chk).is_correct is True
    assert val.verify(base_chk, cand_bad).is_correct is False

    # Generic whole-output SHA-256 fallback
    base_plain = make_exec_res(stdout="Data 1 2 3 4\n")
    cand_plain = make_exec_res(stdout="Data 1 2 3 4\n")
    cand_diff = make_exec_res(stdout="Data 1 2 3 5\n")
    assert val.verify(base_plain, cand_plain).is_correct is True
    assert val.verify(base_plain, cand_diff).is_correct is False


def test_numeric_tolerance_validator():
    val = NumericToleranceValidator(epsilon=1e-4)
    base = make_exec_res(stdout="Matrix Check: 1313.284900\n")
    cand_close = make_exec_res(stdout="Matrix Check: 1313.284902\n")
    cand_far = make_exec_res(stdout="Matrix Check: 1313.285500\n")

    assert val.verify(base, cand_close).is_correct is True
    assert val.verify(base, cand_far).is_correct is False


def test_composite_validator():
    v1 = ExitCodeValidator()
    v2 = StdoutValidator()
    comp = CompositeValidator(strategies=[v1, v2])

    base = make_exec_res(exit_code=0, stdout="OK\n")
    cand_ok = make_exec_res(exit_code=0, stdout="OK\n")
    cand_bad_code = make_exec_res(exit_code=1, stdout="OK\n")
    cand_bad_out = make_exec_res(exit_code=0, stdout="FAIL\n")

    assert comp.verify(base, cand_ok).is_correct is True
    assert comp.verify(base, cand_bad_code).is_correct is False
    assert comp.verify(base, cand_bad_out).is_correct is False


def test_custom_script_validator():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
        f.write("#!/bin/sh\n[ \"$1\" = \"$2\" ] && exit 0 || exit 1\n")
        script_path = f.name
    os.chmod(script_path, 0o755)

    try:
        val = CustomScriptValidator(script_path=script_path)
        base = make_exec_res(stdout="match_test")
        cand_ok = make_exec_res(stdout="match_test")
        cand_fail = make_exec_res(stdout="divergent_test")

        assert val.verify(base, cand_ok).is_correct is True
        assert val.verify(base, cand_fail).is_correct is False
    finally:
        if os.path.exists(script_path):
            os.remove(script_path)
