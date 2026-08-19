"""
End-to-end integration test verifying multi-layer persistent cache hits, fresh-benchmark bypass, and accounting consistency.
"""

import os
import shutil
import tempfile
import pytest

from autotune.doctor import run_doctor_checks
from autotune.llvm import CompilerDriver
from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import CorrectnessStrategy, CorrectnessResult
from autotune.sandbox import SandboxExecutionResult, SandboxExecutor
from autotune.search import GeneticAlgorithmEngine, PersistentCacheManager



class AlwaysCorrectStrategy(CorrectnessStrategy):
    def verify(self, baseline_res: SandboxExecutionResult, candidate_res: SandboxExecutionResult) -> CorrectnessResult:
        return CorrectnessResult(is_correct=True, reason="AlwaysCorrect")



def test_cache_end_to_end_runs_a_b_c():
    source_path = os.path.abspath("examples/matrix_transpose/kernel.c")
    workload_path = os.path.abspath("examples/matrix_transpose/input.txt")

    if not os.path.exists(source_path):
        pytest.skip("matrix_transpose source kernel missing")

    strat = AlwaysCorrectStrategy()

    with tempfile.TemporaryDirectory() as cache_dir:
        doc_report = run_doctor_checks()
        compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
        runner = get_performance_runner()

        with tempfile.TemporaryDirectory() as tmpdir:
            base_bin = os.path.join(tmpdir, "base.bin")
            compiler.compile_baseline(source_path, base_bin, opt_level="-O3")
            executor = SandboxExecutor()
            base_exec = executor.execute(base_bin, workload_path=workload_path)

            # --- RUN A: Initial Run (Cache Misses) ---
            cache_mgr_a = PersistentCacheManager(cache_dir=cache_dir, enabled=True, fresh_all=False, fresh_benchmark=False)
            engine_a = GeneticAlgorithmEngine(
                compiler=compiler,
                runner=runner,
                seed=42,
                population_size=4,
                generations=2,
                correctness_strategy=strat,
                cache_manager=cache_mgr_a,
                fidelity="LOW",
                screen_runs=2,
            )

            pop_a = engine_a.evolve(
                source_path=source_path,
                workload_path=workload_path,
                baseline_res=base_exec,
                baseline_time_ns=100.0,
                initial_sequences=[],
            )

            metrics_a = cache_mgr_a.metrics
            assert metrics_a.actual_compilations > 0, "Run A must compile new candidates"
            assert metrics_a.persistent_compilation_cache_hits == 0, "Run A must have 0 persistent compilation cache hits on empty cache"

            pop_sequences_a = [ind.sequence for ind in pop_a.individuals]

            # --- RUN B: Identical Configuration (Compilation & Correctness Hits) ---
            cache_mgr_b = PersistentCacheManager(cache_dir=cache_dir, enabled=True, fresh_all=False, fresh_benchmark=False)
            engine_b = GeneticAlgorithmEngine(
                compiler=compiler,
                runner=runner,
                seed=42,
                population_size=len(pop_sequences_a),
                generations=1,
                correctness_strategy=strat,
                cache_manager=cache_mgr_b,
                fidelity="LOW",
                screen_runs=2,
            )

            pop_b = engine_b.evolve(
                source_path=source_path,
                workload_path=workload_path,
                baseline_res=base_exec,
                baseline_time_ns=100.0,
                initial_sequences=pop_sequences_a,
            )

            metrics_b = cache_mgr_b.metrics
            assert metrics_b.persistent_compilation_cache_hits > 0, "Run B must reuse compilation cache artifacts"



            # --- RUN C: Fresh Benchmark Mode (--fresh-benchmark) ---
            cache_mgr_c = PersistentCacheManager(cache_dir=cache_dir, enabled=True, fresh_all=False, fresh_benchmark=True)
            engine_c = GeneticAlgorithmEngine(
                compiler=compiler,
                runner=runner,
                seed=42,
                population_size=len(pop_sequences_a),
                generations=1,
                correctness_strategy=strat,
                cache_manager=cache_mgr_c,
                fresh_benchmark=True,
                fidelity="LOW",
                screen_runs=2,
            )

            pop_c = engine_c.evolve(
                source_path=source_path,
                workload_path=workload_path,
                baseline_res=base_exec,
                baseline_time_ns=100.0,
                initial_sequences=pop_sequences_a,
            )


            metrics_c = cache_mgr_c.metrics
            assert metrics_c.persistent_compilation_cache_hits > 0, "Run C must reuse compilation artifacts"
            assert metrics_c.persistent_performance_cache_hits == 0, "Run C --fresh-benchmark must bypass performance cache"
            assert metrics_c.actual_benchmark_executions > 0, "Run C must execute fresh timing benchmarks"
