"""
ExplainService: Explain discovered LLVM pass pipelines, compiler transformation mechanics,
and empirical evidence, clearly separating OBSERVED, INFERRED, and HYPOTHESIZED conclusions.
"""

import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from autotune.reporting.explain import PASS_KNOWLEDGE_BASE


class PassExplanationItem(BaseModel):
    pass_name: str
    domain: str
    description: str
    expected_impact: str
    category: str = "INFERRED"  # OBSERVED | INFERRED | HYPOTHESIZED


class OptimizationExplanation(BaseModel):
    source_path: str
    baseline_mode: str = "-O3"
    winning_passes: List[str] = Field(default_factory=list)
    speedup_ratio: float = 1.0
    baseline_time_ms: float = 0.0
    candidate_time_ms: float = 0.0
    evidence_grade: str = "N/A"
    correctness_status: str = "PASS"
    p_value: float = 1.0
    cohens_d: float = 0.0
    observed_facts: List[str] = Field(default_factory=list)
    inferred_mechanics: List[str] = Field(default_factory=list)
    hypothesized_effects: List[str] = Field(default_factory=list)
    pass_details: List[PassExplanationItem] = Field(default_factory=list)
    disclaimer: str = (
        "IMPORTANT: This explanation is derived from the observed pipeline and compiler evidence. "
        "It is not proof of causality unless explicitly supported by IR/assembly analysis."
    )


class ExplainService:
    """Explains optimization reports and pass sequences in rigorous technical terms."""

    @staticmethod
    def explain_report(report_path: str) -> OptimizationExplanation:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Report file '{report_path}' not found.")

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        source = data.get("source_path", "unknown")
        p_data = data.get("prescription", {})
        ev_data = data.get("evidence_score", {})
        asm_data = data.get("assembly", {})

        passes = p_data.get("pass_sequence", {}).get("passes", [])
        speedup = data.get("confirmed_speedup") or p_data.get("speedup_ratio", 1.0)
        b_ms = ev_data.get("baseline_median_ms") or p_data.get("baseline_time_ms", 0.0)
        c_ms = ev_data.get("candidate_median_ms") or p_data.get("candidate_time_ms", 0.0)
        grade = ev_data.get("grade") or p_data.get("evidence_grade", "N/A")
        p_val = ev_data.get("p_value", 1.0)
        cohens_d = ev_data.get("cohens_d_effect_size", 0.0)
        correctness = "PASS" if ev_data.get("correctness_pass", True) else "FAIL"

        observed: List[str] = []
        observed.append(f"Workload latency reduced from {b_ms:.3f} ms to {c_ms:.3f} ms ({speedup:.2f}x speedup).")
        observed.append(f"Output bitwise/checksum validation returned {correctness}.")
        if p_val < 0.05:
            observed.append(f"Welch's t-test demonstrated statistical significance (p={p_val:.4f}, Cohen's d={cohens_d:.2f}).")
        else:
            observed.append(f"Statistical test yielded p={p_val:.4f} (insufficient statistical significance).")

        if asm_data:
            tot_base = asm_data.get("baseline_instructions")
            tot_cand = asm_data.get("candidate_instructions")
            if tot_base and tot_cand:
                observed.append(f"Assembly instruction count changed from {tot_base} to {tot_cand} ({tot_cand - tot_base:+d} instructions).")

        inferred: List[str] = []
        pass_items: List[PassExplanationItem] = []

        for p in passes:
            info = PASS_KNOWLEDGE_BASE.get(p)
            domain = info.domain if info else "LLVM Core Optimization"
            desc = info.description if info else "LLVM IR transformation pass."
            impact = info.expected_impact if info else "Standard IR optimization."

            pass_items.append(
                PassExplanationItem(
                    pass_name=p,
                    domain=domain,
                    description=desc,
                    expected_impact=impact,
                    category="INFERRED",
                )
            )
            inferred.append(f"{p} ({domain}): {desc}")

        hypothesized: List[str] = []
        if "sccp" in passes and "gvn" in passes:
            hypothesized.append("Early constant propagation combined with value numbering may simplify index address calculations before register allocation.")
        if "mem2reg" in passes:
            hypothesized.append("Promoting stack alloca variables to SSA virtual registers minimizes load/store instructions in tight loop bodies.")
        if "loop-unroll" in passes or "loop-vectorize" in passes:
            hypothesized.append("Loop unrolling/vectorization may increase instruction-level parallelism at the cost of slight binary size increase.")
        if not hypothesized:
            hypothesized.append("The reordered pass pipeline likely avoids premature canonicalization that occurs in standard -O3.")

        return OptimizationExplanation(
            source_path=source,
            baseline_mode="-O3",
            winning_passes=passes,
            speedup_ratio=speedup,
            baseline_time_ms=b_ms,
            candidate_time_ms=c_ms,
            evidence_grade=grade,
            correctness_status=correctness,
            p_value=p_val,
            cohens_d=cohens_d,
            observed_facts=observed,
            inferred_mechanics=inferred,
            hypothesized_effects=hypothesized,
            pass_details=pass_items,
        )
