"""
Unit tests for Phase 16: Confirmation alignment & unconfirmed search result rejection tests.
Ensures that an unconfirmed search-phase speedup is never reported as a successful final optimization.
"""

import pytest
from autotune.benchmark.models import ResultClassification
from autotune.llvm.passes import PassSequence
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade
from autotune.reporting.prescription import PrescriptionBuilder


def test_search_speedup_contradicted_by_fresh_confirmation_is_rejected():
    # Search phase saw 1.11x (100ms vs 90ms), but fresh confirmation saw regression (100ms vs 103ms)
    b_conf = [100000000, 100100000, 99900000, 100050000, 99950000]
    c_conf = [103000000, 103100000, 102900000, 103050000, 102950000]

    score = EvidenceEvaluator.evaluate(
        baseline_samples_ns=b_conf,
        candidate_samples_ns=c_conf,
        correctness_pass=True,
        fresh_confirmation=True,
    )

    assert score.speedup_ratio < 1.0
    assert score.grade == EvidenceGrade.GRADE_F

    seq = PassSequence(passes=["mem2reg"])
    prescription = PrescriptionBuilder.build(
        source_path="kernel.c",
        output_binary="opt.bin",
        pass_sequence=seq,
        clang_path="clang",
        opt_path=None,
        baseline_time_ns=100000000.0,
        candidate_time_ns=103000000.0,
        evidence_grade=score.grade.value,
    )

    assert prescription.classification == ResultClassification.REGRESSION
    assert prescription.evidence_grade == "F"
    assert prescription.speedup_ratio < 1.0


def test_confirmed_speedup_1_10x_accepted():
    b_conf = [100000000, 100100000, 99900000, 100050000, 99950000]
    c_conf = [90000000, 90100000, 89900000, 90050000, 89950000]

    score = EvidenceEvaluator.evaluate(
        baseline_samples_ns=b_conf,
        candidate_samples_ns=c_conf,
        correctness_pass=True,
        fresh_confirmation=True,
    )

    assert score.speedup_ratio > 1.05
    assert score.grade in (EvidenceGrade.GRADE_A, EvidenceGrade.GRADE_B)

    seq = PassSequence(passes=["mem2reg"])
    prescription = PrescriptionBuilder.build(
        source_path="kernel.c",
        output_binary="opt.bin",
        pass_sequence=seq,
        clang_path="clang",
        opt_path=None,
        baseline_time_ns=100000000.0,
        candidate_time_ns=90000000.0,
        evidence_grade=score.grade.value,
    )

    assert prescription.classification == ResultClassification.IMPROVED
    assert prescription.evidence_grade in ("A", "B")
