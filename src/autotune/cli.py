"""
Command Line Interface (CLI) for Autotune using Typer and Rich console formatting.
"""

import json
import os
import sys
import tempfile
import time
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel

from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import (
    ExitCodeAndStdoutStderrValidator,
    NumericToleranceValidator,
)
from autotune.config import CredentialStore
from autotune.doctor import run_doctor_checks
from autotune.analysis import FeatureExtractor
from autotune.llm import get_llm_client
from autotune.llvm import CompilerDriver, PipelineBuilder
from autotune.llvm.passes import PassSequence
from autotune.reporting.manifest import ExperimentManifestExporter
from autotune.reporting.report import SearchReport
from autotune.ui import SearchDashboard, print_banner, print_diagnose_summary, print_doctor_report, print_search_results_summary


from autotune import __version__
from autotune.sandbox import SandboxExecutor
from autotune.search import GeneticAlgorithmEngine, SearchProgressStats, PersistentCacheManager
from autotune.stress import BatchStressTestOrchestrator

app = typer.Typer(
    name="autotune",
    help="AI-Guided LLVM Phase-Ordering CLI Doctor for C/C++ Workloads",
    add_completion=False,
)
console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"autotune {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Show program version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
):
    """
    AI-Guided LLVM Phase-Ordering CLI Doctor for C/C++ Workloads
    """
    pass


@app.command()
def doctor():
    """Run system diagnostics for LLVM, Clang, Opt, Python, and hardware backend environment."""
    report = run_doctor_checks()
    print_doctor_report(report)


@app.command()
def config(
    provider: str = typer.Option("openai", "--provider", help="LLM Provider [openai|anthropic|gemini]"),
    api_key: str = typer.Option(..., "--api-key", prompt=True, hide_input=True, help="API Key for LLM provider"),
):
    """Store LLM API key securely in system keyring or local configuration."""
    print_banner()
    CredentialStore.set_api_key(provider, api_key)
    console.print(f"[bold green]Successfully stored API key for provider '{provider}'.[/bold green]")


@app.command()
def diagnose(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to workload input file"),
):
    """Analyze C/C++ source kernel AST, loop structures, and benchmark baseline -O3 execution."""
    if not os.path.exists(source):
        console.print(f"[bold red]Error: Source file '{source}' not found.[/bold red]")
        raise typer.Exit(code=1)

    doc_report = run_doctor_checks()
    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "baseline.bin")
        compile_res = compiler.compile_baseline(source, base_bin, opt_level="-O3")

        if not compile_res.success:
            console.print(f"[bold red]Baseline compilation failed: {compile_res.error_message}[/bold red]")
            raise typer.Exit(code=1)

        runner = get_performance_runner()
        bench_res = runner.run_benchmark(base_bin, workload_path=workload)

        if not bench_res.success:
            console.print(f"[bold red]Baseline benchmark execution failed: {bench_res.error_message}[/bold red]")
            raise typer.Exit(code=1)

        print_diagnose_summary(source, doc_report, baseline_result=bench_res)


