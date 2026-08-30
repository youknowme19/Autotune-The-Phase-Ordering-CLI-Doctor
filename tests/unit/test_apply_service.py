"""
Unit tests for ApplyService (Phase 5).
"""

import json
import os
import tempfile
import pytest
from autotune.services.apply import ApplyService


def test_apply_report_generates_artifacts():
    src = "examples/matrix_transpose/kernel.c"
    if not os.path.exists(src):
        pytest.skip("matrix_transpose example kernel not found")

    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = os.path.join(tmpdir, "report.json")
        out_dir = os.path.join(tmpdir, "artifacts")

        report_data = {
            "source_path": os.path.abspath(src),
            "run_id": "test_run_123",
            "prescription": {
                "pass_sequence": {"passes": ["sccp", "gvn", "mem2reg", "lower-atomic", "mem2reg"]},
                "reproducible_clang_command": "clang ...",
            },
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f)

        res = ApplyService.apply_report(report_file, output_dir=out_dir)
        assert res.success is True
        assert os.path.exists(res.raw_ir_path)
        assert os.path.exists(res.optimized_ir_path)
        assert os.path.exists(res.assembly_path)
        assert os.path.exists(res.binary_path)
        assert os.path.exists(res.manifest_path)

        # Ensure source code was not modified
        with open(src, "r") as f:
            content = f.read()
            assert "Matrix Transpose" in content
