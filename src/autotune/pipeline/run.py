"""
Unified AutotuneRun Lifecycle Abstraction.
Tracks run creation, state progression, timing breakdowns, and persistent metadata.
"""

import json
import os
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.analysis.profile import WorkloadProfile
from autotune.doctor.checks import DoctorReport
from autotune.reporting.evidence import EvidenceScore


class RunStatus(str, Enum):
    CREATED = "CREATED"
    INITIALIZING = "INITIALIZING"
    PROFILING = "PROFILING"
    BASELINING = "BASELINING"
    SEARCHING = "SEARCHING"
    PROMOTING = "PROMOTING"
    CONFIRMING = "CONFIRMING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AutotuneRun(BaseModel):
    """Unified run lifecycle model encapsulating all search metadata, timings, and evidence."""

    run_id: str
    status: RunStatus = RunStatus.CREATED
    source_path: str
    source_hash: str
    start_time: str = ""
    end_time: str = ""
    elapsed_wall_time_sec: float = 0.0
    compiler_time_sec: float = 0.0
    benchmark_time_sec: float = 0.0
    search_overhead_sec: float = 0.0
    reporting_time_sec: float = 0.0
    workload_profile: Optional[WorkloadProfile] = None
    doctor_report: Optional[DoctorReport] = None
    evidence_score: Optional[EvidenceScore] = None
    winning_pipeline: List[str] = Field(default_factory=list)
    speedup_ratio: float = 1.0

    def start(self) -> None:
        self.status = RunStatus.INITIALIZING
        self.start_time = datetime.now().isoformat()

    def complete(self, speedup: float, winning_passes: List[str]) -> None:
        self.status = RunStatus.COMPLETED
        self.end_time = datetime.now().isoformat()
        self.speedup_ratio = speedup
        self.winning_pipeline = winning_passes

    def save(self, run_dir: str) -> str:
        os.makedirs(run_dir, exist_ok=True)
        file_path = os.path.join(run_dir, f"{self.run_id}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
        return file_path

    @classmethod
    def load(cls, file_path: str) -> "AutotuneRun":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
