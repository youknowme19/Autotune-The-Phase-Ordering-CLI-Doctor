"""
LLVM Pass sequence representation, pass validation, and mutators.
"""

import json
import random
import subprocess
from typing import List, Optional, Set
from pydantic import BaseModel, Field

# Standard LLVM optimization passes across function and loop vectorization/canonicalization
KNOWN_VALID_PASSES: Set[str] = {
    "mem2reg",
    "gvn",
    "instcombine",
    "loop-rotate",
    "loop-unroll",
    "loop-vectorize",
    "slp-vectorize",
    "licm",
    "simplifycfg",
    "dce",
    "adce",
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
}


class PassSequence(BaseModel):
    """Ordered sequence of LLVM optimization passes."""

    passes: List[str] = Field(default_factory=list)

    def to_opt_string(self) -> str:
        """Format pass sequence as comma-separated string for opt -passes="..."."""
        if not self.passes:
            return "mem2reg"
        return ",".join(self.passes)

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
        return pass_name in self.valid_passes

    def validate_sequence(self, sequence: PassSequence) -> bool:
        return all(self.is_valid_pass(p) for p in sequence.passes)

    def filter_sequence(self, sequence: PassSequence) -> PassSequence:
        valid_only = [p for p in sequence.passes if self.is_valid_pass(p)]
        return PassSequence(passes=valid_only)
