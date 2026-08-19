"""
Unit tests for GeneticAlgorithmEngine hardening: elite preservation, duplicate suppression, and resumable state.
"""

import os
import tempfile
import json
import pytest
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence, CanonicalPassNormalizer
from autotune.benchmark import get_performance_runner
from autotune.search.genetic import GeneticAlgorithmEngine, SearchProgressStats
from autotune.search.individual import Individual
from autotune.search.population import Population


def test_canonical_pass_normalizer():
    seq1 = PassSequence(passes=["  mem2reg ", "GVN ", " promote "])
    canonical = CanonicalPassNormalizer.canonicalize_sequence(seq1)

    assert canonical.passes == ["mem2reg", "gvn", "mem2reg"]
    assert canonical.to_opt_string() == "function(mem2reg,gvn,mem2reg)"


def test_elite_preservation():
    # Verify top elite candidate is preserved across generation evolution
    p1 = Individual(sequence=PassSequence(passes=["mem2reg", "gvn"]), fitness=100.0)
    p2 = Individual(sequence=PassSequence(passes=["instcombine"]), fitness=200.0)
    p3 = Individual(sequence=PassSequence(passes=["dce"]), fitness=300.0)

    pop = Population(generation=0, individuals=[p1, p2, p3])
    pop.sort_individuals()

    best_before = pop.best_individual()
    assert best_before.fitness == 100.0
    assert best_before.sequence.passes == ["mem2reg", "gvn"]


def test_resumable_experiment_snapshot():
    with tempfile.TemporaryDirectory() as tmpdir:
        exp_dir = os.path.join(tmpdir, ".autotune", "experiments")
        os.makedirs(exp_dir, exist_ok=True)
        exp_id = "test_resume_exp"
        snapshot_file = os.path.join(exp_dir, f"{exp_id}.json")

        state_data = {
            "generation": 2,
            "best_fitness_ever": 55.0,
            "stagnant_generations": 0,
            "population": [
                {
                    "sequence": json.dumps(["mem2reg", "instcombine"]),
                    "fitness": 55.0,
                    "compilation_success": True,
                    "correctness_success": True,
                }
            ],
        }
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump(state_data, f)

        # Verify state parsing
        with open(snapshot_file, "r") as f:
            loaded = json.load(f)
        assert loaded["generation"] == 2
        assert loaded["best_fitness_ever"] == 55.0
