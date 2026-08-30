"""
Unit tests for HistoryManager service.
"""

import os
import tempfile
import pytest

from autotune.services.history import HistoryManager


def test_history_record_and_list(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setattr(HistoryManager, "get_history_dir", lambda: tmpdir)

        entry = HistoryManager.record_run(
            run_id="run_test_123",
            source_path="examples/matrix_transpose/kernel.c",
            source_hash="abcd1234",
            speedup_ratio=1.19,
            evidence_grade="A",
            classification="IMPROVED",
            winning_passes=["mem2reg", "instcombine"],
            report_json_path=os.path.join(tmpdir, "report.json"),
            report_html_path=os.path.join(tmpdir, "report.html"),
        )

        assert entry.id == "run_test_123"
        assert entry.speedup_ratio == 1.19

        history = HistoryManager.list_history()
        assert len(history) == 1
        assert history[0].id == "run_test_123"

        # Filter by source filename
        filtered = HistoryManager.list_history(source_filter="kernel.c")
        assert len(filtered) == 1

        unmatched = HistoryManager.list_history(source_filter="other.c")
        assert len(unmatched) == 0
