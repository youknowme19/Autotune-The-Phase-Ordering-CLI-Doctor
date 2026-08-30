"""
Evidence Scoring Engine and Decision Gate.
Evaluates candidate results against rigor criteria and computes transparent EvidenceGrade (A/B/C/D/F).
"""

from enum import Enum
import math
import statistics
from typing import List, Optional
from pydantic import BaseModel, Field

from autotune.benchmark.stability import StabilityAnalyzer, StabilityClassification


class EvidenceGrade(str, Enum):
    GRADE_A = "A"  # Rigorous confirmed speedup (Fresh, Stable, Low Noise, Significant p < 0.05, Cohen's d >= 0.8)
    GRADE_B = "B"  # Confirmed speedup (Fresh, Significant p < 0.05)
    GRADE_C = "C"  # Marginal speedup or noisy measurement (CV > 0.15)
    GRADE_D = "D"  # Parity or non-significant difference
    GRADE_F = "F"  # Regression, correctness failure, or execution crash


class EvidenceScore(BaseModel):
    """Transparent evidence grade, rigorous statistical metrics, and decision rationale."""

    grade: EvidenceGrade
    correctness_pass: bool
    fresh_confirmation_used: bool
    baseline_stable: bool
    low_noise: bool
    statistically_significant: bool
    cohens_d_effect_size: float
    p_value: float = 1.0
    speedup_ratio: float
    test_used: str = "Welch's two-tailed t-test"
    confidence_interval_95: List[float] = Field(default_factory=list)
    
    # Detailed sample metrics
    baseline_median_ms: float = 0.0
    candidate_median_ms: float = 0.0
    baseline_mean_ms: float = 0.0
    candidate_mean_ms: float = 0.0
    baseline_stddev_ms: float = 0.0
    candidate_stddev_ms: float = 0.0
    baseline_iqr_ms: float = 0.0
    candidate_iqr_ms: float = 0.0
    baseline_min_ms: float = 0.0
    baseline_max_ms: float = 0.0
    candidate_min_ms: float = 0.0
    candidate_max_ms: float = 0.0
    candidate_cv_pct: float = 0.0

    rationale: List[str] = Field(default_factory=list)


