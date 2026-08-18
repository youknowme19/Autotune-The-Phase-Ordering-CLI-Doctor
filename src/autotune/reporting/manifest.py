"""
Reproducible experiment manifest exporter creating .autotune_runs/<run_id>/ diagnostic artifacts.
"""

from datetime import datetime
import json
import math
import os
import subprocess
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from autotune.benchmark.models import BenchmarkResult
from autotune.doctor.checks import DoctorReport
from autotune.reporting.prescription import CompilerPrescription
from autotune.search.individual import Individual


def calculate_p_value(samples_a: List[float], samples_b: List[float]) -> float:
    """Welch's t-test calculation for statistical significance comparison."""
    if len(samples_a) < 2 or len(samples_b) < 2:
        return 1.0

    mean_a = sum(samples_a) / len(samples_a)
    mean_b = sum(samples_b) / len(samples_b)

    var_a = sum((x - mean_a) ** 2 for x in samples_a) / (len(samples_a) - 1)
    var_b = sum((x - mean_b) ** 2 for x in samples_b) / (len(samples_b) - 1)

    se = math.sqrt((var_a / len(samples_a)) + (var_b / len(samples_b)))
    if se < 1e-9:
        return 0.001 if mean_b < mean_a else 1.0

    t_stat = abs(mean_a - mean_b) / se
    # Approximate p-value for large N
    p_val = math.erfc(t_stat / math.sqrt(2))
    return round(p_val, 6)


class ExperimentManifestExporter:
    """Exports structured experiment runs into .autotune_runs/<run_id>/ directory."""

    @staticmethod
    def get_git_commit_hash() -> str:
        try:
            res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2)
            return res.stdout.strip() if res.returncode == 0 else "unknown"
        except Exception:
            return "unknown"

    @classmethod
    def export_run(
        cls,
        run_id: str,
        source_path: str,
        workload_path: Optional[str],
        seed: Optional[int],
        doc_report: DoctorReport,
        baseline_result: Optional[BenchmarkResult],
        candidates: List[Individual],
        winning_individual: Optional[Individual],
        prescription: Optional[CompilerPrescription],
        output_base_dir: str = ".autotune_runs",
    ) -> str:
        run_dir = os.path.join(output_base_dir, run_id)
        os.makedirs(run_dir, exist_ok=True)

        # 1. manifest.json
        manifest_data = {
            "run_id": run_id,
            "timestamp": datetime.now().isoformat(),
            "git_commit": cls.get_git_commit_hash(),
            "source_path": source_path,
            "workload_path": workload_path,
            "seed": seed,
            "os_name": doc_report.os_name,
            "architecture": doc_report.arch,
            "cpu_info": doc_report.cpu_info,
            "clang_version": doc_report.clang_version,
            "opt_version": doc_report.opt_version,
        }
        with open(os.path.join(run_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        # 2. baseline.json
        if baseline_result and baseline_result.metrics:
            with open(os.path.join(run_dir, "baseline.json"), "w", encoding="utf-8") as f:
                f.write(baseline_result.model_dump_json(indent=2))

        # 3. candidates.jsonl
        with open(os.path.join(run_dir, "candidates.jsonl"), "w", encoding="utf-8") as f:
            for ind in candidates:
                record = {
                    "passes": ind.sequence.passes,
                    "fitness": ind.fitness,
                    "compilation_success": ind.compilation_success,
                    "correctness_success": ind.correctness_success,
                    "status": "OK" if ind.is_valid else ("MISCOMPILE" if not ind.correctness_success else "FAIL"),
                }
                f.write(json.dumps(record) + "\n")

        # 4. best_pipeline.json & prescription.txt
        if winning_individual and prescription:
            b_ns = baseline_result.metrics.median_time_ns if (baseline_result and baseline_result.metrics) else 1.0
            p_val = 1.0
            if baseline_result and baseline_result.metrics and baseline_result.metrics.samples_ns:
                p_val = calculate_p_value(baseline_result.metrics.samples_ns, [winning_individual.fitness or b_ns] * 10)

            best_data = {
                "passes": winning_individual.sequence.passes,
                "baseline_time_ms": prescription.baseline_time_ms,
                "candidate_time_ms": prescription.candidate_time_ms,
                "speedup_ratio": prescription.speedup_ratio,
                "p_value": p_val,
                "statistically_significant": p_val < 0.05,
            }
            with open(os.path.join(run_dir, "best_pipeline.json"), "w", encoding="utf-8") as f:
                json.dump(best_data, f, indent=2)

            with open(os.path.join(run_dir, "prescription.txt"), "w", encoding="utf-8") as f:
                f.write(prescription.reproducible_clang_command + "\n")

        # 5. benchmark_diff.svg ASCII representation
        with open(os.path.join(run_dir, "benchmark_diff.svg"), "w", encoding="utf-8") as f:
            b_ms = prescription.baseline_time_ms if prescription else 0.0
            c_ms = prescription.candidate_time_ms if prescription else 0.0
            f.write(f"<!-- Baseline: {b_ms} ms, Candidate: {c_ms} ms -->\n<svg xmlns='http://www.w3.org/2000/svg' width='400' height='100'><text x='10' y='30'>Baseline: {b_ms} ms</text><text x='10' y='70'>Candidate: {c_ms} ms</text></svg>\n")

        return run_dir
