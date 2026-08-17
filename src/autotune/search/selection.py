"""
Genetic Algorithm selection operators (tournament selection, elitism).
"""

import random
from typing import List, Optional
from autotune.search.individual import Individual


class Selector:
    """Selection operators for GA population evolution."""

    def __init__(self, rng: Optional[random.Random] = None):
        self.rng = rng or random.Random()

    def tournament_select(
        self, population: List[Individual], k: int = 3
    ) -> Individual:
        """Select best candidate out of k randomly drawn individuals."""
        k = min(k, len(population))
        contestants = self.rng.sample(population, k)
        # Sort contestants according to fitness
        contestants.sort()
        return contestants[0]

    def get_elites(self, population: List[Individual], n: int = 2) -> List[Individual]:
        """Extract top n elite individuals."""
        sorted_pop = sorted(population)
        return [ind for ind in sorted_pop[:n] if ind.is_valid]
