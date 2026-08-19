"""
Persistent content-addressed multi-layer cache architecture with atomic storage for Autotune.

Separate cache keys:
1. Compilation identity: SHA256(source_hash + canonical_pipeline + compiler_identity + compiler_version + opt_version + target_arch + OS + compilation_flags + schema_version)
2. Correctness identity: SHA256(compilation_key + correctness_strategy_name + workload_hash)
3. Performance identity: SHA256(compilation_key + workload_hash + measurement_backend + warmup_runs + repetitions)
"""

import hashlib
import json
import os
import shutil
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

CACHE_SCHEMA_VERSION = 1


class CacheMetrics(BaseModel):
    duplicate_proposals_suppressed: int = 0
    in_memory_memoization_hits: int = 0
    persistent_compilation_cache_hits: int = 0
    persistent_correctness_cache_hits: int = 0
    persistent_fitness_cache_hits: int = 0
    persistent_performance_cache_hits: int = 0
    actual_compilations: int = 0
    actual_benchmark_executions: int = 0
    cache_corruption_recovered: bool = False

    @property
    def persistent_cache_hits(self) -> int:
        return (
            self.persistent_compilation_cache_hits
            + self.persistent_correctness_cache_hits
            + self.persistent_fitness_cache_hits
            + self.persistent_performance_cache_hits
        )

    @property
    def persistent_cache_misses(self) -> int:
        return max(self.actual_compilations, self.actual_benchmark_executions)


