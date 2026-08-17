"""
Genetic Algorithm Engine orchestrating compiler pass pipeline search.
"""

import os
import random
import tempfile
from typing import Callable, List, Optional
from pydantic import BaseModel

from autotune.benchmark import PerformanceRunner, get_performance_runner
from autotune.benchmark.correctness import CorrectnessValidator
from autotune.benchmark.models import BenchmarkResult
from autotune.llvm.compiler import CompilerDriver
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.sandbox.executor import SandboxExecutionResult
from autotune.search.fitness import FitnessEvaluator
from autotune.search.individual import Individual
from autotune.search.mutation import Mutator
from autotune.search.population import Population
from autotune.search.selection import Selector


class SearchProgressStats(BaseModel):
    generation: int
    total_generations: int
    best_fitness_ns: Optional[float]
    baseline_fitness_ns: Optional[float]
    speedup_factor: Optional[float]
    valid_candidates_count: int


class GeneticAlgorithmEngine:
    """Orchestrates Genetic Algorithm pass optimization search."""

    def __init__(
        self,
        compiler: CompilerDriver,
        runner: PerformanceRunner,
        seed: Optional[int] = None,
        population_size: int = 20,
        generations: int = 40,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.7,
    ):
        self.compiler = compiler
        self.runner = runner
        self.seed = seed
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.validator = compiler.validator
        self.mutator = Mutator(validator=self.validator, rng=self.rng)
        self.selector = Selector(rng=self.rng)
        self.correctness_validator = CorrectnessValidator()

    def initialize_population(
        self, initial_sequences: List[PassSequence]
    ) -> Population:
        """Seed population with LLM proposals and mutated variants."""
        individuals: List[Individual] = []
        for seq in initial_sequences:
            individuals.append(Individual(sequence=seq))

        # Fill remaining population with mutated variations of initial seeds
        base_pool = list(initial_sequences) if initial_sequences else [PassSequence(passes=["mem2reg", "gvn"])]
        while len(individuals) < self.population_size:
            parent = self.rng.choice(base_pool)
            mutated = self.mutator.mutate(parent, mutation_rate=1.0)
            individuals.append(Individual(sequence=mutated))

        return Population(generation=0, individuals=individuals[: self.population_size])

    def evaluate_individual(
        self,
        individual: Individual,
        source_path: str,
        workload_path: Optional[str],
        baseline_res: SandboxExecutionResult,
        output_dir: str,
    ) -> Individual:
        cand_bin = os.path.join(output_dir, f"cand_{abs(hash(individual.sequence.serialize()))}.bin")
        compile_res = self.compiler.compile_candidate(source_path, individual.sequence, cand_bin)

        if not compile_res.success:
            return FitnessEvaluator.evaluate(individual, compile_res, None, None)

        bench_res = self.runner.run_benchmark(cand_bin, workload_path=workload_path)

        # Validate correctness
        cand_exec_res = SandboxExecutionResult(
            success=bench_res.success,
            stdout=bench_res.stdout,
            stderr=bench_res.stderr,
            exit_code=bench_res.exit_code,
        )
        correctness_res = self.correctness_validator.validate(baseline_res, cand_exec_res)

        return FitnessEvaluator.evaluate(individual, compile_res, correctness_res, bench_res)

    def evolve(
        self,
        source_path: str,
        workload_path: Optional[str],
        baseline_res: SandboxExecutionResult,
        baseline_time_ns: float,
        initial_sequences: List[PassSequence],
        callback: Optional[Callable[[SearchProgressStats], None]] = None,
    ) -> Population:
        """Run complete GA search loop over generations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            pop = self.initialize_population(initial_sequences)

            for gen in range(self.generations):
                pop.generation = gen

                # Evaluate un-evaluated individuals
                for ind in pop.individuals:
                    if ind.fitness is None:
                        self.evaluate_individual(ind, source_path, workload_path, baseline_res, tmpdir)

                pop.sort_individuals()
                best = pop.best_individual()

                if callback:
                    best_ns = best.fitness if best else None
                    speedup = (baseline_time_ns / best_ns) if (best_ns and best_ns > 0) else None
                    valid_cnt = sum(1 for ind in pop.individuals if ind.is_valid)
                    stats = SearchProgressStats(
                        generation=gen + 1,
                        total_generations=self.generations,
                        best_fitness_ns=best_ns,
                        baseline_fitness_ns=baseline_time_ns,
                        speedup_factor=speedup,
                        valid_candidates_count=valid_cnt,
                    )
                    callback(stats)

                if gen == self.generations - 1:
                    break

                # Produce next generation
                new_individuals: List[Individual] = []
                elites = self.selector.get_elites(pop.individuals, n=2)
                for e in elites:
                    new_individuals.append(Individual(sequence=e.sequence, fitness=e.fitness))

                while len(new_individuals) < self.population_size:
                    p1 = self.selector.tournament_select(pop.individuals, k=3)
                    p2 = self.selector.tournament_select(pop.individuals, k=3)

                    if self.rng.random() < self.crossover_rate and len(p1.sequence.passes) > 1 and len(p2.sequence.passes) > 1:
                        pt1 = self.rng.randint(0, len(p1.sequence.passes))
                        pt2 = self.rng.randint(0, len(p2.sequence.passes))
                        child_seq = p1.sequence.crossover(p2.sequence, pt1, pt2)
                    else:
                        child_seq = p1.sequence

                    child_seq = self.mutator.mutate(child_seq, mutation_rate=self.mutation_rate)
                    new_individuals.append(Individual(sequence=child_seq))

                pop.individuals = new_individuals[: self.population_size]

            return pop
