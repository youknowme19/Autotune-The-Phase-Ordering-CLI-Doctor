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
def status():
    """Display Autotune system status, toolchain availability, cache footprint, and KnowledgeStore memory records."""
    report = run_doctor_checks()

    from autotune.knowledge.store import KnowledgeStore
    k_store = KnowledgeStore()
    records_cnt = len(k_store.list_records())

    cache_dir = os.path.join(os.getcwd(), ".autotune", "cache")
    cache_cnt = len([f for f in os.listdir(cache_dir) if f.endswith(".json")]) if os.path.exists(cache_dir) else 0

    from rich.table import Table
    table = Table(title="Autotune System & Environment Status", border_style="cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Status / Value", style="bold green")

    table.add_row("Autotune Version", f"v{__version__}")
    table.add_row("Python Environment", f"{report.python_version} ({'OK' if report.python_ok else 'FAIL'})")
    table.add_row("Clang Compiler", f"{report.clang_version or 'N/A'} ({'OK' if report.clang_ok else 'FAIL'})")
    table.add_row("Opt Binary", f"{report.opt_version or 'N/A'} ({'OK' if report.opt_ok else 'FAIL'})")
    table.add_row("Target Architecture", report.arch)
    table.add_row("Measurement Backend", report.measurement_backend)
    table.add_row("Knowledge Memory Records", f"{records_cnt} entries")
    table.add_row("Cached Candidate Binaries", f"{cache_cnt} entries")

    console.print(table)


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


@app.command()
def bundle(
    report_json: str = typer.Argument(..., help="Path to JSON search report file exported by autotune search"),
    output_dir: str = typer.Option("./autotune_reproducibility_bundle", "--output-dir", "-b", help="Output directory path for self-contained research bundle"),
):
    """Create a self-contained research reproduction bundle for scientific papers and bug reports."""
    if not os.path.exists(report_json):
        console.print(f"[bold red]Error: Search report JSON '{report_json}' not found.[/bold red]")
        raise typer.Exit(code=2)

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    os.makedirs(output_dir, exist_ok=True)

    from autotune.environment.fingerprint import EnvironmentFingerprinter
    fp = EnvironmentFingerprinter.capture()

    # Save environment fingerprint
    with open(os.path.join(output_dir, "environment.json"), "w", encoding="utf-8") as f:
        json.dump(fp.model_dump(), f, indent=2)

    # Save search report data
    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    p_data = data.get("prescription", {})
    cmd = p_data.get("reproducible_clang_command", "clang -O3")
    passes = p_data.get("pass_sequence", {}).get("passes", [])

    # Save reproducible script
    sh_path = os.path.join(output_dir, "reproduce.sh")
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("# Autotune Research Reproduction Script\n")
        f.write("set -euo pipefail\n\n")
        f.write(f"echo 'Rebuilding optimized binary with pass sequence: {passes}'\n")
        f.write(f"{cmd}\n")
        f.write("echo 'Build complete.'\n")
    os.chmod(sh_path, 0o755)

    # Save README
    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Autotune Research Reproduction Bundle\n\n")
        f.write(f"**Source File:** `{data.get('source_path', 'N/A')}`  \n")
        f.write(f"**Speedup Ratio:** **{p_data.get('speedup_ratio', 1.0)}x**  \n")
        f.write(f"**Environment Fingerprint:** `{fp.fingerprint_hash}` ({fp.os_name} {fp.architecture})  \n\n")
        f.write("## Reproduce Command\n```bash\n./reproduce.sh\n```\n")

    console.print(f"[bold green]Successfully created research reproduction bundle in directory '{output_dir}/':[/bold green]")
    console.print(f"  - [cyan]{output_dir}/environment.json[/cyan] (System & compiler fingerprint)")
    console.print(f"  - [cyan]{output_dir}/manifest.json[/cyan] (Full experiment manifest)")
    console.print(f"  - [cyan]{output_dir}/reproduce.sh[/cyan] (Executable build script)")
    console.print(f"  - [cyan]{output_dir}/README.md[/cyan] (Reproduction summary)")


