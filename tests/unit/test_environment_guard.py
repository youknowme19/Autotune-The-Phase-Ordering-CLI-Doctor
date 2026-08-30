"""
Unit tests for Environment-Aware Performance Guard (Phase 2).
"""

import json
import os
import tempfile
import pytest
from autotune.services.guard import GuardService, GuardExitCode


def test_guard_environment_mismatch_warning():
    src = "examples/matrix_transpose/kernel.c"
    if not os.path.exists(src):
        pytest.skip("matrix_transpose example kernel not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        fake_report = os.path.join(tmpdir, "ref_report.json")
        ref_data = {
            "source_path": src,
            "source_hash": "different_hash_12345",
            "environment": {
                "architecture": "x86_64",
                "llvm_version": "14.0.0",
                "target_triple": "x86_64-unknown-linux-gnu",
            },
            "doctor_report": {
                "arch": "x86_64",
                "llvm_version": "14.0.0",
                "target_triple": "x86_64-unknown-linux-gnu",
            },
            "prescription": {
                "candidate_time_ms": 30.0,
                "pass_sequence": {"passes": ["sccp", "gvn"]},
            },
        }
        with open(fake_report, "w", encoding="utf-8") as f:
            json.dump(ref_data, f)

        # Standard guard run should detect environment warnings
        res = GuardService.check_guard(
            source=src,
            reference_report=fake_report,
            threshold=0.50,
            runs=3,
            warmup=1,
            strict_env=False,
        )

        assert len(res.environment_warnings) > 0

        # Strict guard run should reject on environment mismatch
        res_strict = GuardService.check_guard(
            source=src,
            reference_report=fake_report,
            threshold=0.50,
            runs=3,
            warmup=1,
            strict_env=True,
        )
        assert res_strict.exit_code == GuardExitCode.INFRASTRUCTURE_ERROR
        assert res_strict.status == "ENVIRONMENT_MISMATCH"
