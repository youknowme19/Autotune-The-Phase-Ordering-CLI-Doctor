"""
Benchmark and diagnostic report generator and JSON exporter.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from autotune.benchmark.models import BenchmarkResult
from autotune.doctor.checks import DoctorReport
from autotune.reporting.prescription import CompilerPrescription


class DiagnosisReport(BaseModel):
    doctor_report: DoctorReport
    baseline_result: Optional[BenchmarkResult] = None
    prescription: Optional[CompilerPrescription] = None
    status: str = "READY FOR SEARCH"


class SearchReport(BaseModel):
    """Full structured JSON search report containing platform metadata, CPU info, and timing statistics."""

    timestamp: str = datetime.now().isoformat()
    source_path: str
    workload_path: Optional[str] = None
    doctor_report: DoctorReport
    baseline_result: Optional[BenchmarkResult] = None
    prescription: Optional[CompilerPrescription] = None
    generations_searched: int
    population_size: int
    seed: Optional[int] = None

    def export_json(self, output_file_path: str) -> None:
        """Export structured diagnostic report to JSON file."""
        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write(self.model_dump_json(indent=2))
