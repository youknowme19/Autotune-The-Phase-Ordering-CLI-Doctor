"""
Multi-Fidelity Candidate Evaluation Stage Tracking.
Controls staged allocation of measurement repetitions from cheap screening to fresh confirmation.
"""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class EvaluationStage(str, Enum):
    STAGE_1_SCREENING = "STAGE_1_SCREENING"
    STAGE_2_PROMOTED = "STAGE_2_PROMOTED"
    STAGE_3_CONFIRMATION = "STAGE_3_CONFIRMATION"
    STAGE_4_FINAL_INDEPENDENT = "STAGE_4_FINAL_INDEPENDENT"


class MultiFidelityTracker(BaseModel):
    """Tracks candidates through multi-stage evaluation pipelines."""

    candidates_generated: int = 0
    candidates_compiled: int = 0
    candidates_executed: int = 0
    candidates_rejected: int = 0
    stage_1_screened: int = 0
    stage_2_promoted: int = 0
    stage_3_confirmed: int = 0
    stage_4_final_independent: int = 0

    def record_stage(self, stage: EvaluationStage) -> None:
        if stage == EvaluationStage.STAGE_1_SCREENING:
            self.stage_1_screened += 1
        elif stage == EvaluationStage.STAGE_2_PROMOTED:
            self.stage_2_promoted += 1
        elif stage == EvaluationStage.STAGE_3_CONFIRMATION:
            self.stage_3_confirmed += 1
        elif stage == EvaluationStage.STAGE_4_FINAL_INDEPENDENT:
            self.stage_4_final_independent += 1