@app.command()
def search(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to workload input file"),
    args: Optional[str] = typer.Option(None, "--args", help="Space-separated command-line arguments passed via argv"),
    # Search Options
    generations: int = typer.Option(5, "--generations", "-g", help="GA generation count"),
    population: int = typer.Option(10, "--population", "-p", help="GA population size"),
    seed: Optional[int] = typer.Option(42, "--seed", "-s", help="Random seed for deterministic search"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume experiment run state from snapshot ID"),
    early_stop: Optional[int] = typer.Option(None, "--early-stop", help="Stop search early if no improvement after N stagnant generations"),
    time_budget: Optional[float] = typer.Option(None, "--time-budget", help="Maximum wall-clock search time limit in seconds"),
    workers: int = typer.Option(4, "--workers", help="Number of parallel evaluation workers"),
    # Benchmarking Options
    warmup: int = typer.Option(3, "--warmup", help="Number of warmup runs per benchmark"),
    runs: int = typer.Option(10, "--runs", "-r", help="Number of measured benchmark runs"),
    fidelity: str = typer.Option("HIGH", "--fidelity", help="Multi-fidelity level [low|medium|high]"),
    screen_runs: int = typer.Option(3, "--screen-runs", help="Repetitions for LOW fidelity screening"),
    confirm_runs: int = typer.Option(20, "--confirm-runs", help="Repetitions for HIGH fidelity confirmation"),
    # Caching Options
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Enable or disable persistent multi-layer caching"),
    fresh: bool = typer.Option(False, "--fresh", help="Invalidate all experiment compilation, correctness, and performance caches"),
    fresh_benchmark: bool = typer.Option(False, "--fresh-benchmark", help="Reuse compilation/correctness, but force fresh timing measurements"),
    # Optimization & Baseline Gate Options
    baseline_gate: bool = typer.Option(True, "--baseline-gate/--no-baseline-gate", help="Screen non-promising candidates at LOW fidelity"),
    fail_on_regression: bool = typer.Option(False, "--fail-on-regression", help="Exit non-zero if confirmed winner regresses beyond threshold"),
    regression_threshold: float = typer.Option(0.05, "--regression-threshold", help="Regression tolerance threshold (e.g. 0.05 for 5%)"),
    # LLM & Correctness Options
    llm: Optional[bool] = typer.Option(None, "--llm/--no-llm", help="Explicitly enable or disable LLM candidate seeding"),
    provider: str = typer.Option("openai", "--provider", help="LLM Provider [openai|anthropic|gemini]"),
    correctness_strategy: str = typer.Option("exitcode", "--correctness-strategy", help="Strategy [exitcode|numeric|filedigest|custom]"),
    output_json: Optional[str] = typer.Option(None, "--output-json", "-o", help="Path to export structured JSON search report"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Non-interactive quiet mode for CI logging"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging"),
):
    """Run AI-guided genetic algorithm search for optimal LLVM pass pipelines with multi-layer caching."""
    if not os.path.exists(source):
        console.print(f"[bold red]Error: Source file '{source}' not found.[/bold red]")
        raise typer.Exit(code=2)

    api_key = CredentialStore.get_api_key(provider)
    use_llm_mode = False

    if llm is True:
        if not api_key:
            console.print(f"[bold red][ERROR] --llm requested but no API key found for provider '{provider}'.[/bold red]")
            console.print("[yellow]Run 'autotune config' or set OPENAI_API_KEY / AUTOTUNE_LLM_API_KEY.[/yellow]")
            raise typer.Exit(code=2)
        use_llm_mode = True
    elif llm is False:
        use_llm_mode = False
    else:
        if api_key:
            use_llm_mode = True
            if verbose and not quiet:
                console.print(f"[dim][INFO] API key detected for provider '{provider}'. Running AI-guided search.[/dim]")
        else:
            use_llm_mode = False
            if not quiet:
                console.print("[dim][INFO] No LLM API key detected. Running offline heuristic search.[/dim]")

    doc_report = run_doctor_checks()
    if not doc_report.clang_ok:
        console.print(f"[bold red][ERROR] Clang compiler not found on system PATH.[/bold red]")
        raise typer.Exit(code=3)

    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    runner = get_performance_runner(
        platform_name=doc_report.os_name,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
        cpu_info=doc_report.cpu_info,
    )

    cache_mgr = PersistentCacheManager(
        enabled=cache,
        fresh_all=fresh,
        fresh_benchmark=fresh_benchmark,
    )

    extractor = FeatureExtractor(clang_path=doc_report.clang_path)
    features = extractor.extract_from_file(source)

    from autotune.analysis.profile import WorkloadProfiler
    profiler = WorkloadProfiler(clang_path=doc_report.clang_path)
    w_profile = profiler.profile_file(
        source_path=source,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
    )

    strat = ExitCodeAndStdoutStderrValidator()
    if correctness_strategy == "numeric":
        strat = NumericToleranceValidator()

    llm_client = get_llm_client(provider=provider, use_llm=use_llm_mode, api_key=api_key, validator=compiler.validator)
    seed_sequences = llm_client.generate_candidates(features, count=4)

    dashboard = None
    if not quiet:
        dashboard = SearchDashboard(
            total_generations=generations,
            source_filename=os.path.basename(source),
            use_llm=use_llm_mode,
        )
        dashboard.start()

    with tempfile.TemporaryDirectory() as tmpdir:
        base_bin = os.path.join(tmpdir, "baseline.bin")
        compiler.compile_baseline(source, base_bin, opt_level="-O3")

        executor = SandboxExecutor()
        base_exec = executor.execute(base_bin, workload_path=workload)
        base_bench = runner.run_benchmark(base_bin, workload_path=workload, repetitions=runs, warmup_runs=warmup)
        base_time = base_bench.metrics.median_time_ns if base_bench.metrics else 1.0

        engine = GeneticAlgorithmEngine(
            compiler=compiler,
            runner=runner,
            seed=seed,
            population_size=population,
            generations=generations,
            max_stagnant_generations=early_stop if early_stop else 10,
            max_search_time_seconds=time_budget,
            correctness_strategy=strat,
            max_workers=workers,
            cache_manager=cache_mgr,
            fresh_benchmark=fresh_benchmark,
            resume_exp_id=resume,
            fidelity=fidelity,
            screen_runs=screen_runs,
            confirm_runs=confirm_runs,
            baseline_gate=baseline_gate,
        )

        def on_progress(stats: SearchProgressStats) -> None:
            if dashboard:
                dashboard.update(stats)
            elif quiet:
                best_ms = f"{round(stats.best_fitness_ns / 1e6, 3)} ms" if stats.best_fitness_ns is not None else "N/A"
                spd = f"{stats.speedup_factor:.2f}x" if stats.speedup_factor is not None else "N/A"
                console.print(f"[Generation {stats.generation}/{stats.total_generations}] Best: {best_ms} | Speedup: {spd} | Valid: {stats.valid_candidates_count}")

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
        final_confirmation = None

        if best and best.is_valid and best.raw_time_ns:
            cand_bin = os.path.join(tmpdir, "winning_candidate.bin")
            compiler.compile_candidate(source, best.sequence, cand_bin)

            final_confirmation = engine.run_final_confirmation(
                winner=best,
                source_path=source,
                workload_path=workload,
                baseline_bin=base_bin,
                candidate_bin=cand_bin,
                confirm_runs=confirm_runs,
                warmup_runs=warmup,
            )

            from autotune.reporting.prescription import PrescriptionBuilder
            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="optimized_kernel.bin",
                pass_sequence=best.sequence,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time,
                candidate_time_ns=best.raw_time_ns,
            )
            print_search_results_summary(
                prescription=prescription,
                cache_hits=cache_mgr.cache_hits,
                cache_misses=cache_mgr.cache_misses,
            )

            # Regression Guard
            conf_speedup = final_confirmation.get("final_confirmation_speedup", 1.0)
            if fail_on_regression and conf_speedup < (1.0 - regression_threshold):
                console.print(f"\n[bold red][REGRESSION GUARD TRIGGERED] Confirmed speedup {conf_speedup}x regressed beyond threshold {(1.0 - regression_threshold):.2f}x![/bold red]")
                raise typer.Exit(code=1)

        else:
            console.print("\n[bold yellow]No valid candidates outperform baseline.[/bold yellow]")

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
        if not quiet:
            console.print(f"[dim]Run artifacts saved to {manifest_dir}/[/dim]")

        if output_json:
            report = SearchReport(
                source_path=source,
                workload_path=workload,
                doctor_report=doc_report,
                workload_profile=w_profile,
                baseline_result=base_bench,
                prescription=prescription,
                generations_searched=generations,
                population_size=population,
                seed=seed,
            )
            report.export_json(output_json)
            console.print(f"[green]Report exported to {output_json}[/green]")


