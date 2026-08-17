"""
Individual candidate model wrapping a PassSequence and fitness evaluation.
"""

from typing import Optional
from pydantic import BaseModel, Field
from autotune.llvm.passes import PassSequence


class Individual(BaseModel):
    """Genetic algorithm individual candidate."""

    sequence: PassSequence
    fitness: Optional[float] = None  # Lower is better (execution time ns). None = un-evaluated
    compilation_success: bool = True
    correctness_success: bool = True
    error_message: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.compilation_success and self.correctness_success and self.fitness is not None

    def __lt__(self, other: "Individual") -> bool:
        """Comparison for fitness sorting. Valid candidates with lower cost come first."""
        if not self.is_valid and not other.is_valid:
            return False
        if not self.is_valid:
            return False  # self is worse
        if not other.is_valid:
            return True   # self is better
        return self.fitness < other.fitness
