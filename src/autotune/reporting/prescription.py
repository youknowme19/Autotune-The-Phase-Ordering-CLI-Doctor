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


class PrescriptionBuilder:
    """Produces reproducible compiler prescription commands."""

    @staticmethod
    def build(
        source_path: str,
        output_binary: str,
        pass_sequence: PassSequence,
        clang_path: str,
        opt_path: Optional[str],
        baseline_time_ns: float,
        candidate_time_ns: float,
    ) -> CompilerPrescription:
        passes_joined = ",".join(pass_sequence.passes) if pass_sequence.passes else "mem2reg"
        
        if opt_path:
            opt_cmd = f"{opt_path} -passes='{passes_joined}' input.ll -S -o output.ll"
            clang_cmd = f"{clang_path} -O0 -Xclang -disable-O0-optnone -emit-llvm -S {source_path} -o - | {opt_path} -passes='{passes_joined}' -S -o - | {clang_path} -x assembler - -o {output_binary}"
        else:
            opt_cmd = None
            clang_cmd = f"{clang_path} -O2 -mllvm -passes='{passes_joined}' {source_path} -o {output_binary}"

        b_ms = round(baseline_time_ns / 1e6, 3)
        c_ms = round(candidate_time_ns / 1e6, 3)
        speedup = round(baseline_time_ns / candidate_time_ns, 2) if candidate_time_ns > 0 else 1.0

        if candidate_time_ns <= 0 or baseline_time_ns <= 0:
            classification = ResultClassification.NO_VALID_CANDIDATE
        elif speedup >= 1.02:
            classification = ResultClassification.IMPROVED
        elif speedup >= 0.98:
            classification = ResultClassification.TIE
        else:
            classification = ResultClassification.REGRESSION

        return CompilerPrescription(
            pass_sequence=pass_sequence,
            reproducible_clang_command=clang_cmd,
            reproducible_opt_command=opt_cmd,
            baseline_time_ms=b_ms,
            candidate_time_ms=c_ms,
            speedup_ratio=speedup,
            classification=classification,
        )