@app.command()
def export(
    report_json: str = typer.Argument(..., help="Path to JSON search report file exported by autotune search"),
    output_dir: str = typer.Option("./autotune_prescription", "--output-dir", "-o", help="Output directory path for prescription assets"),
):
    """Export reproducible prescription scripts and manifests from a JSON search report."""
    if not os.path.exists(report_json):
        console.print(f"[bold red]Error: Report JSON file '{report_json}' not found.[/bold red]")
        raise typer.Exit(code=2)

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    prescription_data = data.get("prescription")
    if not prescription_data:
        console.print(f"[bold yellow]Warning: No prescription data found in report JSON '{report_json}'.[/bold yellow]")
        raise typer.Exit(code=2)

    os.makedirs(output_dir, exist_ok=True)
    
    txt_path = os.path.join(output_dir, "prescription.txt")
    sh_path = os.path.join(output_dir, "reproduce.sh")
    json_path = os.path.join(output_dir, "prescription.json")

    cmd = prescription_data.get("reproducible_clang_command", "")
    passes = prescription_data.get("pass_sequence", {}).get("passes", [])

    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("AUTOTUNE COMPILER PRESCRIPTION\n")
        f.write("==============================\n")
        f.write(f"Source Path:     {data.get('source_path', 'N/A')}\n")
        f.write(f"Speedup Ratio:   {prescription_data.get('speedup_ratio', 1.0)}x\n")
        f.write(f"Pass Sequence:   {passes}\n\n")
        f.write("Reproducible Compiler Command:\n")
        f.write(f"{cmd}\n")

    with open(sh_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("# Autotune Reproducible Build Script\n")
        f.write("set -euo pipefail\n\n")
        f.write(f"echo 'Building optimized binary with pass sequence: {passes}'\n")
        f.write(f"{cmd}\n")
        f.write("echo 'Build complete: optimized_kernel.bin created.'\n")

    os.chmod(sh_path, 0o755)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(prescription_data, f, indent=2)

    console.print(f"[bold green]Successfully exported prescription assets to directory '{output_dir}/':[/bold green]")
    console.print(f"  - [cyan]{txt_path}[/cyan] (Text summary)")
    console.print(f"  - [cyan]{sh_path}[/cyan] (Executable build script)")
    console.print(f"  - [cyan]{json_path}[/cyan] (JSON metadata)")


@app.command(name="bench-suite")
def bench_suite(
    suite_dir: str = typer.Argument(..., help="Directory containing workload kernel source files"),
    population: int = typer.Option(20, "--population", "-p", help="GA population size"),
    generations: int = typer.Option(10, "--generations", "-g", help="GA generation count"),
    seed: Optional[int] = typer.Option(42, "--seed", "-s", help="Random seed for deterministic offline search"),
    fresh_benchmark: bool = typer.Option(False, "--fresh-benchmark", help="Force fresh timing measurements for bench suite"),
    output_report: str = typer.Option("stress_test_report.json", "--output-report", "-o", help="Path to export stress test report JSON"),
    workers: int = typer.Option(4, "--workers", help="Number of parallel worker processes"),
):
    """Run aggressive batch stress testing across a directory of C/C++ benchmark kernels."""
    if not os.path.exists(suite_dir):
        console.print(f"[bold red]Error: Benchmark suite directory '{suite_dir}' not found.[/bold red]")
        raise typer.Exit(code=1)

    print_banner()
    console.print(f"[bold cyan]Starting Batch Stress Testing on suite directory: {suite_dir}[/bold cyan]\n")

    orchestrator = BatchStressTestOrchestrator(
        population_size=population,
        generations=generations,
        seed=seed,
        max_workers=workers,
    )

    report = orchestrator.run_suite(suite_dir=suite_dir, output_report_path=output_report)

    console.print(f"\n[bold green]Batch Stress Testing Completed![/bold green]")
    console.print(f"Total Workloads Tested: [bold white]{report.total_workloads}[/bold white]")
    console.print(f"Successful Speedups:    [bold green]{report.successful_speedups}[/bold green]")
    console.print(f"Statistical Regressions:[bold yellow]{report.statistical_regressions}[/bold yellow]")
    console.print(f"Compiler Crashes:       [bold red]{report.compiler_crashes}[/bold red]")
    console.print(f"Infinite Timeouts:      [bold red]{report.infinite_compile_timeouts}[/bold red]")
    console.print(f"Silent Miscompilations: [bold red]{report.silent_miscompilations}[/bold red]")
    console.print(f"\nOverall Suite Speedup:  [bold magenta]{report.overall_suite_speedup}x[/bold magenta]")
    console.print(f"Report exported to:     [bold cyan]{output_report}[/bold cyan]\n")


@app.command()
def explain(
    target: str = typer.Argument(..., help="Comma-separated LLVM pass sequence string or JSON search report filepath"),
):
    """Inspect and explain the optimization semantics and expected impact of an LLVM pass pipeline."""
    from autotune.reporting.explain import PipelineInspector
    from rich.table import Table

    passes_list: List[str] = []
    if os.path.exists(target) and target.endswith(".json"):
        with open(target, "r", encoding="utf-8") as f:
            data = json.load(f)
        passes_list = data.get("prescription", {}).get("pass_sequence", {}).get("passes", [])
    else:
        passes_list = [p.strip() for p in target.replace(",", " ").split() if p.strip()]

    if not passes_list:
        console.print(f"[bold red]Error: No valid LLVM passes provided to explain.[/bold red]")
        raise typer.Exit(code=2)

    seq = PassSequence(passes=passes_list)
    inspector = PipelineInspector()
    explanations = inspector.explain(seq)

    table = Table(title="LLVM Pass Pipeline Explanation & Optimization Domains", border_style="cyan")
    table.add_column("Pass Name", style="bold white")
    table.add_column("Optimization Domain", style="bold cyan")
    table.add_column("Description", style="white")
    table.add_column("Expected Impact", style="bold green")

    for exp in explanations:
        table.add_row(exp.pass_name, exp.domain, exp.description, exp.expected_impact)

    console.print(table)


@app.command()
def knowledge(
    action: str = typer.Argument("list", help="Action: list or inspect"),
):
    """Inspect local cross-run optimization memory stored in SQLite KnowledgeStore."""
    from autotune.knowledge.store import KnowledgeStore
    from rich.table import Table

    store = KnowledgeStore()
    records = store.list_records()

    if not records:
        console.print("[dim]No historical optimization knowledge records stored yet.[/dim]")
        return

    table = Table(title="Autotune Cross-Run Optimization Memory Records", border_style="cyan")
    table.add_column("ID", style="dim")
    table.add_column("Filename", style="bold white")
    table.add_column("Architecture", style="cyan")
    table.add_column("Speedup", style="bold green")
    table.add_column("Classification", style="yellow")
    table.add_column("Winning Pipeline", style="bold magenta")

    for r in records:
        pipe_str = " → ".join(r.winning_pipeline)
        table.add_row(
            str(r.id),
            r.source_filename,
            r.architecture,
            f"{r.speedup_ratio}x",
            r.classification,
            pipe_str,
        )

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
