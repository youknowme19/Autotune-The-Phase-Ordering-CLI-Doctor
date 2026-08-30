"""
Security audit test: Ensures API keys are NEVER written to reports, manifests, or HTML files.
"""

import json
import os
import tempfile
import pytest

from autotune.services.doctor import DoctorService


def test_zero_api_key_leakage_in_doctor_artifacts(monkeypatch):
    if not os.path.exists("examples/matrix_transpose/kernel.c"):
        pytest.skip("Example kernel not present")

    fake_secret = "sk-SUPER-SECRET-API-KEY-123456789"
    monkeypatch.setenv("OPENAI_API_KEY", fake_secret)

    with tempfile.TemporaryDirectory() as tmpdir:
        res = DoctorService.run(
            source="examples/matrix_transpose/kernel.c",
            preset="quick",
            output_dir=tmpdir,
            quiet=True,
        )

        assert os.path.exists(res.report_json_path)
        assert os.path.exists(res.report_html_path)

        with open(res.report_json_path, "r", encoding="utf-8") as f:
            json_text = f.read()

        with open(res.report_html_path, "r", encoding="utf-8") as f:
            html_text = f.read()

        # Strict security assertions: Fake secret must never exist in files
        assert fake_secret not in json_text
        assert fake_secret not in html_text
        assert "SUPER-SECRET" not in json_text
        assert "SUPER-SECRET" not in html_text
