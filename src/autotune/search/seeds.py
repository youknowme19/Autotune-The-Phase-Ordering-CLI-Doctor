"""
Seed Archive Manager for storing and loading cross-workload LLVM optimization pipelines.
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

SEED_SCHEMA_VERSION = 1


class SeedRecord(BaseModel):
    schema_version: int = SEED_SCHEMA_VERSION
    pipeline: List[str]
    source_workload_id: str
    compiler_id: str
    llvm_version: str
    architecture: str
    target_info: str
    observed_normalized_speed: float
    correctness_status: str
    confirmation_status: str
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class SeedArchiveManager:
    """Manages persistent seed archive under .autotune/cache/seeds/."""

    def __init__(self, seeds_dir: Optional[str] = None):
        self.seeds_dir = os.path.abspath(
            seeds_dir or os.path.join(os.getcwd(), ".autotune", "cache", "seeds")
        )
        os.makedirs(self.seeds_dir, exist_ok=True)

    def save_seed(
        self,
        pipeline: List[str],
        source_workload_id: str,
        compiler_id: str,
        llvm_version: str,
        architecture: str,
        target_info: str,
        observed_normalized_speed: float,
        correctness_status: str = "PASS",
        confirmation_status: str = "CONFIRMED",
    ) -> None:
        if not pipeline or observed_normalized_speed <= 1.0 or correctness_status != "PASS":
            return

        pipe_str = ",".join(pipeline)
        seed_id = f"seed_{hash(pipe_str) & 0xffffffff:08x}"
        filepath = os.path.join(self.seeds_dir, f"{seed_id}.json")

        record = SeedRecord(
            pipeline=pipeline,
            source_workload_id=source_workload_id,
            compiler_id=compiler_id,
            llvm_version=llvm_version,
            architecture=architecture,
            target_info=target_info,
            observed_normalized_speed=observed_normalized_speed,
            correctness_status=correctness_status,
            confirmation_status=confirmation_status,
        )

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record.model_dump(), f, indent=2)

    def load_valid_seeds(
        self,
        target_architecture: str,
        compiler_id: str,
    ) -> List[List[str]]:
        seeds = []
        if not os.path.exists(self.seeds_dir):
            return seeds

        for fname in os.listdir(self.seeds_dir):
            if fname.endswith(".json"):
                path = os.path.join(self.seeds_dir, fname)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if (
                        data.get("schema_version") == SEED_SCHEMA_VERSION
                        and data.get("architecture") == target_architecture
                        and data.get("correctness_status") == "PASS"
                    ):
                        seeds.append(data.get("pipeline", []))
                except Exception:
                    pass
        return seeds

    @staticmethod
    def get_target_microarch_bias(target_cpu: Optional[str] = None) -> List[List[str]]:
        """Returns microarchitecture-tailored seed pipelines for specific hardware targets."""
        cpu = (target_cpu or "").lower()
        if "apple" in cpu or "m1" in cpu or "m2" in cpu or "m3" in cpu or "arm" in cpu or "darwin" in cpu:
            # Apple Silicon / ARM64 NEON & SIMD pipelining
            return [
                ["mem2reg", "sroa", "loop-rotate", "licm", "loop-unroll", "loop-vectorize", "slp-vectorizer", "instcombine", "early-cse", "gvn", "dce"],
                ["mem2reg", "sroa", "loop-rotate", "licm", "loop-vectorize", "slp-vectorizer", "instcombine"],
                ["mem2reg", "sroa", "loop-flatten", "loop-rotate", "licm", "loop-unroll", "loop-vectorize", "aggressive-instcombine"],
                ["sccp", "gvn", "mem2reg", "lower-atomic", "loop-unroll", "instcombine"],
            ]
        elif "znver" in cpu or "amd" in cpu or "avx2" in cpu or "x86" in cpu:
            # x86-64 AVX2 / AVX-512 vector pipelines
            return [
                ["mem2reg", "sroa", "loop-rotate", "licm", "loop-unroll", "loop-vectorize", "slp-vectorizer", "instcombine", "early-cse", "gvn"],
                ["mem2reg", "early-cse", "reassociate", "loop-vectorize", "instcombine", "dce"],
                ["sroa", "gvn", "loop-rotate", "licm", "loop-unroll", "instcombine", "aggressive-instcombine"],
            ]
        return [
            ["mem2reg", "sroa", "loop-rotate", "licm", "loop-unroll", "loop-vectorize", "slp-vectorizer", "instcombine"],
            ["mem2reg", "instcombine", "loop-rotate", "loop-vectorize", "simplifycfg"],
        ]

