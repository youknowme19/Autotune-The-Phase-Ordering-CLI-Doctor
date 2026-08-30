"""
HistoryManager: Experiment history persistence and querying.
Stores and queries historical runs under .autotune/history/.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HistoryEntry(BaseModel):
    id: str
    timestamp: str
    source_path: str
    source_filename: str
    source_hash: str
    speedup_ratio: float
    evidence_grade: str
    classification: str
    winning_passes: List[str] = Field(default_factory=list)
    report_json_path: str
    report_html_path: str


class HistoryManager:
    """Manages lightweight JSON-based history records under .autotune/history/."""

    @staticmethod
    def get_history_dir() -> str:
        h_dir = os.path.join(os.getcwd(), ".autotune", "history")
        os.makedirs(h_dir, exist_ok=True)
        return h_dir

    @classmethod
    def record_run(
        cls,
        run_id: str,
        source_path: str,
        source_hash: str,
        speedup_ratio: float,
        evidence_grade: str,
        classification: str,
        winning_passes: List[str],
        report_json_path: str,
        report_html_path: str,
    ) -> HistoryEntry:
        h_dir = cls.get_history_dir()
        entry = HistoryEntry(
            id=run_id,
            timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
            source_path=os.path.abspath(source_path),
            source_filename=os.path.basename(source_path),
            source_hash=source_hash,
            speedup_ratio=round(speedup_ratio, 2),
            evidence_grade=evidence_grade,
            classification=classification,
            winning_passes=winning_passes,
            report_json_path=os.path.abspath(report_json_path),
            report_html_path=os.path.abspath(report_html_path),
        )
        record_file = os.path.join(h_dir, f"{run_id}.json")
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(entry.model_dump(), f, indent=2)
        return entry

    @classmethod
    def list_history(cls, source_filter: Optional[str] = None) -> List[HistoryEntry]:
        h_dir = cls.get_history_dir()
        if not os.path.exists(h_dir):
            return []

        entries: List[HistoryEntry] = []
        for fn in sorted(os.listdir(h_dir), reverse=True):
            if fn.endswith(".json"):
                fpath = os.path.join(h_dir, fn)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    entry = HistoryEntry(**data)
                    if source_filter:
                        s_name = os.path.basename(source_filter)
                        if s_name != entry.source_filename and source_filter != entry.source_path and source_filter != entry.source_hash:
                            continue
                    entries.append(entry)
                except Exception:
                    continue
        return entries
