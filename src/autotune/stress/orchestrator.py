"""
Batch Stress Testing Orchestrator executing Autotune across benchmark suites.
"""

from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
import os
import glob
import tempfile
import time
from typing import List, Optional

from autotune.analysis import FeatureExtractor
from autotune.benchmark import get_performance_runner
from autotune.doctor import run_doctor_checks
from autotune.llm import get_llm_client
from autotune.llvm import CompilerDriver
from autotune.reporting.manifest import calculate_p_value
from autotune.sandbox import SandboxExecutor
from autotune.search import GeneticAlgorithmEngine
from autotune.stress.models import FailureCategory, KernelStressResult, StressTestReport


def run_single_kernel_stress(
    source_path: str,
    workload_path: Optional[str],
    population_size: int,
    generations: int,
    seed: Optional[int],
) -> KernelStressResult:
    """Worker task executing genetic algorithm optimization and stress checks on a single workload kernel."""
    kernel_name = os.path.basename(os.path.dirname(source_path)) if os.path.basename(source_path) == "kernel.c" else os.path.basename(source_path).replace(".c", "")
    doc_report = run_doctor_checks()
    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    runner = get_performance_runner(
        platform_name=doc_report.os_name,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
        cpu_info=doc_report.cpu_info,
    )

    extractor = FeatureExtractor(clang_path=doc_report.clang_path)
    features = extractor.extract_from_file(source_path)

    llm = get_llm_client(use_llm=False, validator=compiler.validator)
    seed_sequences = llm.generate_candidates(features=features, count=4)  # Offline heuristic

    miscompilations = 0
    crashes = 0
    timeouts = 0

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "baseline.bin")
        base_compile = compiler.compile_baseline(source_path, base_bin, opt_level="-O3")

        if not base_compile.success:
            return KernelStressResult(
                kernel_name=kernel_name,
                source_path=source_path,
                workload_path=workload_path,
                category=FailureCategory.COMPILER_CRASH,
                crash_count=1,
                details=f"Baseline compilation failed: {base_compile.error_message}",
            )

        executor = SandboxExecutor()
        base_exec = executor.execute(base_bin, workload_path=workload_path)
        base_bench = runner.run_benchmark(base_bin, workload_path=workload_path)
        base_time = base_bench.metrics.median_time_ns if (base_bench and base_bench.metrics) else 1.0

        engine = GeneticAlgorithmEngine(
            compiler=compiler,
            runner=runner,
            seed=seed,
            population_size=population_size,
            generations=generations,
        )

        pop = engine.evolve(
            source_path=source_path,
            workload_path=workload_path,
            baseline_res=base_exec,
            baseline_time_ns=base_time,
            initial_sequences=seed_sequences,
        )

        # Tally failure statistics across evaluated candidates
        for ind in pop.individuals:
            if not ind.compilation_success:
                crashes += 1
            elif not ind.correctness_success:
                miscompilations += 1

        best = pop.best_individual()
        if not best or not best.is_valid or best.fitness is None or best.fitness == float("inf"):
            category = FailureCategory.SILENT_MISCOMPILATION if miscompilations > 0 else FailureCategory.COMPILER_CRASH
            return KernelStressResult(
                kernel_name=kernel_name,
                source_path=source_path,
                workload_path=workload_path,
                category=category,
                miscompilation_count=miscompilations,
                crash_count=crashes,
                details="No valid candidate found in population.",
            )

        best_ms = round(best.fitness / 1e6, 3)
        b_ms = round(base_time / 1e6, 3)
        speedup = round(base_time / max(best.fitness, 1.0), 2)

        # Calculate Welch's t-test p-value
        b_samples = base_bench.metrics.samples_ns if (base_bench and base_bench.metrics) else [base_time]
        p_val = calculate_p_value(b_samples, [best.fitness] * len(b_samples))

        category = FailureCategory.PARITY
        if p_val < 0.05:
            if speedup > 1.0:
                category = FailureCategory.SUCCESSFUL_SPEEDUP
            elif speedup < 1.0:
                category = FailureCategory.STATISTICAL_REGRESSION

        return KernelStressResult(
            kernel_name=kernel_name,
            source_path=source_path,
            workload_path=workload_path,
            category=category,
            baseline_time_ms=b_ms,
            best_candidate_time_ms=best_ms,
            speedup_ratio=speedup,
            p_value=p_val,
            winning_passes=best.sequence.passes,
            miscompilation_count=miscompilations,
            crash_count=crashes,
            timeout_count=timeouts,
        )


class BatchStressTestOrchestrator:
    """Orchestrates execution of Autotune across a directory of workload kernels in parallel."""

    def __init__(self, population_size: int = 20, generations: int = 10, seed: Optional[int] = 42, max_workers: int = 4):
        self.population_size = population_size
        self.generations = generations
        self.seed = seed
        self.max_workers = max_workers

    def run_suite(self, suite_dir: str, output_report_path: str = "stress_test_report.json") -> StressTestReport:
        abs_suite_dir = os.path.abspath(suite_dir)
        c_files = glob.glob(os.path.join(abs_suite_dir, "**/*.c"), recursive=True)
        c_files = [f for f in c_files if not os.path.basename(f).startswith("._")]

        report = StressTestReport(
            timestamp=datetime.now().isoformat(),
            total_workloads=len(c_files),
        )

        tasks = []
        for c_file in c_files:
            base_no_ext = os.path.splitext(c_file)[0]
            dir_name = os.path.dirname(c_file)
            cands = [
                f"{base_no_ext}_input.txt",
                os.path.join(dir_name, "input.txt"),
                os.path.join(dir_name, f"{os.path.basename(base_no_ext)}_input.txt"),
            ]
            workload_path = None
            for cand in cands:
                if os.path.exists(cand):
                    workload_path = cand
                    break
            tasks.append((c_file, workload_path))

        results: List[KernelStressResult] = []
        if tasks:
            with ProcessPoolExecutor(max_workers=min(len(tasks), self.max_workers)) as executor:
                futures = {
                    executor.submit(
                        run_single_kernel_stress, c_file, w_path, self.population_size, self.generations, self.seed
                    ): c_file
                    for c_file, w_path in tasks
                }
                for future in as_completed(futures):
                    res = future.result()
                    results.append(res)

        report.results = results
        # Aggregate statistics
        for r in results:
            if r.category == FailureCategory.SUCCESSFUL_SPEEDUP:
                report.successful_speedups += 1
            elif r.category == FailureCategory.STATISTICAL_REGRESSION:
                report.statistical_regressions += 1
            elif r.category == FailureCategory.COMPILER_CRASH:
                report.compiler_crashes += 1
            elif r.category == FailureCategory.INFINITE_COMPILE_TIME:
                report.infinite_compile_timeouts += 1
            elif r.category == FailureCategory.SILENT_MISCOMPILATION:
                report.silent_miscompilations += 1
            elif r.category == FailureCategory.RUNTIME_TIMEOUT:
                report.runtime_timeouts += 1
            elif r.category == FailureCategory.PARITY:
                report.parities += 1

        if results:
            valid_speedups = [r.speedup_ratio for r in results if r.speedup_ratio > 0]
            report.overall_suite_speedup = round(sum(valid_speedups) / len(valid_speedups), 2) if valid_speedups else 1.0

        report.export_json(output_report_path)
        return report
