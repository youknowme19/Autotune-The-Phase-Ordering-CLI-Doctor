"""
Unit tests for ProfileService workload AST analysis (Phase 3).
"""

import os
import pytest
from autotune.services.profile import ProfileService


def test_profile_matrix_transpose():
    src = "examples/matrix_transpose/kernel.c"
    if not os.path.exists(src):
        pytest.skip("matrix_transpose example kernel not found")

    prof = ProfileService.profile_workload(src)
    assert prof.language == "C"
    assert prof.source_filename == "kernel.c"
    assert prof.function_count >= 1
    assert prof.loop_count >= 1
    assert prof.lines_of_code > 0
    assert prof.loop_intensity in ("HIGH", "MEDIUM", "LOW")
    assert len(prof.potential_optimization_areas) > 0


def test_profile_cpp_classification(tmp_path):
    cpp_file = tmp_path / "workload.cpp"
    cpp_file.write_text("""
    #include <vector>
    #include <numeric>
    extern "C" double compute(int n) {
        std::vector<double> v(n, 1.0);
        return std::accumulate(v.begin(), v.end(), 0.0);
    }
    """)

    prof = ProfileService.profile_workload(str(cpp_file))
    assert prof.language == "C++"
    assert prof.source_filename == "workload.cpp"
