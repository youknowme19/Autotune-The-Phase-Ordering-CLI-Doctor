"""
Unit tests for Flagship DoctorService and CLI doctor command.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from autotune.llvm.passes import PassSequence
from autotune.services.doctor import DoctorService, PRESETS


def test_doctor_presets_configuration():
    assert "quick" in PRESETS
    assert "balanced" in PRESETS
    assert "aggressive" in PRESETS
    assert PRESETS["quick"].population < PRESETS["aggressive"].population
    assert PRESETS["quick"].generations < PRESETS["aggressive"].generations


def test_doctor_missing_source_file():
    with pytest.raises(FileNotFoundError):
        DoctorService.run(source="non_existent_kernel_file.c")


def test_doctor_explicit_llm_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUNE_LLM_API_KEY", raising=False)
    
    with patch("autotune.config.CredentialStore.get_api_key", return_value=None):
        with pytest.raises(ValueError, match="no API key configured"):
            DoctorService.run(source="examples/matrix_transpose/kernel.c", llm=True)


def test_doctor_offline_mode_execution():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    res = DoctorService.run(
        source="examples/matrix_transpose/kernel.c",
        preset="quick",
        llm=False,
        seed=42,
        quiet=True,
    )

    assert res.source_path == "examples/matrix_transpose/kernel.c"
    assert res.search_mode == "offline"
    assert res.correctness_status == "PASS"
    assert res.confirmed_speedup > 0.0
    assert os.path.exists(res.report_json_path)
    assert os.path.exists(res.report_html_path)


def test_doctor_assembly_analysis_flag():
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    res = DoctorService.run(
        source="examples/matrix_transpose/kernel.c",
        preset="quick",
        include_assembly=True,
        llm=False,
        quiet=True,
    )

    assert res.assembly_metrics is not None
    assert res.assembly_metrics.total_instructions > 0
    assert res.baseline_assembly_path is not None
