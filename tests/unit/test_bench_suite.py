"""
Unit tests for batch stress testing orchestrator, failure mode categorization, and stress_test_report.json aggregation.
"""

import os
import tempfile
import pytest
from autotune.stress.models import FailureCategory, KernelStressResult, StressTestReport
from autotune.stress.orchestrator import BatchStressTestOrchestrator


def test_failure_category_enum():
    assert FailureCategory.COMPILER_CRASH == "COMPILER_CRASH"
    assert FailureCategory.SILENT_MISCOMPILATION == "SILENT_MISCOMPILATION"
    assert FailureCategory.STATISTICAL_REGRESSION == "STATISTICAL_REGRESSION"
    assert FailureCategory.SUCCESSFUL_SPEEDUP == "SUCCESSFUL_SPEEDUP"


def test_stress_test_report_aggregation_and_json():
    res1 = KernelStressResult(
        kernel_name="2mm",
        source_path="polybench/2mm.c",
        category=FailureCategory.SUCCESSFUL_SPEEDUP,
        baseline_time_ms=10.0,
        best_candidate_time_ms=8.0,
        speedup_ratio=1.25,
        p_value=0.01,
        winning_passes=["mem2reg", "sroa", "licm"],
    )

    res2 = KernelStressResult(
        kernel_name="cholesky",
        source_path="polybench/cholesky.c",
        category=FailureCategory.STATISTICAL_REGRESSION,
        baseline_time_ms=5.0,
        best_candidate_time_ms=6.0,
        speedup_ratio=0.83,
        p_value=0.02,
        winning_passes=["mem2reg", "dce"],
    )

    res3 = KernelStressResult(
        kernel_name="atax",
        source_path="polybench/atax.c",
        category=FailureCategory.SILENT_MISCOMPILATION,
        miscompilation_count=2,
    )

    report = StressTestReport(
        timestamp="2026-08-18T22:30:00",
        total_workloads=3,
        successful_speedups=1,
        statistical_regressions=1,
        silent_miscompilations=1,
        overall_suite_speedup=1.04,
        results=[res1, res2, res3],
    )

    assert report.total_workloads == 3
    assert report.successful_speedups == 1
    assert report.statistical_regressions == 1
    assert report.silent_miscompilations == 1

    with tempfile.TemporaryDirectory() as tmpdir:
        json_path = os.path.join(tmpdir, "test_report.json")
        report.export_json(json_path)

        assert os.path.exists(json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "2mm" in content
        assert "SUCCESSFUL_SPEEDUP" in content
        assert "STATISTICAL_REGRESSION" in content
        assert "SILENT_MISCOMPILATION" in content


def test_batch_orchestrator_initialization():
    orchestrator = BatchStressTestOrchestrator(
        population_size=10,
        generations=5,
        seed=42,
        max_workers=2,
    )
    assert orchestrator.population_size == 10
    assert orchestrator.generations == 5
    assert orchestrator.seed == 42
    assert orchestrator.max_workers == 2