class EvidenceEvaluator:
    """Evaluates experimental confirmation samples to compute EvidenceScore."""

    @staticmethod
    def evaluate(
        baseline_samples_ns: List[int],
        candidate_samples_ns: List[int],
        correctness_pass: bool = True,
        fresh_confirmation: bool = True,
    ) -> EvidenceScore:
        rationale: List[str] = []

        if not correctness_pass:
            rationale.append("Correctness validation failed.")
            return EvidenceScore(
                grade=EvidenceGrade.GRADE_F,
                correctness_pass=False,
                fresh_confirmation_used=fresh_confirmation,
                baseline_stable=False,
                low_noise=False,
                statistically_significant=False,
                cohens_d_effect_size=0.0,
                speedup_ratio=0.0,
                rationale=rationale,
            )

        if not baseline_samples_ns or not candidate_samples_ns:
            rationale.append("Missing raw sample measurements.")
            return EvidenceScore(
                grade=EvidenceGrade.GRADE_F,
                correctness_pass=True,
                fresh_confirmation_used=fresh_confirmation,
                baseline_stable=False,
                low_noise=False,
                statistically_significant=False,
                cohens_d_effect_size=0.0,
                speedup_ratio=1.0,
                rationale=rationale,
            )

        b_rep = StabilityAnalyzer.analyze(baseline_samples_ns)
        c_rep = StabilityAnalyzer.analyze(candidate_samples_ns)

        b_med = b_rep.median_time_ns
        c_med = c_rep.median_time_ns

        speedup = round(b_med / c_med, 2) if c_med > 0 else 1.0

        # Calculate Cohen's d effect size
        n1, n2 = len(baseline_samples_ns), len(candidate_samples_ns)
        m1, m2 = b_rep.mean_time_ns, c_rep.mean_time_ns
        s1, s2 = b_rep.stddev_time_ns, c_rep.stddev_time_ns

        s_pooled = math.sqrt(((n1 - 1) * s1**2 + (n2 - 1) * s2**2) / max(n1 + n2 - 2, 1))
        cohens_d = (m1 - m2) / s_pooled if s_pooled > 0 else 0.0

        # Welch's t-test p-value approximation
        se = math.sqrt((s1**2 / n1) + (s2**2 / n2)) if (n1 > 0 and n2 > 0) else 1.0
        t_stat = (m1 - m2) / se if se > 0 else 0.0
        p_val = math.erfc(abs(t_stat) / math.sqrt(2)) if se > 0 else 1.0

        # 95% Confidence Interval for mean difference (in ms)
        diff_mean_ms = (m1 - m2) / 1e6
        se_ms = se / 1e6
        ci_low = round(diff_mean_ms - (1.96 * se_ms), 3)
        ci_high = round(diff_mean_ms + (1.96 * se_ms), 3)

        stat_sig = (p_val < 0.05) and (speedup >= 1.02)
        b_stable = (b_rep.classification == StabilityClassification.STABLE)
        low_noise = (c_rep.cv <= 0.15)

        if fresh_confirmation:
            rationale.append("✓ Independent fresh confirmation measurements used.")

        if b_stable:
            rationale.append("✓ Baseline timing demonstrated high stability.")

        if low_noise:
            rationale.append(f"✓ Low candidate timing noise (CV={round(c_rep.cv*100, 1)}%).")

        if stat_sig:
            rationale.append(f"✓ Statistically significant improvement (p={round(p_val, 4)}).")

        # Determine Evidence Grade with deterministic half-open intervals
        if not correctness_pass or speedup < 0.98:
            grade = EvidenceGrade.GRADE_F
            rationale.append("Grade F: Confirmed performance regression or correctness failure.")
        elif speedup < 1.02:
            grade = EvidenceGrade.GRADE_D
            rationale.append("Grade D: Baseline parity (-O3 equivalence).")
        elif stat_sig and fresh_confirmation and b_stable and low_noise and (cohens_d >= 0.8) and (speedup >= 1.05):
            grade = EvidenceGrade.GRADE_A
            rationale.append("High-confidence Grade A scientific optimization evidence.")
        elif stat_sig and fresh_confirmation and (speedup >= 1.02):
            grade = EvidenceGrade.GRADE_B
            rationale.append("Solid Grade B confirmed speedup evidence.")
        else:
            grade = EvidenceGrade.GRADE_C
            rationale.append("Grade C: Marginal or noisy speedup (insufficient statistical confidence).")

        return EvidenceScore(
            grade=grade,
            correctness_pass=correctness_pass,
            fresh_confirmation_used=fresh_confirmation,
            baseline_stable=b_stable,
            low_noise=low_noise,
            statistically_significant=stat_sig,
            cohens_d_effect_size=round(cohens_d, 2),
            p_value=round(p_val, 4),
            speedup_ratio=speedup,
            test_used="Welch's two-tailed t-test",
            confidence_interval_95=[ci_low, ci_high],
            baseline_median_ms=round(b_med / 1e6, 3),
            candidate_median_ms=round(c_med / 1e6, 3),
            baseline_mean_ms=round(m1 / 1e6, 3),
            candidate_mean_ms=round(m2 / 1e6, 3),
            baseline_stddev_ms=round(s1 / 1e6, 3),
            candidate_stddev_ms=round(s2 / 1e6, 3),
            baseline_iqr_ms=round(b_rep.iqr_time_ns / 1e6, 3),
            candidate_iqr_ms=round(c_rep.iqr_time_ns / 1e6, 3),
            baseline_min_ms=round(b_rep.min_time_ns / 1e6, 3),
            baseline_max_ms=round(b_rep.max_time_ns / 1e6, 3),
            candidate_min_ms=round(c_rep.min_time_ns / 1e6, 3),
            candidate_max_ms=round(c_rep.max_time_ns / 1e6, 3),
            candidate_cv_pct=round(c_rep.cv * 100, 1),
            rationale=rationale,
        )
