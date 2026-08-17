"""
Population container for Genetic Algorithm candidates.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from autotune.search.individual import Individual


class Population(BaseModel):
    """Container managing candidate individuals for GA search."""

    generation: int = 0
    individuals: List[Individual] = Field(default_factory=list)

    def best_individual(self) -> Optional[Individual]:
        valid = [ind for ind in self.individuals if ind.is_valid]
        if not valid:
            return None
        valid.sort()
        return valid[0]

    def sort_individuals(self) -> None:
        self.individuals.sort()
