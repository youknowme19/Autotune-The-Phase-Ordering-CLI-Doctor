"""
Unit tests for ExplainService (Phase 4).
"""

import json
import os
import tempfile
import pytest
from autotune.services.explain import ExplainService


def test_explain_report_structure():
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = os.path.join(tmpdir, "test_report.json")
        sample_report = {
            "source_path": "examples/matrix_transpose/kernel.c",
            "confirmed_speedup": 1.30,
            "prescription": {
                "speedup_ratio": 1.30,
                "baseline_time_ms": 37.0,
                "candidate_time_ms": 28.5,
                "pass_sequence": {"passes": ["sccp", "gvn", "mem2reg", "lower-atomic"]},
            },
            "evidence_score": {
                "grade": "A",
                "correctness_pass": True,
                "p_value": 0.0001,
                "cohens_d_effect_size": 7.11,
                "baseline_median_ms": 37.0,
                "candidate_median_ms": 28.5,
            },
            "assembly": {
                "baseline_instructions": 197,
                "candidate_instructions": 179,
            },
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(sample_report, f)

        exp = ExplainService.explain_report(report_file)
        assert exp.speedup_ratio == 1.30
        assert exp.winning_passes == ["sccp", "gvn", "mem2reg", "lower-atomic"]
        assert len(exp.observed_facts) > 0
        assert len(exp.inferred_mechanics) > 0
        assert len(exp.hypothesized_effects) > 0
        assert "not proof of causality" in exp.disclaimer
