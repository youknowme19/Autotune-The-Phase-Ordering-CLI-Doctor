"""
Unit tests for Phase 6 Experimental Intelligence & Scientific Rigor.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.environment.fingerprint import EnvironmentFingerprinter, EnvironmentFingerprint
from autotune.benchmark.experiment import MeasurementPolicy, ExperimentPlan
from autotune.benchmark.stability import StabilityAnalyzer, StabilityClassification
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade

runner = CliRunner()


def test_environment_fingerprinting():
    fp = EnvironmentFingerprinter.capture()
    assert isinstance(fp, EnvironmentFingerprint)
    assert len(fp.fingerprint_hash) == 16
    assert fp.os_name in ("Darwin", "Linux", "Windows")
    assert fp.autotune_version == "0.2.1"


def test_experiment_plan_interleaved_sequence():
    pol = MeasurementPolicy(confirmation_runs=10, interleave=True, randomize_order=True)
    plan = ExperimentPlan.create_interleaved_plan("exp_test_01", seed=42, policy=pol)

    assert plan.experiment_id == "exp_test_01"
    assert len(plan.trial_sequence) == 20

    base_count = sum(1 for t in plan.trial_sequence if t.candidate_type == "baseline")
    cand_count = sum(1 for t in plan.trial_sequence if t.candidate_type == "candidate")
    assert base_count == 10
    assert cand_count == 10


def test_stability_analyzer_robust_statistics():
    # Stable distribution
    stable_samples = [50000000, 50100000, 49900000, 50050000, 49950000, 50000000]
    rep = StabilityAnalyzer.analyze(stable_samples)

    assert rep.sample_count == 6
    assert rep.classification == StabilityClassification.STABLE
    assert rep.mad_time_ns >= 0.0
    assert rep.iqr_time_ns >= 0.0

    # Noisy distribution
    noisy_samples = [50000000, 80000000, 30000000, 90000000, 40000000]
    rep_noisy = StabilityAnalyzer.analyze(noisy_samples)
    assert rep_noisy.classification in (StabilityClassification.NOISY, StabilityClassification.UNSTABLE)


def test_evidence_evaluator_grading():
    baseline_samples = [100000000, 101000000, 99000000, 100500000, 99500000, 100000000]
    winning_samples =  [70000000,   70500000, 69500000,  70100000, 69900000,  70000000]

    score_a = EvidenceEvaluator.evaluate(
        baseline_samples_ns=baseline_samples,
        candidate_samples_ns=winning_samples,
        correctness_pass=True,
        fresh_confirmation=True,
    )

    assert score_a.grade == EvidenceGrade.GRADE_A
    assert score_a.speedup_ratio == 1.43
    assert score_a.statistically_significant is True
    assert score_a.cohens_d_effect_size > 0.8

    # Failed correctness test gives Grade F
    score_f = EvidenceEvaluator.evaluate(
        baseline_samples_ns=baseline_samples,
        candidate_samples_ns=winning_samples,
        correctness_pass=False,
    )
    assert score_f.grade == EvidenceGrade.GRADE_F


def test_cli_bundle_command(tmp_path):
    report_file = tmp_path / "search_report.json"
    report_data = {
        "source_path": "examples/matrix_transpose/kernel.c",
        "prescription": {
            "pass_sequence": {"passes": ["gvn", "mem2reg"]},
            "reproducible_clang_command": "clang -O0 kernel.c -o opt.bin",
            "baseline_time_ms": 70.45,
            "candidate_time_ms": 55.86,
            "speedup_ratio": 1.26,
            "classification": "IMPROVED"
        }
    }
    report_file.write_text(json.dumps(report_data))

    out_bundle = tmp_path / "bundle_out"
    res = runner.invoke(app, ["bundle", str(report_file), "-b", str(out_bundle)])

    assert res.exit_code == 0
    assert (out_bundle / "environment.json").exists()
    assert (out_bundle / "manifest.json").exists()
    assert (out_bundle / "reproduce.sh").exists()
    assert (out_bundle / "README.md").exists()
