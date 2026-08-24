"""
Unit tests for Final Scientific Integrity & Anti-Fabrication Pass:
Proves that statistical metrics (CV, p-value, Cohen's d) are dynamically derived from empirical raw timing samples.
"""

import pytest
from autotune.reporting.evidence import EvidenceEvaluator
from autotune.benchmark.stability import StabilityAnalyzer
from autotune.services.optimize import OptimizeService
from autotune.services.validate import ValidateService


def test_anti_fabrication_different_datasets_yield_different_statistics():
    # Dataset A: Stable, strong speedup (100ms vs 50ms, low noise)
    b_a = [100000000, 100100000, 99900000, 100050000, 99950000]
    c_a = [50000000, 50100000, 49900000, 50050000, 49950000]

    # Dataset B: High noise, modest speedup (100ms vs 95ms, wide variance)
    b_b = [100000000, 120000000, 80000000, 110000000, 90000000]
    c_b = [95000000, 115000000, 75000000, 105000000, 85000000]

    score_a = EvidenceEvaluator.evaluate(b_a, c_a)
    score_b = EvidenceEvaluator.evaluate(b_b, c_b)

    stab_a = StabilityAnalyzer.analyze(c_a)
    stab_b = StabilityAnalyzer.analyze(c_b)

    # Prove statistics are NOT identical or hardcoded
    assert score_a.p_value != score_b.p_value
    assert score_a.cohens_d_effect_size != score_b.cohens_d_effect_size
    assert stab_a.cv != stab_b.cv
    assert score_a.grade != score_b.grade


def test_optimize_service_returns_real_empirical_statistics(tmp_path):
    src = tmp_path / "kernel.c"
    src.write_text("int main() { volatile int sum = 0; for(int i=0; i<100; i++) sum += i; return 0; }")

    res = OptimizeService.run(source=str(src), time_budget=5, quiet=True)
    assert isinstance(res.cv_pct, float)
    assert isinstance(res.p_value, float)
    assert isinstance(res.cohens_d, float)
    assert res.cv_pct >= 0.0
    assert 0.0 <= res.p_value <= 1.0
