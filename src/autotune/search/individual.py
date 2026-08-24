"""
Individual candidate model wrapping a PassSequence and fitness evaluation.
"""

from typing import Optional
from pydantic import BaseModel, Field
from autotune.llvm.passes import PassSequence, CanonicalPassNormalizer


class Individual(BaseModel):
    """Genetic algorithm individual candidate."""

    sequence: PassSequence
    fitness: Optional[float] = None  # Higher normalized_speed (or lower time ns). None = un-evaluated
    raw_time_ns: Optional[float] = None  # Execution time in ns
    normalized_speed: Optional[float] = None  # baseline_median_ns / candidate_median_ns
    fidelity: str = "HIGH"  # LOW, MEDIUM, HIGH
    screened: bool = False  # True if screened out by baseline gate
    confirmed: bool = False  # True if confirmed by final confirmation stage
    compilation_success: bool = True
    correctness_success: bool = True
    error_message: Optional[str] = None
    is_cached_timing: bool = False
    origin: str = "random"  # Provenance: heuristic, llm, random, mutation, crossover

    @property
    def raw_pipeline(self) -> str:
        return self.sequence.to_opt_string()

    @property
    def canonical_pipeline(self) -> str:
        return self.sequence.to_canonical_opt_string()

    @property
    def is_evaluated(self) -> bool:
        """Returns True if fitness evaluation has been completed."""
        return self.fitness is not None

    @property
    def is_valid(self) -> bool:
        return self.compilation_success and self.correctness_success and self.fitness is not None and self.fitness != float("-inf") and self.fitness != float("inf")

    def __lt__(self, other: "Individual") -> bool:
        """Comparison for sorting: candidate with BETTER performance comes first."""
        if not self.is_valid and not other.is_valid:
            return False
        if not self.is_valid:
            return False  # self is worse
        if not other.is_valid:
            return True   # self is better

        # If normalized_speed is present, higher is better
        if self.normalized_speed is not None and other.normalized_speed is not None:
            return self.normalized_speed > other.normalized_speed

        # Fallback to lower time ns
        return (self.raw_time_ns or self.fitness or float("inf")) < (other.raw_time_ns or other.fitness or float("inf"))
