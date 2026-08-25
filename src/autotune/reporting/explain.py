"""
Pipeline Inspector and Pass Explainability Engine.
Translates LLVM pass sequences into human-readable compiler optimization explanations.
"""

from typing import Any, Dict, List, NamedTuple, Optional
from autotune.llvm.passes import PassSequence, PassValidator

class PassExplanation(NamedTuple):
    pass_name: str
    domain: str
    description: str
    expected_impact: str


PASS_KNOWLEDGE_BASE: Dict[str, PassExplanation] = {
    "mem2reg": PassExplanation(
        pass_name="mem2reg",
        domain="SSA Transformation",
        description="Promotes stack memory allocations (alloca) to SSA registers.",
        expected_impact="High - Eliminates stack load/store overhead.",
    ),
    "sroa": PassExplanation(
        pass_name="sroa",
        domain="Scalar Replacement",
        description="Breaks aggregate structures and arrays into individual scalar SSA variables.",
        expected_impact="High - Enables register allocation for struct fields.",
    ),
    "gvn": PassExplanation(
        pass_name="gvn",
        domain="Scalar DCE & CSE",
        description="Global Value Numbering for redundant expression elimination.",
        expected_impact="Medium - Eliminates redundant computations across basic blocks.",
    ),
    "early-cse": PassExplanation(
        pass_name="early-cse",
        domain="Scalar CSE",
        description="Early Common Subexpression Elimination for local value reuse.",
        expected_impact="Medium - Fast local expression deduplication.",
    ),
    "licm": PassExplanation(
        pass_name="licm",
        domain="Loop Optimization",
        description="Loop-Invariant Code Motion hoists invariant computations out of loop bodies.",
        expected_impact="High - Reduces loop body instruction count.",
    ),
    "loop-rotate": PassExplanation(
        pass_name="loop-rotate",
        domain="Loop Canonicalization",
        description="Transforms do-while style loops into bottom-tested loops.",
        expected_impact="Medium - Exposes loop invariants and enables vectorization.",
    ),
    "loop-unroll": PassExplanation(
        pass_name="loop-unroll",
        domain="Loop Transformation",
        description="Unrolls loop bodies to reduce iteration branch cost.",
        expected_impact="High - Reduces loop overhead and exposes ILP.",
    ),
    "loop-vectorize": PassExplanation(
        pass_name="loop-vectorize",
        domain="Vectorization",
        description="Transforms scalar loop iterations into SIMD vector operations.",
        expected_impact="Very High - Multiplies arithmetic throughput on Apple Silicon / x86 AVX.",
    ),
    "slp-vectorize": PassExplanation(
        pass_name="slp-vectorize",
        domain="Vectorization",
        description="Superword-Level Parallelism vectorizer for straight-line code.",
        expected_impact="Medium - Combines independent scalar ops into SIMD registers.",
    ),
    "simplifycfg": PassExplanation(
        pass_name="simplifycfg",
        domain="CFG Cleanup",
        description="Simplifies control flow graph by merging basic blocks and deleting unreachable code.",
        expected_impact="Medium - Reduces branch mispredictions and code bloat.",
    ),
    "instcombine": PassExplanation(
        pass_name="instcombine",
        domain="Peephole Optimization",
        description="Combines algebraic instruction sequences into shorter canonical forms.",
        expected_impact="High - Reductions in raw instruction count.",
    ),
    "reassociate": PassExplanation(
        pass_name="reassociate",
        domain="Arithmetic Transformation",
        description="Reassociates commutative expressions to expose parallel evaluation chains.",
        expected_impact="Medium - Unlocks instruction-level parallelism (ILP).",
    ),
    "inline": PassExplanation(
        pass_name="inline",
        domain="Interprocedural (IPO)",
        description="Inlines small or hot function calls into call sites.",
        expected_impact="High - Removes call frame setup and unlocks inter-procedural passes.",
    ),
    "memcpyopt": PassExplanation(
        pass_name="memcpyopt",
        domain="Memory Optimization",
        description="Optimizes memcpy and memset calls by combining contiguous memory operations.",
        expected_impact="Medium - Improves memory bandwidth utilization.",
    ),
    "dce": PassExplanation(
        pass_name="dce",
        domain="Dead Code Elimination",
        description="Removes instructions whose results are never consumed.",
        expected_impact="Low - Binary size cleanup.",
    ),
    "sccp": PassExplanation(
        pass_name="sccp",
        domain="Constant Propagation",
        description="Sparse Conditional Constant Propagation evaluates constant expressions at compile-time.",
        expected_impact="Medium - Folds compile-time constants.",
    ),
}


