"""
Candidate result cache providing deterministic hashing and caching of evaluation results.
"""

from enum import Enum
import hashlib
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.llvm.passes import PassSequence
from autotune.search.individual import Individual


class CandidateStatus(str, Enum):
    SUCCESSFUL_BENCHMARK = "SUCCESSFUL_BENCHMARK"
    COMPILATION_FAILURE = "COMPILATION_FAILURE"
    COMPILATION_TIMEOUT = "COMPILATION_TIMEOUT"
    CORRECTNESS_FAILURE = "CORRECTNESS_FAILURE"
    RUNTIME_TIMEOUT = "RUNTIME_TIMEOUT"


class CachedCandidateResult(BaseModel):
    candidate_key: str
    status: CandidateStatus
    individual: Individual
    duration_ms: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None


class CandidateCache:
    """Stores and retrieves evaluated candidate results using a deterministic hash key."""

    def __init__(self):
        self._cache: Dict[str, CachedCandidateResult] = {}
        self.hits: int = 0
        self.misses: int = 0

    @staticmethod
    def compute_key(
        source_content: str,
        workload_content: Optional[str],
        clang_version: str,
        opt_version: str,
        target_arch: str,
        pass_sequence: PassSequence,
        compilation_flags: Optional[List[str]] = None,
    ) -> str:
        """Compute deterministic SHA-256 candidate key."""
        hasher = hashlib.sha256()
        hasher.update(source_content.encode("utf-8"))
        if workload_content:
            hasher.update(workload_content.encode("utf-8"))
        hasher.update(clang_version.encode("utf-8"))
        hasher.update(opt_version.encode("utf-8"))
        hasher.update(target_arch.encode("utf-8"))
        hasher.update(pass_sequence.serialize().encode("utf-8"))
        if compilation_flags:
            for flag in sorted(compilation_flags):
                hasher.update(flag.encode("utf-8"))
        return hasher.hexdigest()

    def get(self, key: str) -> Optional[CachedCandidateResult]:
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, key: str, result: CachedCandidateResult) -> None:
        self._cache[key] = result

    def clear(self) -> None:
        self._cache.clear()
        self.hits = 0
        self.misses = 0

    def __len__(self) -> int:
        return len(self._cache)
