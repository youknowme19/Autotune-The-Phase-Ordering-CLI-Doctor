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
        if not sequence.passes:
            return "default<O0>"
        # Wrap passes into module/function pass pipeline string
        joined = ",".join(sequence.passes)
        return f"function({joined})"

    @staticmethod
    def to_clang_flags(sequence: PassSequence) -> List[str]:
        """Convert pass sequence to clang optimization flags."""
        if not sequence.passes:
            return ["-O0"]
        pipeline_str = ",".join(sequence.passes)
        # Use LLVM opaque pipeline flag for clang
        return ["-O2", f"-fplugin-arg-opt=-passes={pipeline_str}"]
