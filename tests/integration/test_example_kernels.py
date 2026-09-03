"""
Test suite validating that all bundled example kernels compile and execute correctly.
"""

import os
import subprocess
import tempfile
import pytest

from autotune.doctor.checks import run_doctor_checks


@pytest.mark.parametrize("kernel_path", [
    "examples/matrix_transpose/kernel.c",
    "examples/conv2d/kernel.c",
    "examples/gemv/kernel.c",
    "examples/fft/kernel.c",
    "examples/nbody/kernel.c",
    "examples/spmv/kernel.c",
])
def test_example_kernel_compiles_and_runs(kernel_path):
    assert os.path.exists(kernel_path), f"Kernel not found: {kernel_path}"
    doc = run_doctor_checks()
    assert doc.clang_ok, "Clang compiler required"

    with tempfile.TemporaryDirectory() as tmpdir:
        bin_path = os.path.join(tmpdir, "test_bin")
        # Compile with -O3
        compile_cmd = [doc.clang_path, "-O3", "-lm", kernel_path, "-o", bin_path]
        res_c = subprocess.run(compile_cmd, capture_output=True, text=True)
        assert res_c.returncode == 0, f"Compilation failed: {res_c.stderr}"

        # Execute
        res_e = subprocess.run([bin_path], capture_output=True, text=True, timeout=10)
        assert res_e.returncode == 0, f"Execution failed: {res_e.stderr}"
        assert len(res_e.stdout) > 0, "Expected stdout checksum from kernel"
