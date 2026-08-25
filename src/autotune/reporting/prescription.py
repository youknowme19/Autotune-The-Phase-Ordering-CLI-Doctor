"""
Compiler prescription builder for reproducible build commands.
"""

from typing import List, Optional
from pydantic import BaseModel
from autotune.benchmark.models import ResultClassification
from autotune.llvm.passes import PassSequence


class CompilerPrescription(BaseModel):
    pass_sequence: PassSequence
    reproducible_clang_command: str
    reproducible_opt_command: Optional[str] = None
    baseline_time_ms: float
    candidate_time_ms: float
    speedup_ratio: float
    classification: ResultClassification = ResultClassification.IMPROVED
    evidence_grade: str = "B"


class PrescriptionBuilder:
    """Produces reproducible compiler prescription commands."""

    @staticmethod
    def build(
        source_path: str,
        output_binary: str,
        pass_sequence: Optional[PassSequence],
        clang_path: str,
        opt_path: Optional[str],
        baseline_time_ns: float,
        candidate_time_ns: float,
        evidence_grade: Optional[str] = None,
    ) -> CompilerPrescription:
        safe_seq = pass_sequence if (pass_sequence is not None and isinstance(pass_sequence, PassSequence)) else PassSequence(passes=[])
        passes_joined = ",".join(safe_seq.passes) if safe_seq.passes else ""
        
        if passes_joined and opt_path:
            opt_cmd = f"{opt_path} -passes='{passes_joined}' input.ll -S -o output.ll"
            clang_cmd = f"{clang_path} -O0 -Xclang -disable-O0-optnone -emit-llvm -S {source_path} -o - | {opt_path} -passes='{passes_joined}' -S -o - | {clang_path} -x assembler - -o {output_binary}"
        elif passes_joined:
            opt_cmd = None
            clang_cmd = f"{clang_path} -O2 -mllvm -passes='{passes_joined}' {source_path} -o {output_binary}"
        else:
            opt_cmd = None
            clang_cmd = f"{clang_path} -O3 {source_path} -o {output_binary}"

        b_ms = round(baseline_time_ns / 1e6, 3)
        c_ms = round(candidate_time_ns / 1e6, 3)
        speedup = round(baseline_time_ns / candidate_time_ns, 2) if candidate_time_ns > 0 else 1.0

        if candidate_time_ns <= 0 or baseline_time_ns <= 0 or not passes_joined:
            classification = ResultClassification.NO_VALID_CANDIDATE if not passes_joined else ResultClassification.REGRESSION
            grade = evidence_grade or "F"
        elif evidence_grade in ("C", "D", "F"):
            grade = evidence_grade
            if grade == "F" or speedup < 0.98:
                classification = ResultClassification.REGRESSION
            else:
                classification = ResultClassification.TIE
        elif speedup >= 1.02:
            classification = ResultClassification.IMPROVED
            grade = evidence_grade or ("B" if speedup < 1.05 else "A")
        elif speedup >= 0.98:
            classification = ResultClassification.TIE
            grade = "D"
        else:
            classification = ResultClassification.REGRESSION
            grade = "F"

        return CompilerPrescription(
            pass_sequence=safe_seq,
            reproducible_clang_command=clang_cmd,
            reproducible_opt_command=opt_cmd,
            baseline_time_ms=b_ms,
            candidate_time_ms=c_ms,
            speedup_ratio=speedup,
            classification=classification,
            evidence_grade=grade,
        )
