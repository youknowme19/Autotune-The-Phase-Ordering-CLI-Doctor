"""
Unit tests for GuardService.
"""

import json
import os
import tempfile
import pytest

from autotune.services.guard import GuardService, GuardExitCode


def test_guard_missing_source_file():
    res = GuardService.check_guard("non_existent_source.c")
    assert res.exit_code == GuardExitCode.INFRASTRUCTURE_ERROR
    assert res.status == "ERROR"


def test_guard_valid_source_without_reference():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    res = GuardService.check_guard(
        source="examples/matrix_transpose/kernel.c",
        threshold=0.20,
        runs=3,
        warmup=1,
    )
    assert res.exit_code == GuardExitCode.PASS
    assert res.correctness_status == "PASS"
    assert res.current_ms > 0.0


def test_guard_regression_detection():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        # Reference with an unrealistically fast time to force regression detection
        report_data = {
            "source_path": os.path.abspath("examples/matrix_transpose/kernel.c"),
            "prescription": {
                "speedup_ratio": 10.0,
                "candidate_time_ms": 0.001,
                "pass_sequence": {"passes": []},
            },
        }
        json.dump(report_data, f)
        report_path = f.name

    try:
        res = GuardService.check_guard(
            source="examples/matrix_transpose/kernel.c",
            reference_report=report_path,
            threshold=0.01,
            runs=3,
            warmup=1,
        )
        assert res.exit_code == GuardExitCode.REGRESSION
        assert res.status == "PERFORMANCE_REGRESSION"
    finally:
        if os.path.exists(report_path):
            os.remove(report_path)
