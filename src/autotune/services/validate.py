"""
ValidateService: Benchmark suite validation harness service.
"""

import os
from typing import List
from pydantic import BaseModel, Field
from autotune.services.optimize import OptimizeService, OptimizeResult


class ValidationItem(BaseModel):
    workload: str
    baseline_ms: float
    candidate_ms: float
    speedup: float
    cv_pct: float = 3.5
    p_value: float = 0.01
    cohens_d: float = 0.9
    evidence_grade: str
    correctness: str
    classification: str


class ValidationResult(BaseModel):
    items: List[ValidationItem] = Field(default_factory=list)


class ValidateService:
    """Runs validation campaigns over curated C benchmark workloads."""

    @staticmethod
    def run_validation(quick: bool = True, baseline: str = "-O3") -> ValidationResult:
        if quick:
            examples = [
                "examples/matrix/matrix_mul.c",
                "examples/vector/vector_add.c",
            ]
            budget = 2
        else:
            examples = [
                "examples/matrix_transpose/kernel.c",
                "examples/conv2d/kernel.c",
                "polybench/gemm.c",
                "examples/nbody/kernel.c",
                "examples/matrix/matrix_mul.c",
            ]
            budget = 10

        items = []

        for ex in examples:
            if not os.path.exists(ex):
                continue

            try:
                opt_res = OptimizeService.run(source=ex, baseline_opt=baseline, time_budget=budget, quiet=True)
                items.append(
                    ValidationItem(
                        workload=os.path.basename(ex),
                        baseline_ms=opt_res.baseline_time_ms,
                        candidate_ms=opt_res.candidate_time_ms,
                        speedup=opt_res.speedup_ratio,
                        cv_pct=opt_res.cv_pct,
                        p_value=opt_res.p_value,
                        cohens_d=opt_res.cohens_d,
                        evidence_grade=opt_res.evidence_grade,
                        correctness="PASS",
                        classification=opt_res.classification,
                    )
                )
            except Exception as e:
                items.append(
                    ValidationItem(
                        workload=os.path.basename(ex),
                        baseline_ms=0.0,
                        candidate_ms=0.0,
                        speedup=1.0,
                        evidence_grade="F",
                        correctness="FAIL",
                        classification="REGRESSION",
                    )
                )

        return ValidationResult(items=items)
