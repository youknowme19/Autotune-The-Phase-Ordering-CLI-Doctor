"""
Typer CLI application entry point for Autotune.
"""

import os
import tempfile
import time
from typing import Optional
import typer
from rich.console import Console

from autotune import __version__
from autotune.analysis import FeatureExtractor
from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import (
    CorrectnessValidator,
    CustomScriptValidator,
    ExitCodeAndStdoutStderrValidator,
    FileDigestValidator,
    NumericToleranceValidator,
)
from autotune.config import get_default_config
from autotune.doctor import run_doctor_checks
from autotune.llm import get_llm_client
from autotune.llvm import CompilerDriver, PassSequence
from autotune.reporting import PrescriptionBuilder, SearchReport
from autotune.reporting.manifest import ExperimentManifestExporter
from autotune.sandbox import SandboxExecutor
from autotune.search import GeneticAlgorithmEngine, SearchProgressStats
from autotune.ui import (
    SearchDashboard,
    console,
    print_banner,
    print_diagnose_summary,
    print_doctor_report,
    print_search_results_summary,
)

app = typer.Typer(
    name="autotune",
    help="AI-guided LLVM compiler optimization and phase-ordering doctor.",
    add_completion=False,
)


@app.command()
def doctor(
    clang_path: Optional[str] = typer.Option(None, "--clang", help="Custom path to clang binary"),
    opt_path: Optional[str] = typer.Option(None, "--opt", help="Custom path to opt binary"),
):
    """Validate installed LLVM compiler toolchain and diagnostic capabilities."""
    report = run_doctor_checks(custom_clang=clang_path, custom_opt=opt_path)
    print_doctor_report(report)
    if not report.is_healthy:
        raise typer.Exit(code=1)


