"""
Genetic Algorithm Engine orchestrating compiler pass pipeline search with parallel evaluation, memoization, and strict evaluation invariants.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import os
import random
import tempfile
import time
from typing import Callable, Dict, List, Optional
from pydantic import BaseModel

from autotune.benchmark import PerformanceRunner, get_performance_runner
from autotune.benchmark.correctness import CorrectnessStrategy, CorrectnessValidator, ExitCodeAndStdoutStderrValidator
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
    stop_reason: Optional[str] = None


class GeneticAlgorithmEngine:
    """Orchestrates Genetic Algorithm pass optimization search with parallel evaluation and invariants."""

    def __init__(
        self,
        compiler: CompilerDriver,
        runner: PerformanceRunner,
        seed: Optional[int] = None,
        population_size: int = 20,
        generations: int = 40,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.7,
        max_stagnant_generations: int = 10,
        max_search_time_seconds: Optional[float] = None,
        correctness_strategy: Optional[CorrectnessStrategy] = None,
        max_workers: int = 4,
    ):
        self.compiler = compiler
        self.runner = runner
        self.seed = seed
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.max_stagnant_generations = max_stagnant_generations
        self.max_search_time_seconds = max_search_time_seconds
        self.max_workers = max_workers

        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.validator = compiler.validator
        self.mutator = Mutator(validator=self.validator, rng=self.rng)
        self.selector = Selector(rng=self.rng)
        self.correctness_validator = CorrectnessValidator(strategy=correctness_strategy)

        # Candidate evaluation memoization cache (SHA-256 pipeline string -> evaluated Individual)
        self.eval_cache: Dict[str, Individual] = {}

    def get_sequence_hash(self, sequence: PassSequence) -> str:
        return hashlib.sha256(sequence.serialize().encode("utf-8")).hexdigest()

    def initialize_population(
        self, initial_sequences: List[PassSequence]
    ) -> Population:
        """Seed population with LLM proposals and mutated variants."""
        individuals: List[Individual] = []
        for seq in initial_sequences:
            norm_seq = self.mutator.normalize(seq)
            individuals.append(Individual(sequence=norm_seq))

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
        seq_hash = self.get_sequence_hash(individual.sequence)
        if seq_hash in self.eval_cache:
            return self.eval_cache[seq_hash]

        cand_bin = os.path.join(output_dir, f"cand_{seq_hash[:12]}.bin")
        compile_res = self.compiler.compile_candidate(source_path, individual.sequence, cand_bin)

        if not compile_res.success:
            evaluated = FitnessEvaluator.evaluate(individual, compile_res, None, None)
            self.eval_cache[seq_hash] = evaluated
            return evaluated

        bench_res = self.runner.run_benchmark(cand_bin, workload_path=workload_path)

        cand_exec_res = SandboxExecutionResult(
            success=bench_res.success,
            stdout=bench_res.stdout,
            stderr=bench_res.stderr,
            exit_code=bench_res.exit_code,
        )
        correctness_res = self.correctness_validator.validate(baseline_res, cand_exec_res)

        evaluated = FitnessEvaluator.evaluate(individual, compile_res, correctness_res, bench_res)
        self.eval_cache[seq_hash] = evaluated
        return evaluated

    def evolve(
        self,
        source_path: str,
        workload_path: Optional[str],
        baseline_res: SandboxExecutionResult,
        baseline_time_ns: float,
        initial_sequences: List[PassSequence],
        callback: Optional[Callable[[SearchProgressStats], None]] = None,
    ) -> Population:
        """Run complete GA search loop over generations with parallel evaluation and invariants."""
        search_start_t = time.perf_counter()
        best_fitness_ever: Optional[float] = None
        stagnant_generations = 0

        with tempfile.TemporaryDirectory() as tmpdir:
            pop = self.initialize_population(initial_sequences)

            for gen in range(self.generations):
                pop.generation = gen

                # Parallel evaluation of un-evaluated individuals
                unevaluated = [ind for ind in pop.individuals if ind.fitness is None]
                if unevaluated:
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        futures = {
                            executor.submit(
                                self.evaluate_individual, ind, source_path, workload_path, baseline_res, tmpdir
                            ): ind
                            for ind in unevaluated
                        }
                        evaluated_map = {}
                        for future in as_completed(futures):
                            orig_ind = futures[future]
                            res_ind = future.result()
                            evaluated_map[id(orig_ind)] = res_ind

                        # Reassign evaluated individuals explicitly back to pop.individuals
                        pop.individuals = [
                            evaluated_map.get(id(ind), ind) if ind.fitness is None else ind
                            for ind in pop.individuals
                        ]

                # Invariant Assertion: Ensure all individuals are evaluated with non-None fitness
                for ind in pop.individuals:
                    assert ind.fitness is not None and ind.is_evaluated, (
                        f"Invariant Violated: Candidate {ind.sequence} fitness is None after evaluation!"
                    )

                pop.sort_individuals()
                best = pop.best_individual()

                stop_reason = None
                best_ns = best.fitness if best else None

                if best_ns is not None:
                    if best_fitness_ever is None or best_ns < (best_fitness_ever - 1e-6):
                        best_fitness_ever = best_ns
                        stagnant_generations = 0
                    else:
                        stagnant_generations += 1

                if self.max_stagnant_generations and stagnant_generations >= self.max_stagnant_generations:
                    stop_reason = f"Plateau reached ({stagnant_generations} stagnant generations)"

                elapsed_s = time.perf_counter() - search_start_t
                if self.max_search_time_seconds and elapsed_s >= self.max_search_time_seconds:
                    stop_reason = f"Search timeout reached ({round(elapsed_s, 1)}s)"

                if callback:
                    speedup = (baseline_time_ns / best_ns) if (best_ns and best_ns > 0) else None
                    valid_cnt = sum(1 for ind in pop.individuals if ind.is_valid)
                    stats = SearchProgressStats(
                        generation=gen + 1,
                        total_generations=self.generations,
                        best_fitness_ns=best_ns,
                        baseline_fitness_ns=baseline_time_ns,
                        speedup_factor=speedup,
                        valid_candidates_count=valid_cnt,
                        stop_reason=stop_reason,
                    )
                    callback(stats)

                if stop_reason or gen == self.generations - 1:
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
