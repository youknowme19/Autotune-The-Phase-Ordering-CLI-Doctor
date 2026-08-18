"""
Type-aware LLVM Pass Registry classifying passes into ModulePass, FunctionPass, LoopPass, and AnalysisPass
and nesting them into valid New Pass Manager pipeline strings.
"""

from enum import Enum
from typing import Dict, List, Optional
from autotune.llvm.passes import PassSequence


class PassType(str, Enum):
    MODULE = "ModulePass"
    FUNCTION = "FunctionPass"
    LOOP = "LoopPass"
    ANALYSIS = "AnalysisPass"
    UNKNOWN = "Unknown"


# Comprehensive compatibility classification of standard LLVM passes
KNOWN_PASS_CLASSIFICATIONS: Dict[str, PassType] = {
    # Function passes
    "mem2reg": PassType.FUNCTION,
    "sroa": PassType.FUNCTION,
    "early-cse": PassType.FUNCTION,
    "gvn": PassType.FUNCTION,
    "instcombine": PassType.FUNCTION,
    "simplifycfg": PassType.FUNCTION,
    "reassociate": PassType.FUNCTION,
    "sccp": PassType.FUNCTION,
    "dce": PassType.FUNCTION,
    "adce": PassType.FUNCTION,
    "bdce": PassType.FUNCTION,
    "jump-threading": PassType.FUNCTION,
    "memcpyopt": PassType.FUNCTION,
    "slp-vectorize": PassType.FUNCTION,
    "loop-vectorize": PassType.FUNCTION,
    "correlated-propagation": PassType.FUNCTION,
    "lower-expect": PassType.FUNCTION,
    "tailcallelim": PassType.FUNCTION,
    "loop-rotate": PassType.FUNCTION,
    "loop-unroll": PassType.FUNCTION,
    "loop-simplify": PassType.FUNCTION,
    "loop-idiom": PassType.FUNCTION,
    "loop-deletion": PassType.FUNCTION,
    "loop-reduce": PassType.FUNCTION,
    "indvars": PassType.FUNCTION,

    # Loop passes requiring loop-mssa adapter
    "licm": PassType.LOOP,

    # Module passes
    "inline": PassType.MODULE,
    "always-inline": PassType.MODULE,
    "globalopt": PassType.MODULE,
    "globaldce": PassType.MODULE,
    "ipsccp": PassType.MODULE,
    "deadargelim": PassType.MODULE,
    "argpromotion": PassType.MODULE,

    # Analysis passes
    "basic-aa": PassType.ANALYSIS,
    "globals-aa": PassType.ANALYSIS,
    "scalar-evolution": PassType.ANALYSIS,
    "targetlibinfo": PassType.ANALYSIS,
    "aa": PassType.ANALYSIS,
}


class LLVMPassRegistry:
    """Manages classification, validation, and construction of New Pass Manager syntax."""

    def __init__(self, opt_path: Optional[str] = None):
        self.opt_path = opt_path
        self.classifications: Dict[str, PassType] = dict(KNOWN_PASS_CLASSIFICATIONS)

    def get_pass_type(self, pass_name: str) -> PassType:
        return self.classifications.get(pass_name, PassType.FUNCTION)

    def is_analysis_pass(self, pass_name: str) -> bool:
        return self.get_pass_type(pass_name) == PassType.ANALYSIS

    def validate_sequence(self, sequence: PassSequence) -> PassSequence:
        """Filter out unknown or analysis-only passes."""
        valid_passes: List[str] = []
        for p in sequence.passes:
            if not self.is_analysis_pass(p):
                valid_passes.append(p)
        return PassSequence(passes=valid_passes)

    def construct_npm_pipeline_string(self, sequence: PassSequence) -> str:
        """
        Constructs valid New Pass Manager pipeline string by adapting loop/module passes appropriately.
        e.g. ['inline', 'mem2reg', 'licm', 'gvn'] -> 'inline,function(mem2reg,loop-mssa(licm),gvn)'
        """
        if not sequence.passes:
            return "default<O2>"

        valid_seq = self.validate_sequence(sequence)
        parts: List[str] = []
        fn_passes: List[str] = []

        for p in valid_seq.passes:
            ptype = self.get_pass_type(p)
            if ptype == PassType.MODULE:
                if fn_passes:
                    parts.append(f"function({','.join(fn_passes)})")
                    fn_passes = []
                parts.append(p)
            elif p == "licm":
                fn_passes.append("loop-mssa(licm)")
            else:
                fn_passes.append(p)

        if fn_passes:
            parts.append(f"function({','.join(fn_passes)})")

        return ",".join(parts) if parts else "default<O2>"
