"""
Unit tests for Final Product Overhaul: Search State Machine, Multi-Fidelity Tracker, Checkpointing, Cache management, and CI Gate.
"""

import json
import pytest
from typer.testing import CliRunner

from autotune.cli import app
from autotune.search.state import SearchState, SearchStateMachine
from autotune.search.multifidelity import EvaluationStage, MultiFidelityTracker
from autotune.search.checkpoint import SearchCheckpoint

runner = CliRunner()


def test_search_state_machine_transitions():
    sm = SearchStateMachine(stagnation_threshold=3)
    assert sm.current_state == SearchState.EXPLORING

    # Record non-improvement evaluations until stagnation
    sm.record_evaluation(improved=False)
    sm.record_evaluation(improved=False)
    stagnating = sm.record_evaluation(improved=False)

    assert stagnating is True
    assert len(sm.transitions) >= 1


def test_multifidelity_tracker():
    tracker = MultiFidelityTracker()
    tracker.record_stage(EvaluationStage.STAGE_1_SCREENING)
    tracker.record_stage(EvaluationStage.STAGE_2_PROMOTED)
    tracker.record_stage(EvaluationStage.STAGE_3_CONFIRMATION)

    assert tracker.stage_1_screened == 1
    assert tracker.stage_2_promoted == 1
    assert tracker.stage_3_confirmed == 1


def test_search_checkpoint_persistence(tmp_path):
    ckpt_file = tmp_path / "search.state"
    ckpt = SearchCheckpoint(
        checkpoint_id="chk123",
        generation=5,
        evaluations_count=45,
        best_pass_sequence=["mem2reg", "sroa", "gvn"],
        best_speedup=1.24,
        seed=42,
        source_path="kernel.c",
        source_hash="abcd1234efgh",
    )
    ckpt.save(str(ckpt_file))

    loaded = SearchCheckpoint.load(str(ckpt_file))
    assert loaded.checkpoint_id == "chk123"
    assert loaded.best_speedup == 1.24
    assert loaded.best_pass_sequence == ["mem2reg", "sroa", "gvn"]


def test_cli_cache_and_gate_commands(tmp_path):
    # Test cache status
    res_cache = runner.invoke(app, ["cache", "status"])
    assert res_cache.exit_code == 0

    # Test CI gate passing report
    report_pass = tmp_path / "report_pass.json"
    report_pass.write_text(json.dumps({
        "prescription": {"speedup_ratio": 1.15, "classification": "IMPROVED"}
    }))
    res_gate_pass = runner.invoke(app, ["gate", str(report_pass), "-m", "1.05"])
    assert res_gate_pass.exit_code == 0

    # Test CI gate failing report
    report_fail = tmp_path / "report_fail.json"
    report_fail.write_text(json.dumps({
        "prescription": {"speedup_ratio": 1.01, "classification": "NO_SIGNIFICANT_CHANGE"}
    }))
    res_gate_fail = runner.invoke(app, ["gate", str(report_fail), "-m", "1.05"])
    assert res_gate_fail.exit_code == 1
