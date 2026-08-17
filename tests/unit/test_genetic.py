"""
Unit tests for Genetic Algorithm operators, fitness ordering, and determinism.
"""

import random
import pytest
from autotune.llvm.passes import PassSequence
from autotune.search.fitness import FitnessEvaluator
from autotune.search.individual import Individual
from autotune.search.mutation import Mutator
from autotune.search.selection import Selector


def test_fitness_ordering():
    i1 = Individual(sequence=PassSequence(passes=["mem2reg"]), fitness=100.0)
    i2 = Individual(sequence=PassSequence(passes=["gvn"]), fitness=200.0)
    i_fail_comp = Individual(
        sequence=PassSequence(passes=["dce"]),
        compilation_success=False,
        fitness=float("inf"),
    )
    i_fail_corr = Individual(
        sequence=PassSequence(passes=["licm"]),
        correctness_success=False,
        fitness=float("inf"),
    )

    pop = [i2, i_fail_comp, i1, i_fail_corr]
    pop.sort()

    assert pop[0] == i1  # Lowest runtime (100.0 ns) is best
    assert pop[1] == i2  # 200.0 ns is second best
    # Failed individuals sort after valid ones


def test_deterministic_seed():
    rng1 = random.Random(42)
    mutator1 = Mutator(rng=rng1)
    seq1 = PassSequence(passes=["mem2reg", "gvn"])
    mutated1 = mutator1.mutate(seq1, mutation_rate=1.0)

    rng2 = random.Random(42)
    mutator2 = Mutator(rng=rng2)
    seq2 = PassSequence(passes=["mem2reg", "gvn"])
    mutated2 = mutator2.mutate(seq2, mutation_rate=1.0)

    assert mutated1.passes == mutated2.passes


def test_tournament_selection():
    rng = random.Random(42)
    selector = Selector(rng=rng)

    ind1 = Individual(sequence=PassSequence(passes=["mem2reg"]), fitness=50.0)
    ind2 = Individual(sequence=PassSequence(passes=["gvn"]), fitness=100.0)
    ind3 = Individual(sequence=PassSequence(passes=["licm"]), fitness=150.0)

    selected = selector.tournament_select([ind1, ind2, ind3], k=2)
    assert selected in [ind1, ind2, ind3]
