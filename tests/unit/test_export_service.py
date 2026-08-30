"""
Unit tests for ExportService (Phase 6).
"""

import json
import os
import tempfile
import pytest
from autotune.services.export import ExportService


def test_export_formats_and_secret_absence():
    with tempfile.TemporaryDirectory() as tmpdir:
        report_file = os.path.join(tmpdir, "report.json")
        report_data = {
            "source_path": "kernel.c",
            "source_hash": "a1b2c3d4e5f6",
            "run_id": "exp_42",
            "confirmed_speedup": 1.30,
            "prescription": {
                "pass_sequence": {"passes": ["sccp", "gvn", "mem2reg"]},
                "reproducible_clang_command": "clang ...",
            },
            "doctor_report": {
                "clang_path": "/usr/bin/clang",
                "opt_path": "/usr/bin/opt",
                "arch": "arm64",
                "target_triple": "arm64-apple-darwin",
            },
        }

        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(report_data, f)

        # JSON export
        res_json = ExportService.export(report_file, export_format="json")
        assert "exp_42" in res_json.content
        assert "sccp" in res_json.content

        # Shell export
        res_sh = ExportService.export(report_file, export_format="shell")
        assert "#!/usr/bin/env bash" in res_sh.content
        assert "sccp,gvn,mem2reg" in res_sh.content

        # CMake export
        res_cmake = ExportService.export(report_file, export_format="cmake")
        assert "add_autotune_executable" in res_cmake.content
        assert "sccp,gvn,mem2reg" in res_cmake.content

        # Make export
        res_make = ExportService.export(report_file, export_format="make")
        assert "AUTOTUNE_PASSES :=" in res_make.content
        assert "%.opt.bin: %.opt.bc" in res_make.content

        # Secret absence
        for content in [res_json.content, res_sh.content, res_cmake.content, res_make.content]:
            assert "sk-" not in content
            assert "API_KEY" not in content
