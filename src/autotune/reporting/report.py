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

    def export_markdown(self, output_file_path: str) -> None:
        """Export research-grade Markdown report summary."""
        lines = [
            "# Autotune Optimization Search Report",
            "",
            f"**Timestamp:** {self.timestamp}  ",
            f"**Source File:** `{self.source_path}`  ",
            f"**Workload File:** `{self.workload_path or 'N/A'}`  ",
            f"**Architecture:** {self.doctor_report.arch} ({self.doctor_report.os_name})  ",
            f"**Compiler:** {self.doctor_report.clang_version or 'Clang'}  ",
            "",
            "## Executive Summary",
            "",
        ]

        if self.prescription:
            p = self.prescription
            cls_val = getattr(p.classification, "value", str(p.classification))
            lines.extend([
                f"- **Classification:** `{cls_val}`",
                f"- **Baseline (-O3):** {p.baseline_time_ms} ms",
                f"- **Candidate Best:** {p.candidate_time_ms} ms",
                f"- **Confirmed Speedup:** **{p.speedup_ratio}x**",
                "",
                "## Recommended LLVM Pass Pipeline",
                "",
                "```text",
                f"{' -> '.join(p.pass_sequence.passes)}",
                "```",
                "",
                "## Reproducible Build Command",
                "",
                "```bash",
                f"{p.reproducible_clang_command}",
                "```",
                "",
            ])
        else:
            lines.append("No valid candidates outperformed baseline -O3.\n")

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
