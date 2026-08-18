"""
Genetic Algorithm mutation operators (insert, delete, swap) with post-crossover pipeline normalization.
"""

import random
from typing import List, Optional
from autotune.llvm.passes import KNOWN_VALID_PASSES, PassSequence, PassValidator


class Mutator:
    """Applies genetic mutations to LLVM pass sequences with pipeline normalization."""

    def __init__(
        self,
        validator: Optional[PassValidator] = None,
        rng: Optional[random.Random] = None,
        min_length: int = 3,
        max_length: int = 32,
    ):
        self.validator = validator or PassValidator()
        self.rng = rng or random.Random()
        self.min_length = min_length
        self.max_length = max_length
        self.available_passes: List[str] = sorted(list(self.validator.valid_passes))

    def normalize(self, sequence: PassSequence) -> PassSequence:
        """Post-crossover & mutation normalization: deduplicate adjacent passes, ensure prerequisites, enforce bounds."""
        if not sequence.passes:
            return PassSequence(passes=["mem2reg", "instcombine", "gvn"])

        # 1. Collapse adjacent duplicate idempotent passes
        deduped: List[str] = []
        for p in sequence.passes:
            if not deduped or deduped[-1] != p:
                deduped.append(p)

        # 2. Prerequisite normalization: ensure scalar memory lowering precedes downstream optimizations
        if "mem2reg" not in deduped and "sroa" not in deduped:
            deduped.insert(0, "mem2reg")

        # 3. Enforce length bounds
        if len(deduped) < self.min_length:
            while len(deduped) < self.min_length:
                deduped.append(self.rng.choice(self.available_passes or ["instcombine"]))

        if len(deduped) > self.max_length:
            deduped = deduped[: self.max_length]

        return PassSequence(passes=deduped)

    def insert(self, sequence: PassSequence) -> PassSequence:
        if not self.available_passes:
            return sequence
        pass_to_add = self.rng.choice(self.available_passes)
        idx = self.rng.randint(0, len(sequence.passes))
        return sequence.insert(pass_to_add, idx)

    def delete(self, sequence: PassSequence) -> PassSequence:
        if len(sequence.passes) <= self.min_length:
            return sequence
        idx = self.rng.randint(0, len(sequence.passes) - 1)
        return sequence.delete(idx)

    def swap(self, sequence: PassSequence) -> PassSequence:
        if len(sequence.passes) < 2:
            return sequence
        idx1 = self.rng.randint(0, len(sequence.passes) - 1)
        idx2 = self.rng.randint(0, len(sequence.passes) - 1)
        while idx1 == idx2:
            idx2 = self.rng.randint(0, len(sequence.passes) - 1)
        return sequence.swap(idx1, idx2)

    def mutate(self, sequence: PassSequence, mutation_rate: float = 0.3) -> PassSequence:
        seq = self.normalize(sequence)
        if self.rng.random() > mutation_rate:
            return seq

        op = self.rng.choice(["insert", "delete", "swap"])
        if op == "insert":
            res = self.insert(seq)
        elif op == "delete":
            res = self.delete(seq)
        else:
            res = self.swap(seq)

        filtered = self.validator.filter_sequence(res)
        return self.normalize(filtered)