@app.command()
def diagnose(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to workload input file"),
    clang_path: Optional[str] = typer.Option(None, "--clang", help="Custom path to clang binary"),
    opt_path: Optional[str] = typer.Option(None, "--opt", help="Custom path to opt binary"),
    repetitions: int = typer.Option(10, "--repetitions", "-r", help="Number of benchmark repetitions"),
):
    """Diagnose C/C++ source code, validate toolchain, and establish baseline -O3 performance."""
    if not os.path.exists(source):
        console.print(f"[bold red]Error: Source file '{source}' not found.[/bold red]")
        raise typer.Exit(code=1)

    if workload and not os.path.exists(workload):
        console.print(f"[bold red]Error: Workload file '{workload}' not found.[/bold red]")
        raise typer.Exit(code=1)

    doc_report = run_doctor_checks(custom_clang=clang_path, custom_opt=opt_path)
    if not doc_report.clang_ok:
        console.print("[bold red]Clang compiler toolchain check failed.[/bold red]")
        raise typer.Exit(code=1)

    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    runner = get_performance_runner(
        platform_name=doc_report.os_name,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
        cpu_info=doc_report.cpu_info,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        baseline_bin = os.path.join(tmpdir, "baseline_O3.bin")
        compile_res = compiler.compile_baseline(source, baseline_bin, opt_level="-O3")

        if not compile_res.success:
            console.print(f"[bold red]Baseline compilation failed: {compile_res.error_message}[/bold red]")
            raise typer.Exit(code=1)

        bench_res = runner.run_benchmark(
            baseline_bin, workload_path=workload, repetitions=repetitions
        )

        if not bench_res.success:
            console.print(f"[bold red]Baseline benchmark execution failed: {bench_res.error_message}[/bold red]")
            raise typer.Exit(code=1)

        print_diagnose_summary(source, doc_report, baseline_result=bench_res)


@app.command()
def search(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to workload input file"),
    generations: int = typer.Option(5, "--generations", "-g", help="GA generation count"),
    population: int = typer.Option(10, "--population", "-p", help="GA population size"),
    seed: Optional[int] = typer.Option(42, "--seed", "-s", help="Random seed for deterministic search"),
    use_llm: bool = typer.Option(False, "--llm/--no-llm", help="Enable LLM candidate proposal seeding"),
    provider: str = typer.Option("heuristic", "--provider", help="LLM Provider [openai|anthropic|gemini|heuristic]"),
    correctness_strategy: str = typer.Option("exitcode", "--correctness-strategy", help="Strategy [exitcode|numeric|filedigest|custom]"),
    output_json: Optional[str] = typer.Option(None, "--output-json", "-o", help="Path to export structured JSON search report"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """Run AI-guided genetic algorithm search for optimal LLVM pass pipelines."""
    if not os.path.exists(source):
        console.print(f"[bold red]Error: Source file '{source}' not found.[/bold red]")
        raise typer.Exit(code=1)

    doc_report = run_doctor_checks()
    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    runner = get_performance_runner(
        platform_name=doc_report.os_name,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
        cpu_info=doc_report.cpu_info,
    )

    extractor = FeatureExtractor(clang_path=doc_report.clang_path)
    features = extractor.extract_from_file(source)

    if verbose:
        console.print(f"[dim]Features extracted: {features.suggested_focus_areas}[/dim]")

    # Select correctness strategy
    strat = ExitCodeAndStdoutStderrValidator()
    if correctness_strategy == "numeric":
        strat = NumericToleranceValidator()

    llm = get_llm_client(provider=provider, use_llm=use_llm, validator=compiler.validator)
    seed_sequences = llm.generate_candidates(features, count=4)

    dashboard = SearchDashboard(total_generations=generations, source_filename=os.path.basename(source))
    dashboard.start()

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "baseline.bin")
        compiler.compile_baseline(source, base_bin, opt_level="-O3")

        executor = SandboxExecutor()
        base_exec = executor.execute(base_bin, workload_path=workload)
        base_bench = runner.run_benchmark(base_bin, workload_path=workload)
        base_time = base_bench.metrics.median_time_ns if base_bench.metrics else 1.0

        engine = GeneticAlgorithmEngine(
            compiler=compiler,
            runner=runner,
            seed=seed,
            population_size=population,
            generations=generations,
            correctness_strategy=strat,
        )

        def on_progress(stats: SearchProgressStats) -> None:
            dashboard.update(stats)

        pop = engine.evolve(
            source_path=source,
            workload_path=workload,
            baseline_res=base_exec,
            baseline_time_ns=base_time,
            initial_sequences=seed_sequences,
            callback=on_progress,
        )

        best = pop.best_individual()
        prescription = None
        if best and best.fitness:
            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="optimized_kernel.bin",
                pass_sequence=best.sequence,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time,
                candidate_time_ns=best.fitness,
            )
            print_search_results_summary(prescription)
        else:
            console.print("\n[bold yellow]No valid candidates outperform baseline.[/bold yellow]")

        # Export manifest run artifacts
        run_id = f"run_{int(time.time())}"
        manifest_dir = ExperimentManifestExporter.export_run(
            run_id=run_id,
            source_path=source,
            workload_path=workload,
            seed=seed,
            doc_report=doc_report,
            baseline_result=base_bench,
            candidates=pop.individuals,
            winning_individual=best,
            prescription=prescription,
        )
        console.print(f"[dim]Run artifacts saved to {manifest_dir}/[/dim]")

        if output_json:
            report = SearchReport(
                source_path=source,
                workload_path=workload,
                doctor_report=doc_report,
                baseline_result=base_bench,
                prescription=prescription,
                generations_searched=generations,
                population_size=population,
                seed=seed,
            )
            report.export_json(output_json)
            console.print(f"[green]Report exported to {output_json}[/green]")


@app.command()
def benchmark(
    binary: str = typer.Argument(..., help="Path to executable binary to benchmark"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to workload input file"),
    repetitions: int = typer.Option(10, "--repetitions", "-r", help="Number of repetitions"),
):
    """Run benchmark performance runner directly on an executable binary."""
    if not os.path.exists(binary):
        console.print(f"[bold red]Error: Binary '{binary}' not found.[/bold red]")
        raise typer.Exit(code=1)

    runner = get_performance_runner()
    res = runner.run_benchmark(binary, workload_path=workload, repetitions=repetitions)
    if res.success and res.metrics:
        b_ms = round(res.metrics.median_time_ns / 1e6, 3)
        console.print(f"[bold green]Benchmark Completed[/bold green]: Median {b_ms} ms (noise: {round(res.metrics.noise_ratio * 100, 2)}%)")
    else:
        console.print(f"[bold red]Benchmark Failed: {res.error_message}[/bold red]")


@app.command()
def validate(
    source: str = typer.Argument(..., help="Source C/C++ file"),
    candidate: str = typer.Argument(..., help="Candidate binary file"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Workload input file"),
):
    """Validate correctness of candidate binary against baseline -O3 execution."""
    compiler = CompilerDriver()
    validator = CorrectnessValidator()
    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "base.bin")
        compiler.compile_baseline(source, base_bin)
        executor = SandboxExecutor()
        b_res = executor.execute(base_bin, workload_path=workload)
        c_res = executor.execute(candidate, workload_path=workload)
        ver = validator.validate(b_res, c_res)
        if ver.is_correct:
            console.print("[bold green][VALID] Candidate output matches baseline output.[/bold green]")
        else:
            console.print(f"[bold red][INVALID] Correctness failed: {ver.reason}[/bold red]")


@app.command()
def report():
    """Display autotune diagnostic report and summary."""
    doc_report = run_doctor_checks()
    print_doctor_report(doc_report)


if __name__ == "__main__":
    app()
