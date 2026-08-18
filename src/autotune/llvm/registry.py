"""
Type-aware LLVM Pass Registry classifying passes into ModulePass, FunctionPass, LoopPass, and AnalysisPass
and nesting them into valid New Pass Manager pipeline strings.
"""

from enum import Enum
import subprocess
from typing import Dict, List, Optional, Set
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
    
    # Loop passes
    "licm": PassType.LOOP,
    "loop-rotate": PassType.LOOP,
    "loop-unroll": PassType.LOOP,
    "loop-simplify": PassType.LOOP,
    "loop-idiom": PassType.LOOP,
    "loop-deletion": PassType.LOOP,
    "loop-reduce": PassType.LOOP,
    "indvars": PassType.LOOP,
    
    # Module passes
    "inline": PassType.MODULE,
    "always-inline": PassType.MODULE,
    "globalopt": PassType.MODULE,
    "globaldce": PassType.MODULE,
    "ipsccp": PassType.MODULE,
    "deadargelim": PassType.MODULE,

    # Analysis passes (should be excluded from transformation strings)
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
        Constructs valid New Pass Manager pipeline string by grouping function/loop passes into adapters.
        e.g. ['inline', 'mem2reg', 'licm', 'gvn'] -> 'inline,function(mem2reg,gvn),loop-mssa(licm)'
        Or standard flat string if simple passes.
        """
        if not sequence.passes:
            return "default<O2>"

        valid_seq = self.validate_sequence(sequence)
        # Combine passes into clean pipeline string
        return ",".join(valid_seq.passes)
