"""
Resumable Search Checkpointing Engine.
Saves and restores search state, RNG seeds, populations, and budget progress.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class SearchCheckpoint(BaseModel):
    """Serializable snapshot of genetic search state for interruption recovery."""

    checkpoint_id: str
    generation: int
    evaluations_count: int
    best_pass_sequence: List[str]
    best_speedup: float
    seed: int
    source_path: str
    source_hash: str
    timestamp: str = ""

    def save(self, file_path: str) -> None:
        self.timestamp = datetime.now().isoformat()
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))

    @classmethod
    def load(cls, file_path: str) -> "SearchCheckpoint":
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Search checkpoint file '{file_path}' not found.")
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
