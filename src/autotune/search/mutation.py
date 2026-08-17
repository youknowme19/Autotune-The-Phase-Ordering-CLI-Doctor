"""
Genetic Algorithm mutation operators (insert, delete, swap).
"""

import random
from typing import List, Optional
from autotune.llvm.passes import KNOWN_VALID_PASSES, PassSequence, PassValidator


class Mutator:
    """Applies genetic mutations to LLVM pass sequences."""

    def __init__(
        self,
        validator: Optional[PassValidator] = None,
        rng: Optional[random.Random] = None,
    ):
        self.validator = validator or PassValidator()
        self.rng = rng or random.Random()
        self.available_passes: List[str] = sorted(list(self.validator.valid_passes))

    def insert(self, sequence: PassSequence) -> PassSequence:
        if not self.available_passes:
            return sequence
        pass_to_add = self.rng.choice(self.available_passes)
        idx = self.rng.randint(0, len(sequence.passes))
        return sequence.insert(pass_to_add, idx)

    def delete(self, sequence: PassSequence) -> PassSequence:
        if not sequence.passes:
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
        if self.rng.random() > mutation_rate:
            return sequence

        op = self.rng.choice(["insert", "delete", "swap"])
        if op == "insert":
            res = self.insert(sequence)
        elif op == "delete":
            res = self.delete(sequence)
        else:
            res = self.swap(sequence)

        return self.validator.filter_sequence(res)
