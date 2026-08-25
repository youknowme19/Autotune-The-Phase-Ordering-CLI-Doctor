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
    search_speedup_a: float
    search_speedup_b: float
    confirmed_speedup_a: float
    confirmed_speedup_b: float
    speedup_diff: float
    p_value_a: float
    p_value_b: float
    cv_pct_a: float
    cv_pct_b: float
    cohens_d_a: float
    cohens_d_b: float
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

        s_a = data_a.get("search_speedup", p_a.get("speedup_ratio", 1.0))
        s_b = data_b.get("search_speedup", p_b.get("speedup_ratio", 1.0))

        c_a = data_a.get("confirmed_speedup", s_a)
        c_b = data_b.get("confirmed_speedup", s_b)

        diff = round(c_b - c_a, 3)

        ev_a = data_a.get("evidence_score", {})
        ev_b = data_b.get("evidence_score", {})

        if c_b > c_a:
            summary = f"Report B confirmed speedup ({c_b:.2f}x) outperformed Report A ({c_a:.2f}x) by +{diff}x gain."
        elif c_b < c_a:
            summary = f"Report B confirmed speedup ({c_b:.2f}x) regressed relative to Report A ({c_a:.2f}x) by {diff}x delta."
        else:
            summary = "Report A and Report B achieved identical confirmed speedup parity."

        return ComparisonResult(
            report_a_path=report_a_path,
            report_b_path=report_b_path,
            search_speedup_a=round(s_a, 2),
            search_speedup_b=round(s_b, 2),
            confirmed_speedup_a=round(c_a, 2),
            confirmed_speedup_b=round(c_b, 2),
            speedup_diff=diff,
            p_value_a=round(ev_a.get("p_value", 1.0), 4),
            p_value_b=round(ev_b.get("p_value", 1.0), 4),
            cv_pct_a=round(ev_a.get("candidate_cv_pct", 0.0), 1),
            cv_pct_b=round(ev_b.get("candidate_cv_pct", 0.0), 1),
            cohens_d_a=round(ev_a.get("cohens_d_effect_size", 0.0), 2),
            cohens_d_b=round(ev_b.get("cohens_d_effect_size", 0.0), 2),
            classification_a=p_a.get("classification", "N/A"),
            classification_b=p_b.get("classification", "N/A"),
            evidence_grade_a=p_a.get("evidence_grade", "B"),
            evidence_grade_b=p_b.get("evidence_grade", "B"),
            passes_count_a=len(p_a.get("pass_sequence", {}).get("passes", [])),
            passes_count_b=len(p_b.get("pass_sequence", {}).get("passes", [])),
            summary=summary,
        )