class PersistentCacheManager:
    """Manages persistent immutable content-addressed multi-layer cache under .autotune/cache/."""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        enabled: bool = True,
        fresh_all: bool = False,
        fresh_benchmark: bool = False,
    ):
        self.cache_dir = os.path.abspath(cache_dir or os.path.join(os.getcwd(), ".autotune", "cache"))
        self.enabled = enabled
        self.fresh_all = fresh_all
        self.fresh_benchmark = fresh_benchmark

        self.compilation_dir = os.path.join(self.cache_dir, "compilation")
        self.correctness_dir = os.path.join(self.cache_dir, "correctness")
        self.performance_dir = os.path.join(self.cache_dir, "performance")
        self.fitness_dir = os.path.join(self.cache_dir, "fitness")
        self.seeds_dir = os.path.join(self.cache_dir, "seeds")

        if self.enabled:
            for d in [
                self.compilation_dir,
                self.correctness_dir,
                self.performance_dir,
                self.fitness_dir,
                self.seeds_dir,
            ]:
                os.makedirs(d, exist_ok=True)

        self.metrics = CacheMetrics()

    @property
    def compilations_avoided(self) -> int:
        return self.metrics.persistent_compilation_cache_hits

    @property
    def correctness_checks_avoided(self) -> int:
        return self.metrics.persistent_correctness_cache_hits

    @property
    def benchmark_runs_avoided(self) -> int:
        return self.metrics.persistent_performance_cache_hits

    @property
    def cache_hits(self) -> int:
        return self.metrics.persistent_cache_hits

    @property
    def cache_misses(self) -> int:
        return self.metrics.persistent_cache_misses

    @property
    def cache_corruption_recovered(self) -> bool:
        return self.metrics.cache_corruption_recovered

    @cache_corruption_recovered.setter
    def cache_corruption_recovered(self, val: bool) -> None:
        self.metrics.cache_corruption_recovered = val


    @staticmethod
    def hash_str(data: str) -> str:
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @staticmethod
    def hash_file(file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _atomic_write_json(self, target_path: str, data: Dict[str, Any]) -> None:
        """Atomic write using temporary file + fsync + os.replace."""
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", dir=target_dir, delete=False, encoding="utf-8") as tf:
            json.dump(data, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_name = tf.name
        os.replace(tmp_name, target_path)

    def _atomic_copy_file(self, src_path: str, target_path: str) -> None:
        """Atomic file copy using tempfile + fsync + os.replace."""
        target_dir = os.path.dirname(target_path)
        os.makedirs(target_dir, exist_ok=True)
        with tempfile.NamedTemporaryFile("wb", dir=target_dir, delete=False) as tf:
            with open(src_path, "rb") as sf:
                while chunk := sf.read(65536):
                    tf.write(chunk)
            tf.flush()
            os.fsync(tf.fileno())
            tmp_name = tf.name
        os.replace(tmp_name, target_path)

    def compute_compilation_key(
        self,
        source_content: str,
        canonical_pipeline: str,
        compiler_path: str,
        compiler_version: str,
        opt_version: str,
        target_arch: str,
        os_name: str,
        compilation_flags: Optional[List[str]] = None,
    ) -> str:
        """Compute compilation key independently from benchmark repetition configuration."""
        parts = [
            self.hash_str(source_content),
            canonical_pipeline.strip(),
            compiler_path.strip(),
            compiler_version.strip(),
            opt_version.strip(),
            target_arch.strip(),
            os_name.strip(),
            str(CACHE_SCHEMA_VERSION),
        ]
        if compilation_flags:
            parts.extend(sorted(compilation_flags))
        return self.hash_str("|".join(parts))

    def compute_correctness_key(
        self,
        compilation_key: str,
        correctness_strategy: str,
        workload_content: Optional[str] = None,
    ) -> str:
        workload_hash = self.hash_str(workload_content) if workload_content else "none"
        parts = [compilation_key, correctness_strategy.strip(), workload_hash]
        return self.hash_str("|".join(parts))

    def compute_performance_key(
        self,
        compilation_key: str,
        workload_content: Optional[str],
        measurement_backend: str,
        warmup_runs: int,
        repetitions: int,
    ) -> str:
        workload_hash = self.hash_str(workload_content) if workload_content else "none"
        parts = [
            compilation_key,
            workload_hash,
            measurement_backend.strip(),
            str(warmup_runs),
            str(repetitions),
        ]
        return self.hash_str("|".join(parts))

    # --- Compilation Cache ---
    def get_compilation(self, comp_key: str) -> Optional[str]:
        if not self.enabled or self.fresh_all:
            return None

        meta_path = os.path.join(self.compilation_dir, f"{comp_key}.json")
        bin_path = os.path.join(self.compilation_dir, f"{comp_key}.bin")

        if not os.path.exists(meta_path) or not os.path.exists(bin_path):
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("schema_version") != CACHE_SCHEMA_VERSION:
                self.metrics.cache_corruption_recovered = True
                self._quarantine(meta_path, bin_path)
                return None

            expected_bin_hash = data.get("binary_hash")
            actual_bin_hash = self.hash_file(bin_path)
            if expected_bin_hash != actual_bin_hash:
                self.metrics.cache_corruption_recovered = True
                self._quarantine(meta_path, bin_path)
                return None

            self.metrics.persistent_compilation_cache_hits += 1
            return bin_path
        except Exception:
            self.metrics.cache_corruption_recovered = True
            self._quarantine(meta_path, bin_path)
            return None

    def put_compilation(self, comp_key: str, src_binary_path: str) -> str:
        if not self.enabled:
            return src_binary_path

        dest_bin = os.path.join(self.compilation_dir, f"{comp_key}.bin")
        dest_meta = os.path.join(self.compilation_dir, f"{comp_key}.json")

        if not os.path.exists(dest_bin):
            self._atomic_copy_file(src_binary_path, dest_bin)
            bin_hash = self.hash_file(dest_bin)
            meta_data = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "cache_key": comp_key,
                "binary_hash": bin_hash,
            }
            self._atomic_write_json(dest_meta, meta_data)

        return dest_bin

    # --- Correctness Cache ---
    def get_correctness(self, corr_key: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or self.fresh_all:
            return None

        meta_path = os.path.join(self.correctness_dir, f"{corr_key}.json")
        if not os.path.exists(meta_path):
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("schema_version") != CACHE_SCHEMA_VERSION:
                self.metrics.cache_corruption_recovered = True
                self._quarantine(meta_path)
                return None

            self.metrics.persistent_correctness_cache_hits += 1
            return data.get("result")
        except Exception:
            self.metrics.cache_corruption_recovered = True
            self._quarantine(meta_path)
            return None

    def put_correctness(self, corr_key: str, result_dict: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        dest_meta = os.path.join(self.correctness_dir, f"{corr_key}.json")
        if not os.path.exists(dest_meta):
            meta_data = {
                "schema_version": CACHE_SCHEMA_VERSION,
                "cache_key": corr_key,
                "result": result_dict,
            }
            self._atomic_write_json(dest_meta, meta_data)

    # --- Performance Cache ---
    def get_performance(self, perf_key: str) -> Optional[Dict[str, Any]]:
        if not self.enabled or self.fresh_all or self.fresh_benchmark:
            return None

        meta_path = os.path.join(self.performance_dir, f"{perf_key}.json")
        if not os.path.exists(meta_path):
            return None

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("schema_version") != CACHE_SCHEMA_VERSION:
                self.metrics.cache_corruption_recovered = True
                self._quarantine(meta_path)
                return None

            self.metrics.persistent_performance_cache_hits += 1
            res = data.get("result")
            if isinstance(res, dict):
                res["is_cached_timing"] = True
            return res
        except Exception:
            self.metrics.cache_corruption_recovered = True
            self._quarantine(meta_path)
            return None

    def put_performance(self, perf_key: str, perf_dict: Dict[str, Any]) -> None:
        if not self.enabled:
            return

        dest_meta = os.path.join(self.performance_dir, f"{perf_key}.json")
        meta_data = {
            "schema_version": CACHE_SCHEMA_VERSION,
            "cache_key": perf_key,
            "result": perf_dict,
        }
        self._atomic_write_json(dest_meta, meta_data)

    def _quarantine(self, *paths: str) -> None:
        for p in paths:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
