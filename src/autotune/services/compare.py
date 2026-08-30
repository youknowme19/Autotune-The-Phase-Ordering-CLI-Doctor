"""
CompareService: Side-by-side search report and live heuristic vs LLM comparison service.
"""

import json
import os
import time
from typing import Any, Dict, Optional
from pydantic import BaseModel

from autotune.services.doctor import DoctorService, DoctorResult


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


class LiveComparisonResult(BaseModel):
    source_path: str
    heuristic_speedup: float
    llm_speedup: float
    speedup_delta: float
    heuristic_grade: str
    llm_grade: str
    heuristic_passes_count: int
    llm_passes_count: int
    heuristic_search_time_s: float
    llm_search_time_s: float
    heuristic_correctness: str
    llm_correctness: str
    summary: str


class CompareService:
    """Compares two optimization search reports or runs live A/B comparison."""

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

    @staticmethod
    def compare_live(
        source: str,
        preset: str = "quick",
        seed: int = 42,
        workload: Optional[str] = None,
        provider: str = "openai",
    ) -> LiveComparisonResult:
        """Run controlled comparison between Heuristic (offline) and LLM-guided seeding."""
        if not os.path.exists(source):
            raise FileNotFoundError(f"Source file '{source}' not found.")

        t0 = time.perf_counter()
        res_heur = DoctorService.run(
            source=source,
            preset=preset,
            seed=seed,
            workload=workload,
            llm=False,
            quiet=True,
        )
        t_heur = round(time.perf_counter() - t0, 2)

        t1 = time.perf_counter()
        res_llm = DoctorService.run(
            source=source,
            preset=preset,
            seed=seed,
            workload=workload,
            llm=True,
            provider=provider,
            quiet=True,
        )
        t_llm = round(time.perf_counter() - t1, 2)

        diff = round(res_llm.confirmed_speedup - res_heur.confirmed_speedup, 2)
        if diff > 0:
            summary = f"LLM-guided seeding achieved +{diff}x higher confirmed speedup than offline heuristic seeding."
        elif diff < 0:
            summary = f"Offline heuristic seeding outperformed LLM-guided seeding by +{abs(diff)}x higher speedup."
        else:
            summary = f"Both heuristic and LLM-guided seeding achieved identical speedup parity ({res_heur.confirmed_speedup:.2f}x)."

        return LiveComparisonResult(
            source_path=source,
            heuristic_speedup=res_heur.confirmed_speedup,
            llm_speedup=res_llm.confirmed_speedup,
            speedup_delta=diff,
            heuristic_grade=res_heur.evidence_grade,
            llm_grade=res_llm.evidence_grade,
            heuristic_passes_count=len(res_heur.winning_passes),
            llm_passes_count=len(res_llm.winning_passes),
            heuristic_search_time_s=t_heur,
            llm_search_time_s=t_llm,
            heuristic_correctness=res_heur.correctness_status,
            llm_correctness=res_llm.correctness_status,
            summary=summary,
        )
