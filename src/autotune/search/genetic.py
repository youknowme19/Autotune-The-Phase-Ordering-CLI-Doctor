"""
Genetic Algorithm Engine orchestrating compiler pass pipeline search with persistent multi-layer caching,
baseline-normalized fitness, multi-fidelity screening, final confirmation, and seed archive reuse.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import math
import os
import random
import statistics
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Set
from pydantic import BaseModel

from autotune.benchmark import PerformanceRunner
from autotune.benchmark.correctness import CorrectnessStrategy, CorrectnessValidator
from autotune.benchmark.models import BenchmarkResult
from autotune.llvm.compiler import CompilerDriver, CompilationResult
from autotune.llvm.passes import PassSequence, CanonicalPassNormalizer
from autotune.sandbox.executor import SandboxExecutionResult
from autotune.search.fitness import FitnessEvaluator
from autotune.search.individual import Individual
from autotune.search.mutation import Mutator
from autotune.search.persistent_cache import PersistentCacheManager
from autotune.search.population import Population
from autotune.search.selection import Selector
from autotune.search.seeds import SeedArchiveManager


class SearchProgressStats(BaseModel):
    generation: int
    total_generations: int
    best_fitness_ns: Optional[float]
    baseline_fitness_ns: Optional[float]
    speedup_factor: Optional[float]
    valid_candidates_count: int
    unique_candidates_count: int = 0
    duplicate_suppression_count: int = 0
    persistent_compilation_cache_hits: int = 0
    persistent_correctness_cache_hits: int = 0
    persistent_performance_cache_hits: int = 0
    actual_compilations: int = 0
    actual_benchmark_executions: int = 0
    screened_low_count: int = 0
    promoted_medium_count: int = 0
    promoted_high_count: int = 0
    early_stop_triggered: bool = False
    stop_reason: Optional[str] = None


class GeneticAlgorithmEngine:
    """Orchestrates Genetic Algorithm pass optimization search with multi-layer persistent caching and invariants."""

    def __init__(
        self,
        compiler: CompilerDriver,
        runner: PerformanceRunner,
        seed: Optional[int] = None,
        population_size: int = 20,
        generations: int = 40,
        mutation_rate: float = 0.3,
        crossover_rate: float = 0.7,
        elite_count: int = 2,
        max_stagnant_generations: int = 10,
        max_search_time_seconds: Optional[float] = None,
        correctness_strategy: Optional[CorrectnessStrategy] = None,
        max_workers: int = 4,
        cache_manager: Optional[PersistentCacheManager] = None,
        fresh_benchmark: bool = False,
        resume_exp_id: Optional[str] = None,
        fidelity: str = "HIGH",
        screen_runs: int = 3,
        confirm_runs: int = 20,
        baseline_gate: bool = True,
        baseline_gate_threshold: float = 0.80,
    ):
        self.compiler = compiler
        self.runner = runner
        self.seed = seed
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.elite_count = max(1, elite_count)
        self.max_stagnant_generations = max_stagnant_generations
        self.max_search_time_seconds = max_search_time_seconds
        self.max_workers = max_workers
        self.fresh_benchmark = fresh_benchmark
        self.resume_exp_id = resume_exp_id

        self.fidelity = fidelity.upper()
        self.screen_runs = screen_runs
        self.confirm_runs = confirm_runs
        self.baseline_gate = baseline_gate
        self.baseline_gate_threshold = baseline_gate_threshold

        self.cache_mgr = cache_manager or PersistentCacheManager(
            fresh_benchmark=fresh_benchmark
        )
        self.seed_mgr = SeedArchiveManager()

        self.rng = random.Random(seed) if seed is not None else random.Random()
        self.validator = compiler.validator
        self.mutator = Mutator(validator=self.validator, rng=self.rng)
        self.selector = Selector(rng=self.rng)
        self.correctness_validator = CorrectnessValidator(strategy=correctness_strategy)
        self.correctness_strategy_name = correctness_strategy.__class__.__name__ if correctness_strategy else "ExitCodeAndStdoutStderrValidator"

        self.session_eval_cache: Dict[str, Individual] = {}
        self.screened_low_count: int = 0
        self.promoted_medium_count: int = 0
        self.promoted_high_count: int = 0

    def get_sequence_hash(self, sequence: PassSequence) -> str:
        canonical_str = sequence.to_canonical_opt_string()
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def initialize_population(
        self, initial_sequences: List[PassSequence]
    ) -> Population:
        """Construct hybrid initial population (20% LLVM defaults, 20% seed archive, 20% conservative, 20% heuristics, 20% random)."""
        individuals: List[Individual] = []
        seen_hashes: Set[str] = set()

        # Load valid historical seeds from .autotune/seeds/
        arch = getattr(self.compiler, "target_arch", "arm64")
        hist_seeds = self.seed_mgr.load_valid_seeds(target_architecture=arch, compiler_id=self.compiler.clang_path)

        hybrid_pool: List[PassSequence] = list(initial_sequences) if initial_sequences else []
        for hs in hist_seeds:
            hybrid_pool.append(PassSequence(passes=hs))

        # Known generic LLVM optimization patterns
        hybrid_pool.extend([
            PassSequence(passes=["mem2reg", "instcombine", "gvn"]),
            PassSequence(passes=["mem2reg", "sroa", "loop-rotate", "instcombine"]),
            PassSequence(passes=["reassociate", "inline", "mem2reg", "instcombine", "loop-simplify", "indvars"]),
            PassSequence(passes=["mem2reg", "sccp", "dce", "memcpyopt", "gvn"]),
            PassSequence(passes=["canon-freeze", "mem2reg", "loop-reduce", "inline"]),
        ])

        for seq in hybrid_pool:
            norm_seq = self.mutator.normalize(seq)
            h = self.get_sequence_hash(norm_seq)
            if h not in seen_hashes:
                seen_hashes.add(h)
                individuals.append(Individual(sequence=norm_seq))
                if len(individuals) >= self.population_size:
                    break

        base_pool = list(hybrid_pool) if hybrid_pool else [PassSequence(passes=["mem2reg", "instcombine"])]
        while len(individuals) < self.population_size:
            parent = self.rng.choice(base_pool)
            mutated = self.mutator.mutate(parent, mutation_rate=1.0)
            h = self.get_sequence_hash(mutated)
            if h not in seen_hashes or len(individuals) > self.population_size // 2:
                seen_hashes.add(h)
                individuals.append(Individual(sequence=mutated))

        return Population(generation=0, individuals=individuals[: self.population_size])

    def evaluate_individual(
        self,
        individual: Individual,
        source_path: str,
        workload_path: Optional[str],
        baseline_res: SandboxExecutionResult,
        baseline_time_ns: float,
        output_dir: str,
    ) -> Individual:
        seq_hash = self.get_sequence_hash(individual.sequence)

        # 1. Session memory lookup
        if seq_hash in self.session_eval_cache:
            self.cache_mgr.metrics.in_memory_memoization_hits += 1
            return self.session_eval_cache[seq_hash]

        with open(source_path, "r", encoding="utf-8") as f:
            source_content = f.read()
        workload_content = None
        if workload_path and os.path.exists(workload_path):
            with open(workload_path, "r", encoding="utf-8") as f:
                workload_content = f.read()

        canonical_pipe = individual.canonical_pipeline

        # Compute separate cache keys
        comp_key = self.cache_mgr.compute_compilation_key(
            source_content=source_content,
            canonical_pipeline=canonical_pipe,
            compiler_path=self.compiler.clang_path,
            compiler_version=self.compiler.clang_version or "clang",
            opt_version=self.compiler.opt_version or "opt",
            target_arch=getattr(self.compiler, "target_arch", "arm64"),
            os_name="Darwin",
        )

        corr_key = self.cache_mgr.compute_correctness_key(
            compilation_key=comp_key,
            correctness_strategy=self.correctness_strategy_name,
            workload_content=workload_content,
        )

        # Multi-Fidelity Repetition Parameters
        if self.fidelity == "LOW":
            warmup_r, measure_r = 2, self.screen_runs
        elif self.fidelity == "MEDIUM":
            warmup_r, measure_r = 3, 7
        else:  # HIGH
            warmup_r, measure_r = 5, self.confirm_runs

        perf_key = self.cache_mgr.compute_performance_key(
            compilation_key=comp_key,
            workload_content=workload_content,
            measurement_backend=getattr(self.runner, "platform_name", "auto"),
            warmup_runs=warmup_r,
            repetitions=measure_r,
        )

        # A. Check Compilation Cache
        cached_bin = self.cache_mgr.get_compilation(comp_key)
        if cached_bin and os.path.exists(cached_bin):
            cand_bin = cached_bin
            compile_success = True
        else:
            cand_bin = os.path.join(output_dir, f"cand_{seq_hash[:12]}.bin")
            compile_res = self.compiler.compile_candidate(source_path, individual.sequence, cand_bin)
            compile_success = compile_res.success
            self.cache_mgr.metrics.actual_compilations += 1
            if compile_success:
                cand_bin = self.cache_mgr.put_compilation(comp_key, cand_bin)
            else:
                evaluated = FitnessEvaluator.evaluate(individual, compile_res, None, None, baseline_time_ns)
                self.session_eval_cache[seq_hash] = evaluated
                return evaluated

        # B. Check Correctness Cache
        cached_corr = self.cache_mgr.get_correctness(corr_key)
        if cached_corr is not None:
            is_correct = cached_corr.get("is_correct", True)
            reason = cached_corr.get("reason", "")
        else:
            b_exec = baseline_res
            cand_exec_res = self.runner.run_benchmark(cand_bin, workload_path=workload_path, repetitions=1, warmup_runs=0)
            c_exec = SandboxExecutionResult(
                success=cand_exec_res.success,
                stdout=cand_exec_res.stdout,
                stderr=cand_exec_res.stderr,
                exit_code=cand_exec_res.exit_code,
            )
            val_res = self.correctness_validator.validate(b_exec, c_exec)
            is_correct = val_res.is_correct
            reason = val_res.reason
            self.cache_mgr.put_correctness(corr_key, {"is_correct": is_correct, "reason": reason})

        if not is_correct:
            individual.compilation_success = True
            individual.correctness_success = False
            individual.fitness = float("-inf")
            individual.normalized_speed = 0.0
            individual.error_message = reason or "Correctness check failed"
            self.session_eval_cache[seq_hash] = individual
            return individual

        # C. Check Performance Cache & Multi-Fidelity Measurement
        cached_perf = self.cache_mgr.get_performance(perf_key)
        if cached_perf is not None:
            samples = cached_perf.get("samples_ns", [])
            median_ns = cached_perf.get("median_time_ns", baseline_time_ns)
            exec_m = ExecutionMetrics(
                samples_ns=samples,
                median_time_ns=median_ns,
                mean_time_ns=median_ns,
                min_time_ns=median_ns,
                max_time_ns=median_ns,
                stddev_time_ns=0.0,
                noise_ratio=0.0,
            )
            meta_m = getattr(self.runner, "env_metadata", None)
            if meta_m is None:
                from autotune.benchmark.models import BenchmarkEnvironmentMetadata
                meta_m = BenchmarkEnvironmentMetadata(
                    platform="Darwin", architecture="arm64", compiler_version="clang",
                    measurement_backend="timing", cpu_info="cpu", sample_count=len(samples), noise_ratio=0.0
                )
            bench_res = BenchmarkResult(success=True, metrics=exec_m, metadata=meta_m)
            individual.is_cached_timing = True

        else:
            bench_res = self.runner.run_benchmark(
                cand_bin, workload_path=workload_path, repetitions=measure_r, warmup_runs=warmup_r
            )
            self.cache_mgr.metrics.actual_benchmark_executions += 1
            if bench_res and bench_res.success and bench_res.metrics:
                self.cache_mgr.put_performance(perf_key, {
                    "median_time_ns": bench_res.metrics.median_time_ns,
                    "samples_ns": bench_res.metrics.samples_ns,
                })

        evaluated = FitnessEvaluator.evaluate(
            individual,
            CompilationResult(success=True),
            val_res if "val_res" in locals() else None,
            bench_res,
            baseline_time_ns=baseline_time_ns,
        )

        evaluated.fidelity = self.fidelity

        # Baseline Gate Screening
        if self.baseline_gate and evaluated.normalized_speed is not None:
            if evaluated.normalized_speed < self.baseline_gate_threshold:
                evaluated.screened = True
                self.screened_low_count += 1

        self.session_eval_cache[seq_hash] = evaluated
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
        """Run GA optimization with elite preservation, multi-fidelity screening, and resumable state snapshots."""
        search_start_t = time.perf_counter()
        best_fitness_ever: Optional[float] = None
        stagnant_generations = 0
        early_stop_triggered = False

        start_gen = 0
        pop = self.initialize_population(initial_sequences)

        exp_dir = os.path.join(os.getcwd(), ".autotune", "experiments")
        os.makedirs(exp_dir, exist_ok=True)
        resume_file = os.path.join(exp_dir, f"{self.resume_exp_id}.json") if self.resume_exp_id else None

        if resume_file and os.path.exists(resume_file):
            try:
                with open(resume_file, "r", encoding="utf-8") as f:
                    state_data = json.load(f)
                start_gen = state_data.get("generation", 0) + 1
                best_fitness_ever = state_data.get("best_fitness_ever")
                stagnant_generations = state_data.get("stagnant_generations", 0)
                parsed_inds = [
                    Individual(
                        sequence=PassSequence.deserialize(item["sequence"]),
                        fitness=item.get("fitness"),
                        normalized_speed=item.get("normalized_speed"),
                        raw_time_ns=item.get("raw_time_ns"),
                        compilation_success=item.get("compilation_success", True),
                        correctness_success=item.get("correctness_success", True),
                    )
                    for item in state_data.get("population", [])
                ]
                if parsed_inds:
                    pop = Population(generation=start_gen, individuals=parsed_inds)
            except Exception:
                pass

        with tempfile.TemporaryDirectory() as tmpdir:
            for gen in range(start_gen, self.generations):
                pop.generation = gen

                unevaluated = [ind for ind in pop.individuals if ind.fitness is None]
                if unevaluated:
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        futures = {
                            executor.submit(
                                self.evaluate_individual, ind, source_path, workload_path, baseline_res, baseline_time_ns, tmpdir
                            ): ind
                            for ind in unevaluated
                        }
                        evaluated_map = {}
                        for future in as_completed(futures):
                            orig_ind = futures[future]
                            res_ind = future.result()
                            evaluated_map[id(orig_ind)] = res_ind

                        pop.individuals = [
                            evaluated_map.get(id(ind), ind) if ind.fitness is None else ind
                            for ind in pop.individuals
                        ]

                for ind in pop.individuals:
                    assert ind.fitness is not None and ind.is_evaluated, (
                        f"Invariant Violated: Candidate {ind.sequence} fitness is None after evaluation!"
                    )

                pop.sort_individuals()
                best = pop.best_individual()

                stop_reason = None
                best_ns = best.raw_time_ns if (best and best.raw_time_ns) else None
                best_speed = best.normalized_speed if best else None

                if best_speed is not None:
                    if best_fitness_ever is None or best_speed > (best_fitness_ever + 1e-4):
                        best_fitness_ever = best_speed
                        stagnant_generations = 0
                    else:
                        stagnant_generations += 1

                if self.max_stagnant_generations and stagnant_generations >= self.max_stagnant_generations:
                    stop_reason = f"Plateau reached ({stagnant_generations} stagnant generations)"
                    early_stop_triggered = True

                elapsed_s = time.perf_counter() - search_start_t
                if self.max_search_time_seconds and elapsed_s >= self.max_search_time_seconds:
                    stop_reason = f"Search timeout reached ({round(elapsed_s, 1)}s)"

                if callback:
                    valid_cnt = sum(1 for ind in pop.individuals if ind.is_valid)
                    unique_hashes = len({self.get_sequence_hash(ind.sequence) for ind in pop.individuals})
                    stats = SearchProgressStats(
                        generation=gen + 1,
                        total_generations=self.generations,
                        best_fitness_ns=best_ns,
                        baseline_fitness_ns=baseline_time_ns,
                        speedup_factor=best_speed,
                        valid_candidates_count=valid_cnt,
                        unique_candidates_count=unique_hashes,
                        duplicate_suppression_count=self.population_size - unique_hashes,
                        persistent_compilation_cache_hits=self.cache_mgr.metrics.persistent_compilation_cache_hits,
                        persistent_correctness_cache_hits=self.cache_mgr.metrics.persistent_correctness_cache_hits,
                        persistent_performance_cache_hits=self.cache_mgr.metrics.persistent_performance_cache_hits,
                        actual_compilations=self.cache_mgr.metrics.actual_compilations,
                        actual_benchmark_executions=self.cache_mgr.metrics.actual_benchmark_executions,
                        screened_low_count=self.screened_low_count,
                        early_stop_triggered=early_stop_triggered,
                        stop_reason=stop_reason,
                    )
                    callback(stats)

                if stop_reason or gen == self.generations - 1:
                    break

                # Next Generation Selection & Elite Preservation
                new_individuals: List[Individual] = []
                elites = self.selector.get_elites(pop.individuals, n=self.elite_count)
                for e in elites:
                    new_individuals.append(Individual(
                        sequence=e.sequence,
                        fitness=e.fitness,
                        raw_time_ns=e.raw_time_ns,
                        normalized_speed=e.normalized_speed,
                    ))

                unique_ratio = len({self.get_sequence_hash(ind.sequence) for ind in pop.individuals}) / self.population_size
                effective_mutation_rate = self.mutation_rate * (1.5 if unique_ratio < 0.5 else 1.0)

                seen_hashes: Set[str] = {self.get_sequence_hash(e.sequence) for e in elites}
                while len(new_individuals) < self.population_size:
                    p1 = self.selector.tournament_select(pop.individuals, k=3)
                    p2 = self.selector.tournament_select(pop.individuals, k=3)

                    if self.rng.random() < self.crossover_rate and len(p1.sequence.passes) > 1 and len(p2.sequence.passes) > 1:
                        pt1 = self.rng.randint(0, len(p1.sequence.passes))
                        pt2 = self.rng.randint(0, len(p2.sequence.passes))
                        child_seq = p1.sequence.crossover(p2.sequence, pt1, pt2)
                    else:
                        child_seq = p1.sequence

                    child_seq = self.mutator.mutate(child_seq, mutation_rate=effective_mutation_rate)
                    child_hash = self.get_sequence_hash(child_seq)

                    if child_hash not in seen_hashes or len(new_individuals) > self.population_size // 2:
                        seen_hashes.add(child_hash)
                        new_individuals.append(Individual(sequence=child_seq))

                pop.individuals = new_individuals[: self.population_size]

            return pop

    def run_final_confirmation(
        self,
        winner: Individual,
        source_path: str,
        workload_path: Optional[str],
        baseline_bin: str,
        candidate_bin: str,
        confirm_runs: int = 20,
        warmup_runs: int = 5,
    ) -> Dict[str, Any]:
        """Execute independent Final Confirmation Protocol using fresh baseline and winner measurements."""
        winner.confirmed = True

        b_bench = self.runner.run_benchmark(baseline_bin, workload_path=workload_path, repetitions=confirm_runs, warmup_runs=warmup_runs)
        c_bench = self.runner.run_benchmark(candidate_bin, workload_path=workload_path, repetitions=confirm_runs, warmup_runs=warmup_runs)

        b_ns = b_bench.metrics.samples_ns if (b_bench and b_bench.metrics) else []
        c_ns = c_bench.metrics.samples_ns if (c_bench and c_bench.metrics) else []

        b_med = round(b_bench.metrics.median_time_ns / 1e6, 3) if b_bench and b_bench.metrics else 0.0
        c_med = round(c_bench.metrics.median_time_ns / 1e6, 3) if c_bench and c_bench.metrics else 0.0

        b_mean = round(b_bench.metrics.mean_time_ns / 1e6, 3) if b_bench and b_bench.metrics else 0.0
        c_mean = round(c_bench.metrics.mean_time_ns / 1e6, 3) if c_bench and c_bench.metrics else 0.0

        b_std = round(b_bench.metrics.stddev_time_ns / 1e6, 3) if b_bench and b_bench.metrics else 0.0
        c_std = round(c_bench.metrics.stddev_time_ns / 1e6, 3) if c_bench and c_bench.metrics else 0.0

        speedup = round(b_med / c_med, 2) if c_med > 0 else 1.0

        # Welch's t-test
        n1, n2 = len(b_ns), len(c_ns)
        m1, m2 = statistics.mean(b_ns), statistics.mean(c_ns)
        v1, v2 = statistics.variance(b_ns), statistics.variance(c_ns)
        se = math.sqrt(v1/n1 + v2/n2) if (n1 > 0 and n2 > 0) else 1.0
        t_stat = (m1 - m2) / se if se > 0 else 0.0
        df = ((v1/n1 + v2/n2)**2) / (((v1/n1)**2)/(n1-1) + ((v2/n2)**2)/(n2-1)) if se > 0 else 1.0
        p_val_welch = math.erfc(abs(t_stat) / math.sqrt(2)) if se > 0 else 1.0

        # Mann-Whitney U test
        u1 = 0.0
        for x in b_ns:
            for y in c_ns:
                if x > y:
                    u1 += 1.0
                elif x == y:
                    u1 += 0.5
        mean_u = (n1 * n2) / 2.0
        std_u = math.sqrt((n1 * n2 * (n1 + n2 + 1)) / 12.0)
        z_u = (u1 - mean_u) / std_u if std_u > 0 else 0.0
        p_val_mwu = 0.5 * math.erfc(abs(z_u) / math.sqrt(2))

        # Save to Seed Archive if confirmed speedup
        if speedup > 1.0 and p_val_welch < 0.05:
            self.seed_mgr.save_seed(
                pipeline=winner.sequence.passes,
                source_workload_id=os.path.basename(source_path),
                compiler_id=self.compiler.clang_path,
                llvm_version=getattr(self.compiler, "clang_version", "LLVM 22.1"),
                architecture=getattr(self.compiler, "target_arch", "arm64"),
                target_info="macOS arm64",
                observed_normalized_speed=speedup,
                correctness_status="PASS",
                confirmation_status="CONFIRMED",
            )

        return {
            "baseline_samples_ms": [round(s / 1e6, 3) for s in b_ns],
            "candidate_samples_ms": [round(s / 1e6, 3) for s in c_ns],
            "baseline_median_ms": b_med,
            "candidate_median_ms": c_med,
            "baseline_mean_ms": b_mean,
            "candidate_mean_ms": c_mean,
            "baseline_stddev_ms": b_std,
            "candidate_stddev_ms": c_std,
            "final_confirmation_speedup": speedup,
            "welch_t_stat": round(t_stat, 4),
            "welch_df": round(df, 1),
            "welch_p_value": p_val_welch,
            "mann_whitney_u": round(u1, 1),
            "mann_whitney_p_value": p_val_mwu,
            "timing_stability_warning": (c_bench.metrics.timing_stability_warning if c_bench and c_bench.metrics else False),
        }