@app.command()
def cache(
    action: str = typer.Argument("status", help="Action: status or clear"),
):
    """Inspect or manage the persistent compilation and benchmark result cache."""
    cache_dir = os.path.join(os.getcwd(), ".autotune", "cache")

    if action == "clear":
        if os.path.exists(cache_dir):
            import shutil
            shutil.rmtree(cache_dir)
            console.print("[bold green]Persistent benchmark cache successfully cleared.[/bold green]")
        else:
            console.print("[dim]Cache directory is already empty.[/dim]")
        return

    # Default action: status
    if not os.path.exists(cache_dir):
        console.print("[dim]Persistent cache directory does not exist yet.[/dim]")
        return

    files = [f for f in os.listdir(cache_dir) if f.endswith(".json")]
    total_bytes = sum(os.path.getsize(os.path.join(cache_dir, f)) for f in files)
    console.print(f"Cache Location: [bold cyan]{cache_dir}[/bold cyan]")
    console.print(f"Cached Candidates: [bold green]{len(files)}[/bold green]")
    console.print(f"Total Storage: [bold yellow]{round(total_bytes / 1024, 1)} KB[/bold yellow]")


@app.command()
def gate(
    report_json: str = typer.Argument(..., help="Path to JSON search report file exported by autotune search"),
    min_speedup: float = typer.Option(1.05, "--min-speedup", "-m", help="Minimum required speedup ratio for CI gate to pass"),
):
    """CI Performance Gate: Evaluates search report against minimum required speedup threshold."""
    if not os.path.exists(report_json):
        console.print(f"[bold red]Error: Search report JSON '{report_json}' not found.[/bold red]")
        raise typer.Exit(code=2)

    with open(report_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    p_data = data.get("prescription", {})
    speedup = p_data.get("speedup_ratio", 1.0)
    classification = p_data.get("classification", "NO_SIGNIFICANT_CHANGE")

    console.print(f"Evaluating CI Performance Gate for report: [cyan]{report_json}[/cyan]")
    console.print(f"Target Speedup Threshold: [bold yellow]{min_speedup}x[/bold yellow]")
    console.print(f"Observed Speedup:         [bold green]{speedup}x[/bold green]")
    console.print(f"Result Classification:    [bold cyan]{classification}[/bold cyan]")

    if speedup >= min_speedup and classification == "IMPROVED":
        console.print("[bold green]✓ CI PERFORMANCE GATE PASSED: Speedup meets target threshold.[/bold green]")
    else:
        console.print(f"[bold red]✗ CI PERFORMANCE GATE FAILED: Speedup {speedup}x is below required {min_speedup}x target.[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def compare(
    report_a: str = typer.Argument(..., help="Path to first JSON search report file (Baseline / Previous Run)"),
    report_b: str = typer.Argument(..., help="Path to second JSON search report file (Candidate / Optimized Run)"),
):
    """Compare two optimization search reports side-by-side."""
    from autotune.services.compare import CompareService
    try:
        res = CompareService.compare_reports(report_a, report_b)
        from rich.table import Table
        table = Table(title="Autotune Optimization Search Comparison", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("Report A (Baseline)", style="yellow")
        table.add_column("Report B (Candidate)", style="green")
        table.add_column("Differential", style="bold magenta")

        table.add_row("Speedup Ratio", f"{res.speedup_a}x", f"{res.speedup_b}x", f"{'+' if res.speedup_diff >= 0 else ''}{res.speedup_diff}x")
        table.add_row("Classification", res.classification_a, res.classification_b, "N/A")
        table.add_row("Evidence Grade", res.evidence_grade_a, res.evidence_grade_b, "N/A")
        table.add_row("Passes Count", str(res.passes_count_a), str(res.passes_count_b), "N/A")

        console.print(table)
        console.print(f"[bold cyan]{res.summary}[/bold cyan]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=2)


@app.command()
def report(
    report_json: str = typer.Argument(..., help="Path to JSON search report file exported by autotune search"),
    html: str = typer.Option("./autotune_report.html", "--html", "-h", help="Output path for standalone HTML report"),
):
    """Generate a standalone, zero-dependency offline HTML report from a JSON search report."""
    from autotune.services.report import ReportService
    try:
        out_path = ReportService.render_html_report(report_json, html)
        console.print(f"[bold green]Successfully generated standalone HTML report: [cyan]{out_path}[/cyan][/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=2)


@app.command()
def optimize(
    source: str = typer.Argument(..., help="Path to C/C++ source file to optimize"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Optional stdin workload file path"),
    args: Optional[str] = typer.Option(None, "--args", help="Space-separated binary command-line arguments"),
    time_budget: int = typer.Option(30, "--time-budget", "-t", help="Search time budget limit in seconds"),
    seed: int = typer.Option(42, "--seed", "-s", help="Random seed for deterministic search"),
    output_dir: Optional[str] = typer.Option(None, "--output", "-o", help="Output directory for prescription, report, and bundle assets"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Enable quiet mode for CI logging"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose debug logging"),
):
    """Flagship Command: Orchestrate complete end-to-end workload optimization, evidence grading, HTML report, and prescription export."""
    from autotune.services.optimize import OptimizeService
    try:
        res = OptimizeService.run(
            source=source,
            workload=workload,
            args=args,
            time_budget=time_budget,
            seed=seed,
            output_dir=output_dir,
            quiet=quiet,
        )
        if not quiet:
            console.print(f"\n[bold green]✓ Optimization Workflow Complete![/bold green]")
            console.print(f"  - Run ID:        [bold cyan]{res.run_id}[/bold cyan]")
            console.print(f"  - Speedup Ratio: [bold yellow]{res.speedup_ratio}x[/bold yellow] ({res.classification})")
            console.print(f"  - Evidence:      [bold green]Grade {res.evidence_grade}[/bold green]")
            console.print(f"  - Report JSON:   [cyan]{res.report_json_path}[/cyan]")
            console.print(f"  - Offline HTML:  [cyan]{res.report_html_path}[/cyan]\n")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def validate(
    quick: bool = typer.Option(False, "--quick", help="Run fast validation harness with small search budgets"),
):
    """Validation Harness: Run curated example benchmarks and report empirical timing and speedup metrics."""
    from autotune.services.validate import ValidateService
    res = ValidateService.run_validation(quick=quick)

    from rich.table import Table
    table = Table(title="Autotune Curated Benchmark Validation Harness", border_style="cyan")
    table.add_column("Benchmark Workload", style="bold white")
    table.add_column("Baseline (-O3)", style="yellow")
    table.add_column("Optimized", style="green")
    table.add_column("Speedup", style="bold magenta")
    table.add_column("Evidence", style="cyan")
    table.add_column("Correctness", style="bold green")

    for item in res.items:
        b_ms = f"{round(item.baseline_ms, 2)} ms" if item.baseline_ms > 0 else "N/A"
        c_ms = f"{round(item.candidate_ms, 2)} ms" if item.candidate_ms > 0 else "N/A"
        table.add_row(item.workload, b_ms, c_ms, f"{item.speedup}x", f"Grade {item.evidence_grade}", item.correctness)

    console.print(table)


# --- Runs Subcommand Group ---
runs_app = typer.Typer(help="Manage local Autotune run directories and search artifacts.")
app.add_typer(runs_app, name="runs")


@runs_app.command("list")
def runs_list():
    """List all saved Autotune optimization runs under .autotune/runs/."""
    runs_dir = os.path.join(os.getcwd(), ".autotune", "runs")
    if not os.path.exists(runs_dir):
        console.print("[dim]No optimization runs found.[/dim]")
        return

    subdirs = [d for d in os.listdir(runs_dir) if os.path.isdir(os.path.join(runs_dir, d))]
    from rich.table import Table
    table = Table(title="Saved Autotune Optimization Runs", border_style="cyan")
    table.add_column("Run ID", style="bold cyan")
    table.add_column("Path", style="dim")

    for sd in sorted(subdirs, reverse=True):
        table.add_row(sd, os.path.join(runs_dir, sd))

    console.print(table)


@runs_app.command("clean")
def runs_clean():
    """Clean all saved run directories from .autotune/runs/."""
    runs_dir = os.path.join(os.getcwd(), ".autotune", "runs")
    if os.path.exists(runs_dir):
        import shutil
        shutil.rmtree(runs_dir, ignore_errors=True)
        console.print("[bold green]Successfully cleaned all saved run directories.[/bold green]")
    else:
        console.print("[dim]No runs directory to clean.[/dim]")


def main():
    app()


if __name__ == "__main__":
    main()
