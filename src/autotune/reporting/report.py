"""
Benchmark and diagnostic report generator.
"""

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
