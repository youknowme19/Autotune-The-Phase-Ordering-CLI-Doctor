"""
Unit tests for Final Release Gate: Verifying Grade C vs Grade F semantics, Cohen's d sign direction, and full evidence test matrix.
"""

import json
import pytest
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade


def test_noisy_positive_speedup_receives_grade_c_not_f():
    # 1.19x speedup with high noise (CV > 15%) and non-significant p-value
    base_noisy = [1000000, 1300000, 700000, 1200000, 800000]
    cand_noisy = [800000, 1100000, 600000, 1000000, 700000]

    score = EvidenceEvaluator.evaluate(
        baseline_samples_ns=base_noisy,
        candidate_samples_ns=cand_noisy,
        correctness_pass=True,
        fresh_confirmation=True,
    )
    assert score.speedup_ratio > 1.0
    # Must NOT be Grade F! Must be Grade C due to high noise / non-significant p-value
    assert score.grade == EvidenceGrade.GRADE_C
    assert score.grade != EvidenceGrade.GRADE_F


def test_cohens_d_sign_direction():
    # Faster candidate -> positive Cohen's d
    base_fast = [100000, 101000, 99000, 100500, 99500]
    cand_fast = [50000, 51000, 49000, 50500, 49500]
    score_fast = EvidenceEvaluator.evaluate(baseline_samples_ns=base_fast, candidate_samples_ns=cand_fast)
    assert score_fast.speedup_ratio > 1.0
    assert score_fast.cohens_d_effect_size > 0.0

    # Slower candidate -> negative Cohen's d
    base_slow = [50000, 51000, 49000, 50500, 49500]
    cand_slow = [100000, 101000, 99000, 100500, 99500]
    score_slow = EvidenceEvaluator.evaluate(baseline_samples_ns=base_slow, candidate_samples_ns=cand_slow)
    assert score_slow.speedup_ratio < 1.0
    assert score_slow.cohens_d_effect_size < 0.0
    assert score_slow.grade == EvidenceGrade.GRADE_F


def test_evidence_grade_test_matrix():
    b_stable = [100000, 100100, 99900, 100050, 99950]

    # 1. 0.45x Regression -> Grade F
    c_045 = [220000, 221000, 219000, 220500, 219500]
    assert EvidenceEvaluator.evaluate(b_stable, c_045).grade == EvidenceGrade.GRADE_F

    # 2. 0.97x Minor Regression -> Grade F
    c_097 = [103000, 103100, 102900, 103050, 102950]
    assert EvidenceEvaluator.evaluate(b_stable, c_097).grade == EvidenceGrade.GRADE_F

    # 3. 1.00x Baseline Parity -> Grade D
    c_100 = [100000, 100100, 99900, 100050, 99950]
    assert EvidenceEvaluator.evaluate(b_stable, c_100).grade == EvidenceGrade.GRADE_D

    # 4. 1.01x Baseline Parity -> Grade D
    c_101 = [99000, 99100, 98900, 99050, 98950]
    assert EvidenceEvaluator.evaluate(b_stable, c_101).grade == EvidenceGrade.GRADE_D

    # 5. 1.07x Strong Evidence -> Grade B / A
    c_107 = [93400, 93500, 93300, 93450, 93350]
    score_107 = EvidenceEvaluator.evaluate(b_stable, c_107)
    assert score_107.grade in (EvidenceGrade.GRADE_A, EvidenceGrade.GRADE_B)

    # 6. Correctness Failure -> Grade F
    score_fail = EvidenceEvaluator.evaluate(b_stable, c_107, correctness_pass=False)
    assert score_fail.grade == EvidenceGrade.GRADE_F
