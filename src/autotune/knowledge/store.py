"""
Local Knowledge Store for cross-run optimization memory and workload profile similarity matching.
Uses zero-dependency local SQLite database under .autotune/knowledge.db.
"""

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autotune.analysis.profile import WorkloadProfile


class KnowledgeRecord(BaseModel):
    id: Optional[int] = None
    source_hash: str
    source_filename: str
    architecture: str
    compiler_version: str
    winning_pipeline: List[str]
    speedup_ratio: float
    classification: str
    loop_count: int
    float_ops: int
    memory_intensity: float
    timestamp: str = ""


class KnowledgeStore:
    """Manages persistent SQLite optimization memory under .autotune/knowledge.db."""

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = os.path.abspath(
            db_path or os.path.join(os.getcwd(), ".autotune", "knowledge.db")
        )
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_hash TEXT NOT NULL,
                    source_filename TEXT NOT NULL,
                    architecture TEXT NOT NULL,
                    compiler_version TEXT NOT NULL,
                    winning_pipeline TEXT NOT NULL,
                    speedup_ratio REAL NOT NULL,
                    classification TEXT NOT NULL,
                    loop_count INTEGER NOT NULL,
                    float_ops INTEGER NOT NULL,
                    memory_intensity REAL NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.commit()

    def save_knowledge(
        self,
        profile: WorkloadProfile,
        winning_pipeline: List[str],
        speedup_ratio: float,
        classification: str = "IMPROVED",
    ) -> None:
        if not winning_pipeline or speedup_ratio <= 1.0:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO knowledge_records (
                    source_hash, source_filename, architecture, compiler_version,
                    winning_pipeline, speedup_ratio, classification,
                    loop_count, float_ops, memory_intensity, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.source_hash,
                    profile.source_filename,
                    profile.architecture,
                    profile.compiler_version,
                    json.dumps(winning_pipeline),
                    speedup_ratio,
                    classification,
                    profile.loop_count,
                    profile.float_ops,
                    profile.memory_intensity,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    def find_similar_workloads(
        self, profile: WorkloadProfile, limit: int = 3
    ) -> List[List[str]]:
        """Find historical pipelines from structurally similar workloads using profile feature distance."""
        records: List[KnowledgeRecord] = self.list_records()
        if not records:
            return []

        scored_pipelines = []
        for r in records:
            if r.architecture != profile.architecture:
                continue
            # Calculate profile distance
            d_loop = abs(r.loop_count - profile.loop_count) / 10.0
            d_float = abs(r.float_ops - profile.float_ops) / 20.0
            d_mem = abs(r.memory_intensity - profile.memory_intensity)
            dist = d_loop + d_float + d_mem

            scored_pipelines.append((dist, r.winning_pipeline))

        scored_pipelines.sort(key=lambda x: x[0])
        return [pipe for _, pipe in scored_pipelines[:limit]]

    def list_records(self) -> List[KnowledgeRecord]:
        records = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT id, source_hash, source_filename, architecture, compiler_version, winning_pipeline, speedup_ratio, classification, loop_count, float_ops, memory_intensity, timestamp FROM knowledge_records ORDER BY id DESC"
            )
            for row in cursor.fetchall():
                records.append(
                    KnowledgeRecord(
                        id=row[0],
                        source_hash=row[1],
                        source_filename=row[2],
                        architecture=row[3],
                        compiler_version=row[4],
                        winning_pipeline=json.loads(row[5]),
                        speedup_ratio=row[6],
                        classification=row[7],
                        loop_count=row[8],
                        float_ops=row[9],
                        memory_intensity=row[10],
                        timestamp=row[11],
                    )
                )
        return records
