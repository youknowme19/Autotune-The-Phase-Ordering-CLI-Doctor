"""
Unit tests for ReproduceService.
"""

import json
import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch

from autotune.services.reproduce import ReproduceService, ReproductionVerdict


def test_reproduce_missing_report_file():
    with pytest.raises(FileNotFoundError):
        ReproduceService.reproduce("non_existent_report.json")


def test_reproduce_with_valid_report():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        report_data = {
            "source_path": os.path.abspath("examples/matrix_transpose/kernel.c"),
            "confirmed_speedup": 1.05,
            "prescription": {
                "speedup_ratio": 1.05,
                "candidate_time_ms": 60.0,
                "baseline_time_ms": 63.0,
                "pass_sequence": {"passes": ["mem2reg", "instcombine", "loop-simplify"]},
                "reproducible_clang_command": "clang -O3 kernel.c",
            },
        }
        json.dump(report_data, f)
        report_path = f.name

    try:
        res = ReproduceService.reproduce(report_path=report_path, tolerance=0.50, runs=3, warmup=1)
        assert res.correctness_status == "PASS"
        assert res.verdict in (
            ReproductionVerdict.REPRODUCED,
            ReproductionVerdict.INCONCLUSIVE,
            ReproductionVerdict.NOT_REPRODUCED,
        )
        assert res.observed_speedup > 0.0
    finally:
        if os.path.exists(report_path):
            os.remove(report_path)
