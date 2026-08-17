"""
LLVM Pass Pipeline string formatting and builder.
"""

from typing import List
from autotune.llvm.passes import PassSequence


class PipelineBuilder:
    """Builds LLVM pass pipeline execution arguments for clang and opt."""

    @staticmethod
    def to_opt_passes_arg(sequence: PassSequence) -> str:
        """Convert pass sequence to modern LLVM opt `-passes=...` string."""
        return sequence.to_opt_string()

    @staticmethod
    def to_clang_flags(sequence: PassSequence) -> List[str]:
        """Convert pass sequence to clang optimization flags."""
        if not sequence.passes:
            return ["-O0"]
        pipeline_str = sequence.to_opt_string()
        return ["-O2", f"-fplugin-arg-opt=-passes={pipeline_str}"]
