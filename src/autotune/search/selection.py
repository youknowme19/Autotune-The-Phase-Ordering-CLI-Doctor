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
        self, population: List[Individual], k: int = 3, pressure: float = 0.85
    ) -> Individual:
        """Select candidate out of k randomly drawn individuals with probabilistic selection pressure."""
        k = min(k, len(population))
        contestants = self.rng.sample(population, k)
        # Sort contestants according to fitness (best first)
        contestants.sort()
        if len(contestants) > 1 and self.rng.random() > pressure:
            return contestants[1]
        return contestants[0]

    def rank_proportional_select(self, population: List[Individual]) -> Individual:
        """Linear rank-based roulette wheel selection."""
        sorted_pop = sorted(population)
        n = len(sorted_pop)
        if n == 1:
            return sorted_pop[0]
        # Rank weights: highest rank gets highest weight (n, n-1, ..., 1)
        weights = [n - i for i in range(n)]
        total_weight = sum(weights)
        pick = self.rng.uniform(0, total_weight)
        current = 0.0
        for ind, w in zip(sorted_pop, weights):
            current += w
            if current >= pick:
                return ind
        return sorted_pop[0]

    def get_elites(self, population: List[Individual], n: int = 2) -> List[Individual]:
        """Extract top n elite individuals."""
        sorted_pop = sorted(population)
        return [ind for ind in sorted_pop[:n] if ind.is_valid]