class PipelineInspector:
    """Inspects and explains LLVM pass sequences and full search reports."""

    def __init__(self, validator: Optional[PassValidator] = None):
        self.validator = validator or PassValidator()

    def explain(self, sequence: PassSequence) -> List[PassExplanation]:
        explanations = []
        for p in sequence.passes:
            if p in PASS_KNOWLEDGE_BASE:
                explanations.append(PASS_KNOWLEDGE_BASE[p])
            else:
                explanations.append(
                    PassExplanation(
                        pass_name=p,
                        domain="LLVM Optimization",
                        description=f"Standard LLVM pass '{p}'",
                        expected_impact="Variable",
                    )
                )
        return explanations

    @staticmethod
    def explain_report(report_data: Dict[str, Any]) -> List[str]:
        """Provides a human-readable scientific rationale for an optimization search report."""
        p_data = report_data.get("prescription", {})
        search_speedup = report_data.get("search_speedup", p_data.get("speedup_ratio", 1.0))
        confirmed_speedup = report_data.get("confirmed_speedup", search_speedup)
        classification = p_data.get("classification", "NO_SIGNIFICANT_CHANGE")
        grade = p_data.get("evidence_grade", "D")

        ev_score = report_data.get("evidence_score", {})
        pval = ev_score.get("p_value", 1.0)
        cd = ev_score.get("cohens_d_effect_size", 0.0)
        correctness = ev_score.get("correctness_pass", True)

        lines = [
            f"1. Search Phase: Discovered candidate pipeline with best exploratory speedup of {search_speedup:.2f}x.",
            f"2. Confirmation Phase: Fresh independent benchmarking measured {confirmed_speedup:.2f}x speedup.",
        ]

        if not correctness:
            lines.append("3. Correctness Gate: Candidate output FAILED correctness verification.")
        else:
            lines.append("3. Correctness Gate: Candidate output PASSED correctness verification.")

        lines.append(f"4. Statistical Evaluation: Welch's t-test p-value={pval:.4f}, Cohen's d={cd:.2f}.")

        if grade == "A":
            lines.append("5. Evidence Verdict: Grade A — High-confidence, statistically significant speedup exceeding 1.05x.")
        elif grade == "B":
            lines.append("5. Evidence Verdict: Grade B — Statistically significant confirmed speedup exceeding 1.02x.")
        elif grade == "C":
            lines.append("5. Evidence Verdict: Grade C — Marginal speedup or noisy measurement (insufficient statistical confidence).")
        elif grade == "D":
            lines.append("5. Evidence Verdict: Grade D — Baseline parity (-O3 performance equivalence).")
        else:
            lines.append("5. Evidence Verdict: Grade F — Performance regression, execution failure, or correctness failure.")

        if classification == "IMPROVED":
            lines.append("6. Action Recommendation: Prescribed candidate pipeline is eligible for production deployment & KnowledgeStore persistence.")
        elif classification == "REGRESSION":
            lines.append("6. Action Recommendation: Prescribed pipeline REJECTED due to confirmed performance regression or failure.")
        else:
            lines.append("6. Action Recommendation: Prescribed pipeline REJECTED due to lack of statistically significant improvement.")

        return lines

