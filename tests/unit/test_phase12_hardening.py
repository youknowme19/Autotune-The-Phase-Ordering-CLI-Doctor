"""
Unit tests for Final Hardening Phase: Evidence Grade boundary enforcement, statistical robustness, KnowledgeStore filtering, and HTML XSS escaping.
"""

import pytest
from autotune.benchmark.models import ResultClassification
from autotune.benchmark.stability import StabilityAnalyzer, StabilityClassification
from autotune.llvm.passes import PassSequence
from autotune.reporting.evidence import EvidenceEvaluator, EvidenceGrade
from autotune.reporting.prescription import PrescriptionBuilder
from autotune.reporting.html import HTMLReportGenerator
from autotune.knowledge.store import KnowledgeStore
from autotune.analysis.profile import WorkloadProfile


def test_prescription_builder_boundary_conditions():
    seq = PassSequence(passes=["mem2reg"])

    # 1. Massive Regression (0.39x) -> REGRESSION, Grade F
    p_reg = PrescriptionBuilder.build(
        source_path="matrix.c", output_binary="opt.bin", pass_sequence=seq,
        clang_path="clang", opt_path=None, baseline_time_ns=1000000.0, candidate_time_ns=2500000.0
    )
    assert p_reg.classification == ResultClassification.REGRESSION
    assert p_reg.evidence_grade == "F"
    assert p_reg.speedup_ratio < 1.0

    # 2. Minor Regression (0.97x) -> REGRESSION, Grade F
    p_minor = PrescriptionBuilder.build(
        source_path="loop.c", output_binary="opt.bin", pass_sequence=seq,
        clang_path="clang", opt_path=None, baseline_time_ns=1000000.0, candidate_time_ns=1030000.0
    )
    assert p_minor.classification == ResultClassification.REGRESSION
    assert p_minor.evidence_grade == "F"

    # 3. Parity (1.00x) -> NO_SIGNIFICANT_CHANGE (TIE), Grade D
    p_par = PrescriptionBuilder.build(
        source_path="kernel.c", output_binary="opt.bin", pass_sequence=seq,
        clang_path="clang", opt_path=None, baseline_time_ns=1000000.0, candidate_time_ns=1000000.0
    )
    assert p_par.classification == ResultClassification.TIE
    assert p_par.evidence_grade == "D"

    # 4. Moderate Improvement (1.03x) -> IMPROVED, Grade B
    p_mod = PrescriptionBuilder.build(
        source_path="stencil.c", output_binary="opt.bin", pass_sequence=seq,
        clang_path="clang", opt_path=None, baseline_time_ns=1030000.0, candidate_time_ns=1000000.0
    )
    assert p_mod.classification == ResultClassification.IMPROVED
    assert p_mod.evidence_grade == "B"

    # 5. Strong Improvement (1.12x) -> IMPROVED, Grade A
    p_strong = PrescriptionBuilder.build(
        source_path="vector.c", output_binary="opt.bin", pass_sequence=seq,
        clang_path="clang", opt_path=None, baseline_time_ns=1120000.0, candidate_time_ns=1000000.0
    )
    assert p_strong.classification == ResultClassification.IMPROVED
    assert p_strong.evidence_grade == "A"


def test_evidence_evaluator_correctness_failure():
    score = EvidenceEvaluator.evaluate(
        baseline_samples_ns=[1000, 1000, 1000],
        candidate_samples_ns=[500, 500, 500],
        correctness_pass=False
    )
    assert score.grade == EvidenceGrade.GRADE_F
    assert score.correctness_pass is False


def test_stability_analyzer_edge_cases():
    # N < 3 samples
    report_short = StabilityAnalyzer.analyze([100, 100])
    assert report_short.classification == StabilityClassification.INCONCLUSIVE

    # Zero variance (identical timings)
    report_zero = StabilityAnalyzer.analyze([500, 500, 500, 500, 500])
    assert report_zero.stddev_time_ns == 0.0
    assert report_zero.classification == StabilityClassification.STABLE


def test_knowledge_store_filters_untrustworthy_grades(tmp_path):
    db_file = tmp_path / "test_k.db"
    k_store = KnowledgeStore(db_path=str(db_file))
    prof = WorkloadProfile(
        source_hash="hash123",
        source_filename="test.c",
        lines_of_code=20,
        architecture="arm64",
        compiler_version="Clang 22",
        loop_count=1,
        max_loop_depth=1,
        function_count=1,
        call_count=0,
        int_ops=10,
        float_ops=0,
        bitwise_ops=0,
        array_accesses=2,
        pointer_derefs=0,
        memory_intensity=0.2,
        compute_intensity=0.8,
        has_arrays_or_pointers=True,
        has_math_lib=False,
    )

    # Should reject Grade F
    k_store.save_knowledge(profile=prof, winning_pipeline=["mem2reg"], speedup_ratio=0.95, evidence_grade="F")
    assert len(k_store.list_records()) == 0

    # Should reject Grade D
    k_store.save_knowledge(profile=prof, winning_pipeline=["mem2reg"], speedup_ratio=1.00, evidence_grade="D")
    assert len(k_store.list_records()) == 0

    # Should accept Grade B
    k_store.save_knowledge(profile=prof, winning_pipeline=["mem2reg"], speedup_ratio=1.08, evidence_grade="B")
    assert len(k_store.list_records()) == 1


def test_html_xss_sanitization():
    payload_data = {
        "source_path": "<script>alert('xss')</script>",
        "prescription": {
            "speedup_ratio": 1.10,
            "classification": "<img src=x onerror=alert(1)>",
            "evidence_grade": "A",
            "pass_sequence": {"passes": ["<svg/onload=alert(1)>"]},
            "reproducible_clang_command": "clang -O3 evil.c"
        }
    }
    html = HTMLReportGenerator.generate_html(payload_data)
    assert "<script>" not in html
    assert "<img src=x" not in html
    assert "<svg/onload" not in html
    assert "&lt;script&gt;" in html
