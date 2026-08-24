"""
CompareService: Side-by-side search report comparison service.
"""

import json
import os
from typing import Any, Dict
from pydantic import BaseModel


class ComparisonResult(BaseModel):
    report_a_path: str
    report_b_path: str
    speedup_a: float
    speedup_b: float
    speedup_diff: float
    classification_a: str
    classification_b: str
    evidence_grade_a: str
    evidence_grade_b: str
    passes_count_a: int
    passes_count_b: int
    summary: str


class CompareService:
    """Compares two optimization search reports side-by-side."""

    @staticmethod
    def compare_reports(report_a_path: str, report_b_path: str) -> ComparisonResult:
        if not os.path.exists(report_a_path) or not os.path.exists(report_b_path):
            raise FileNotFoundError("One or both report JSON files not found.")

        with open(report_a_path, "r", encoding="utf-8") as f:
            data_a = json.load(f)
        with open(report_b_path, "r", encoding="utf-8") as f:
            data_b = json.load(f)

        p_a = data_a.get("prescription", {})
        p_b = data_b.get("prescription", {})

        sp_a = p_a.get("speedup_ratio", 1.0)
        sp_b = p_b.get("speedup_ratio", 1.0)
        diff = round(sp_b - sp_a, 3)

        if sp_b > sp_a:
            summary = f"Report B outperformed Report A by +{diff}x speedup gain."
        elif sp_b < sp_a:
            summary = f"Report B regressed relative to Report A by {diff}x speedup delta."
        else:
            summary = "Report A and Report B achieved identical speedup parity."

        return ComparisonResult(
            report_a_path=report_a_path,
            report_b_path=report_b_path,
            speedup_a=sp_a,
            speedup_b=sp_b,
            speedup_diff=diff,
            classification_a=p_a.get("classification", "N/A"),
            classification_b=p_b.get("classification", "N/A"),
            evidence_grade_a=p_a.get("evidence_grade", "B"),
            evidence_grade_b=p_b.get("evidence_grade", "B"),
            passes_count_a=len(p_a.get("pass_sequence", {}).get("passes", [])),
            passes_count_b=len(p_b.get("pass_sequence", {}).get("passes", [])),
            summary=summary,
        )
