"""
LLVM Pass sequence representation, pass validation, mutators, and conservative canonicalization.
"""

import json
import random
import subprocess
from typing import Dict, List, Optional, Set
from pydantic import BaseModel, Field

KNOWN_VALID_PASSES: Set[str] = {
    "mem2reg",
    "gvn",
    "instcombine",
    "aggressive-instcombine",
    "loop-rotate",
    "loop-unroll",
    "loop-vectorize",
    "slp-vectorize",
    "slp-vectorizer",
    "vector-combine",
    "loop-flatten",
    "loop-interchange",
    "loop-unroll-and-jam",
    "loop-distribute",
    "loop-versioning",
    "licm",
    "simplifycfg",
    "dce",
    "adce",
    "dse",
    "sccp",
    "ipsccp",
    "inline",
    "always-inline",
    "argpromotion",
    "deadargelim",
    "globalopt",
    "globaldce",
    "reassociate",
    "sroa",
    "early-cse",
    "jump-threading",
    "correlated-propagation",
    "tailcallelim",
    "loop-idiom",
    "loop-deletion",
    "indvars",
    "loop-simplify",
    "memcpyopt",
    "lower-atomic",
    "gvn-hoist",
    "gvn-sink",
}

# Known explicit pass aliases with verified LLVM equivalence
PASS_ALIASES: Dict[str, str] = {
    "scalarrepl": "sroa",
    "promote": "mem2reg",
    "loweratomic": "lower-atomic",
    "slp-vectorize": "slp-vectorizer",
}


class CanonicalPassNormalizer:
    """
    Conservatively normalizes LLVM pass sequences for cache indexing.
    Syntactic canonicalization ONLY (whitespace normalization, alias resolution, deterministic formatting).
    STRICTLY PROHIBITED: Pass reordering, pass deletion, pass collapsing, or idempotence assumptions.
    """

    @staticmethod
    def canonicalize_pass_name(pass_name: str) -> str:
        clean = pass_name.strip().lower()
        return PASS_ALIASES.get(clean, clean)

    @classmethod
    def canonicalize_sequence(cls, sequence: "PassSequence") -> "PassSequence":
        canonical_passes = [cls.canonicalize_pass_name(p) for p in sequence.passes if p.strip()]
        return PassSequence(passes=canonical_passes)


class PassSequence(BaseModel):
    """Ordered sequence of LLVM optimization passes."""

    passes: List[str] = Field(default_factory=list)

    def to_opt_string(self) -> str:
        """Format pass sequence as comma-separated string for opt -passes="..."."""
        from autotune.llvm.registry import LLVMPassRegistry
        registry = LLVMPassRegistry()
        return registry.construct_npm_pipeline_string(self)

    def to_canonical_opt_string(self) -> str:
        """Format canonicalized pass sequence string."""
        canonical_seq = CanonicalPassNormalizer.canonicalize_sequence(self)
        return canonical_seq.to_opt_string()

    def insert(self, pass_name: str, index: Optional[int] = None) -> "PassSequence":
        new_passes = list(self.passes)
        if index is None or index < 0 or index > len(new_passes):
            new_passes.append(pass_name)
        else:
            new_passes.insert(index, pass_name)
        return PassSequence(passes=new_passes)

    def delete(self, index: int) -> "PassSequence":
        if 0 <= index < len(self.passes):
            new_passes = list(self.passes)
            new_passes.pop(index)
            return PassSequence(passes=new_passes)
        return PassSequence(passes=list(self.passes))

    def swap(self, idx1: int, idx2: int) -> "PassSequence":
        if 0 <= idx1 < len(self.passes) and 0 <= idx2 < len(self.passes):
            new_passes = list(self.passes)
            new_passes[idx1], new_passes[idx2] = new_passes[idx2], new_passes[idx1]
            return PassSequence(passes=new_passes)
        return PassSequence(passes=list(self.passes))

    def crossover(self, other: "PassSequence", pt1: int, pt2: int) -> "PassSequence":
        """Two-point crossover with another pass sequence."""
        if not self.passes or not other.passes:
            return PassSequence(passes=list(self.passes))

        p1 = max(0, min(pt1, len(self.passes)))
        p2 = max(p1, min(pt2, len(self.passes)))

        child_passes = self.passes[:p1] + other.passes[p1:p2] + self.passes[p2:]
        return PassSequence(passes=child_passes)

    def validate(self, validator: Optional["PassValidator"] = None) -> bool:
        """Validate if all passes in sequence are valid."""
        v = validator or PassValidator()
        return v.validate_sequence(self)

    def serialize(self) -> str:
        return json.dumps(self.passes)

    @classmethod
    def deserialize(cls, data: str) -> "PassSequence":
        parsed = json.loads(data)
        if isinstance(parsed, list):
            return cls(passes=[str(p) for p in parsed])
        raise ValueError("Invalid pass sequence JSON data")


class PassValidator:
    """Validates LLVM passes against installed toolchain capabilities."""

    def __init__(self, opt_path: Optional[str] = None):
        self.opt_path = opt_path
        self.valid_passes: Set[str] = set(KNOWN_VALID_PASSES)
        if opt_path:
            self._query_opt_passes()

    def _query_opt_passes(self) -> None:
        """Query LLVM opt binary for supported passes if possible."""
        try:
            res = subprocess.run(
                [self.opt_path, "--print-passes"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout:
                for line in res.stdout.splitlines():
                    line = line.strip()
                    if line and not line.startswith("Module passes:") and not line.startswith("Function passes:"):
                        pass_name = line.split()[0] if line.split() else line
                        self.valid_passes.add(pass_name)
        except Exception:
            pass

    def is_valid_pass(self, pass_name: str) -> bool:
        clean = CanonicalPassNormalizer.canonicalize_pass_name(pass_name)
        return clean in self.valid_passes

    def validate_sequence(self, sequence: PassSequence) -> bool:
        return all(self.is_valid_pass(p) for p in sequence.passes)

    def filter_sequence(self, sequence: PassSequence) -> PassSequence:
        valid_only = [
            CanonicalPassNormalizer.canonicalize_pass_name(p)
            for p in sequence.passes
            if self.is_valid_pass(p)
        ]
        return PassSequence(passes=valid_only)


class PassDAGOptimizer:
    """
    Intelligent Pass Pipeline Dependency and Redundancy Pruning.
    Eliminates redundant adjacent idempotent passes (e.g. repeated mem2reg without intermediary mutation)
    and resolves pass conflicts to maximize compiler throughput and search efficacy.
    """

    # Passes that are strictly idempotent when run consecutively without mutations
    IDEMPOTENT_CONSECUTIVE_PASSES: Set[str] = {
        "mem2reg",
        "sroa",
        "dce",
        "adce",
        "loop-simplify",
        "simplifycfg",
        "lower-atomic",
    }

    @classmethod
    def prune_redundant_passes(cls, sequence: PassSequence) -> PassSequence:
        """Prunes contiguous identical idempotent passes in a pass pipeline."""
        if not sequence.passes or len(sequence.passes) <= 1:
            return sequence

        pruned: List[str] = []
        prev: Optional[str] = None

        for p in sequence.passes:
            norm_p = CanonicalPassNormalizer.canonicalize_pass_name(p)
            if prev is not None and norm_p == prev and norm_p in cls.IDEMPOTENT_CONSECUTIVE_PASSES:
                # Skip consecutive duplicate idempotent pass
                continue
            pruned.append(norm_p)
            prev = norm_p

        return PassSequence(passes=pruned)
