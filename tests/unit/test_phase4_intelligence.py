"""
Unit tests for Phase 4 Optimization Intelligence & Workload Profiling.
"""

import pytest
from autotune.analysis.profile import WorkloadProfiler, WorkloadProfile
from autotune.doctor.checks import DoctorReport
from autotune.reporting.report import SearchReport


def test_workload_profiler_extraction(tmp_path):
    src_file = tmp_path / "matrix_kernel.c"
    src_file.write_text("""
    #include <stdio.h>
    void compute(double* a, double* b, int n) {
        for (int i = 0; i < n; i++) {
            for (int j = 0; j < n; j++) {
                a[i * n + j] = b[j * n + i] * 2.5;
            }
        }
    }
    """)

    profiler = WorkloadProfiler()
    profile = profiler.profile_file(str(src_file), architecture="arm64", compiler_version="Clang 22.1")

    assert isinstance(profile, WorkloadProfile)
    assert profile.source_filename == "matrix_kernel.c"
    assert profile.loop_count >= 1
    assert profile.float_ops >= 1 or profile.array_accesses >= 1
    assert "mem2reg" in profile.recommended_passes
    assert "loop-rotate" in profile.recommended_passes or "loop-vectorize" in profile.recommended_passes


def test_search_report_with_workload_profile(tmp_path):
    doc_report = DoctorReport(
        clang_ok=True,
        clang_path="clang",
        clang_version="Clang 22.1",
        python_version="3.11",
        python_ok=True,
        arch="arm64",
        os_name="Darwin",
        cpu_info="Apple Silicon",
        measurement_backend="macOS high-precision timing",
    )
    profile = WorkloadProfile(
        source_hash="abcd1234efgh5678",
        source_filename="test.c",
        lines_of_code=20,
        architecture="arm64",
        compiler_version="Clang 22.1",
        loop_count=2,
        max_loop_depth=2,
        function_count=1,
        call_count=0,
        int_ops=5,
        float_ops=2,
        bitwise_ops=0,
        array_accesses=4,
        pointer_derefs=2,
        memory_intensity=0.3,
        compute_intensity=0.35,
        has_arrays_or_pointers=True,
        has_math_lib=False,
        recommended_passes=["mem2reg", "sroa", "loop-vectorize"],
    )

    report = SearchReport(
        source_path="test.c",
        doctor_report=doc_report,
        workload_profile=profile,
        generations_searched=5,
        population_size=10,
    )

    out_file = tmp_path / "report.json"
    report.export_json(str(out_file))

    assert out_file.exists()
    content = out_file.read_text()
    assert "workload_profile" in content
    assert "abcd1234efgh5678" in content
    assert "loop-vectorize" in content
