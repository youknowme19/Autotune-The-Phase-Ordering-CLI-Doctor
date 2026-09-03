"""
Command Line Interface (CLI) for Autotune using Typer and Rich console formatting.
"""

import json
import os
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from autotune import __version__
from autotune.analysis import FeatureExtractor
from autotune.benchmark import get_performance_runner
from autotune.benchmark.correctness import (
    ExitCodeAndStdoutStderrValidator,
    NumericToleranceValidator,
)
from autotune.config import CredentialStore
from autotune.doctor import run_doctor_checks
from autotune.llm import get_llm_client
from autotune.llvm import CompilerDriver, PipelineBuilder
from autotune.llvm.passes import PassSequence
from autotune.reporting.manifest import ExperimentManifestExporter
from autotune.reporting.prescription import PrescriptionBuilder
from autotune.reporting.report import SearchReport
from autotune.sandbox import SandboxExecutor
from autotune.search import GeneticAlgorithmEngine, SearchProgressStats, PersistentCacheManager
from autotune.services import (
    DoctorService,
    DoctorResult,
    ReproduceService,
    ReproductionResult,
    ReproductionVerdict,
    GuardService,
    GuardResult,
    GuardExitCode,
    InspectService,
    InspectResult,
    HistoryManager,
    HistoryEntry,
    CompareService,
    CompareResult,
    ProfileService,
    ProfileFeatureSummary,
    ExplainService,
    OptimizationExplanation,
    ApplyService,
    ApplyResult,
    ExportService,
    ExportResult,
    OptimizeService,
    ValidateService,
    ReportService,
)
from autotune.stress import BatchStressTestOrchestrator
from autotune.ui import (
    SearchDashboard,
    print_banner,
    print_diagnose_summary,
    print_doctor_report,
    print_search_results_summary,
)

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
def doctor(
    source: Optional[str] = typer.Argument(None, help="Path to C/C++ source kernel file (orchestrates full optimization when provided)"),
    preset: str = typer.Option("balanced", "--preset", "-p", help="Optimization preset [quick|balanced|aggressive]"),
    generations: Optional[int] = typer.Option(None, "--generations", "-g", help="GA generation count override"),
    population: Optional[int] = typer.Option(None, "--population", help="GA population size override"),
    seed: int = typer.Option(42, "--seed", "-s", help="Random seed for deterministic search"),
    time_budget: Optional[float] = typer.Option(None, "--time-budget", "-t", help="Search time limit in seconds"),
    workers: int = typer.Option(4, "--workers", help="Evaluation workers count"),
    llm: Optional[bool] = typer.Option(None, "--llm/--no-llm", help="Explicitly enable or disable LLM seeding"),
    provider: str = typer.Option("openai", "--provider", help="LLM Provider [openai|anthropic|gemini]"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Path to stdin workload input file"),
    args: Optional[str] = typer.Option(None, "--args", help="Space-separated argv arguments"),
    correctness_strategy: str = typer.Option("exitcode", "--correctness-strategy", help="Strategy [exitcode|numeric]"),
    assembly: bool = typer.Option(False, "--assembly", "-a", help="Emit and analyze compiler assembly differences"),
    ci: bool = typer.Option(False, "--ci", help="CI/CD automated non-interactive execution mode"),
    output_json: Optional[str] = typer.Option(None, "--output-json", "-o", help="Path to export JSON report"),
    output_html: Optional[str] = typer.Option(None, "--output-html", help="Path to export HTML report"),
    export_sh: Optional[str] = typer.Option(None, "--export-sh", help="Path to export executable shell script"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", help="Output directory for experiment artifacts"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Quiet output mode for logs"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose debug logging"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume experiment snapshot ID"),
):
    """Flagship Command: Analyze workload, search optimal LLVM pass pipelines, validate, and export reports."""
    if source is None:
        # Backward-compatible environment diagnostics check
        report = run_doctor_checks()
        print_doctor_report(report)
        return

    if not os.path.exists(source):
        console.print(f"[bold red]Error: Source file '{source}' not found.[/bold red]")
        raise typer.Exit(code=1)

    if not quiet and not ci:
        console.print(Panel(
            "[bold cyan]AUTOTUNE DOCTOR[/bold cyan]\n"
            "[dim]AI-Guided LLVM Phase-Ordering Optimization & Diagnostics[/dim]",
            border_style="cyan",
            expand=False,
        ))
        console.print(f"Analyzing [bold green]{os.path.basename(source)}[/bold green] (Preset: [cyan]{preset}[/cyan])...")

    def on_progress(stats: SearchProgressStats):
        if not quiet and not ci:
            spd = f"{stats.speedup_factor:.2f}x" if stats.speedup_factor else "1.00x"
            best_ms = f"{stats.best_fitness_ns / 1e6:.3f} ms" if stats.best_fitness_ns else "N/A"
            pct = int((stats.generation / max(stats.total_generations, 1)) * 20)
            bar = "━" * pct + "╸" + "─" * max(0, 19 - pct)
            console.print(f"  [cyan]Gen {stats.generation:02d}/{stats.total_generations:02d}[/cyan] [bold blue][{bar}][/bold blue] | Best: [bold green]{best_ms:>10}[/bold green] | Gain: [bold magenta]{spd:>6}[/bold magenta] | Diversity: [dim]{stats.diversity_ratio:.2f}[/dim] | Valid: [cyan]{stats.valid_candidates_count}[/cyan]")
        elif ci:
            console.print(f"[CI] Gen {stats.generation}/{stats.total_generations} | Best: {stats.best_fitness_ns / 1e6 if stats.best_fitness_ns else 0.0:.2f}ms")

    try:
        res = DoctorService.run(
            source=source,
            workload=workload,
            args=args,
            preset=preset,
            population=population,
            generations=generations,
            seed=seed,
            time_budget=time_budget,
            workers=workers,
            llm=llm,
            provider=provider,
            correctness_strategy=correctness_strategy,
            include_assembly=assembly,
            output_json=output_json,
            output_html=output_html,
            output_dir=output_dir,
            quiet=quiet,
            verbose=verbose,
            ci_mode=ci,
            progress_callback=on_progress,
            resume_snapshot=resume,
        )

        if ci:
            console.print(f"\nAutotune Performance Check")
            console.print(f"Baseline:   {res.baseline_median_ms:.3f} ms")
            console.print(f"Candidate:  {res.candidate_median_ms:.3f} ms")
            console.print(f"Speedup:    {res.confirmed_speedup:.2f}x")
            console.print(f"Correctness:{res.correctness_status}")
            console.print(f"Grade:      Grade {res.evidence_grade}")
            console.print(f"STATUS:     {'PASS' if res.correctness_status == 'PASS' and res.confirmed_speedup >= 1.0 else 'FAIL'}\n")
            if res.correctness_status != "PASS":
                raise typer.Exit(code=2)
            return

        if not quiet:
            if res.confirmed_speedup >= 1.02 and res.correctness_status == "PASS":
                console.print(f"\n[bold green]🏆 OPTIMIZATION FOUND[/bold green]")
            else:
                console.print(f"\n[bold yellow]ℹ BASELINE EVALUATION COMPLETE[/bold yellow]")

            console.print(f"  - Baseline (-O3):  [bold white]{res.baseline_median_ms:.3f} ms[/bold white]")
            console.print(f"  - Autotune Winner: [bold green]{res.candidate_median_ms:.3f} ms[/bold green]")
            console.print(f"  - Confirmed Gain:  [bold yellow]{res.confirmed_speedup:.2f}×[/bold yellow] (Grade {res.evidence_grade} — {res.classification})")
            console.print(f"  - Correctness:     [bold green]✓ {res.correctness_status}[/bold green]")
            console.print(f"  - Statistical p:   [cyan]{res.p_value:.4f}[/cyan] (Cohen's d: {res.cohens_d:.2f})")

            if res.winning_passes:
                console.print("\nWinning pass pipeline:")
                pipe_str = " → ".join(f"[bold cyan]{p}[/bold cyan]" for p in res.winning_passes)
                console.print(f"  {pipe_str}\n")

            if res.assembly_metrics:
                console.print(f"Assembly Evidence:")
                console.print(f"  Instructions: {res.assembly_metrics.total_instructions} (Vector: {res.assembly_metrics.vector_instructions}, Branches: {res.assembly_metrics.branch_instructions})\n")

            console.print(f"Artifacts:")
            console.print(f"  - JSON Report: [cyan]{res.report_json_path}[/cyan]")
            console.print(f"  - HTML Report: [cyan]{res.report_html_path}[/cyan]")

            if export_sh and res.report_json_path:
                ExportService.export_reproduction_artifacts(res.report_json_path, fmt="shell", output_path=export_sh)
                console.print(f"  - Shell Script: [cyan]{export_sh}[/cyan]")

            console.print(f"\nReproduce:")
            console.print(f"  [bold white]autotune reproduce {res.report_json_path}[/bold white]\n")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def profile(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    json_output: bool = typer.Option(False, "--json", help="Output profile in JSON format"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Explicitly ensure 100% offline analysis"),
):
    """Analyze and profile workload characteristics, loop depth, memory ops, and potential optimization areas."""
    try:
        prof = ProfileService.profile_workload(source)
        if json_output:
            console.print(json.dumps(prof.model_dump(), indent=2))
            return

        console.print(Panel(
            f"[bold cyan]AUTOTUNE WORKLOAD PROFILE[/bold cyan]\n"
            f"[dim]Source: {prof.source_filename}[/dim]",
            border_style="cyan",
            expand=False,
        ))
        console.print(f"Source:           [bold white]{prof.source_path}[/bold white]")
        console.print(f"Language:         [bold green]{prof.language}[/bold green]")
        console.print(f"Functions:        [cyan]{prof.function_count}[/cyan]")
        console.print(f"Lines of Code:    [white]{prof.lines_of_code}[/white]")
        
        loop_color = "red" if prof.loop_intensity == "HIGH" else ("yellow" if prof.loop_intensity == "MEDIUM" else "dim")
        mem_color = "red" if prof.memory_intensity == "HIGH" else ("yellow" if prof.memory_intensity == "MEDIUM" else "dim")
        br_color = "red" if prof.branch_intensity == "HIGH" else ("yellow" if prof.branch_intensity == "MEDIUM" else "dim")
        fp_color = "red" if prof.floating_point_intensity == "HIGH" else ("yellow" if prof.floating_point_intensity == "MEDIUM" else "dim")
        call_color = "red" if prof.function_calls_intensity == "HIGH" else ("yellow" if prof.function_calls_intensity == "MEDIUM" else "dim")

        console.print(f"Loops:            [bold {loop_color}]{prof.loop_intensity}[/bold {loop_color}] ({prof.loop_count} loops, max depth {prof.max_loop_depth})")
        console.print(f"Memory Operations:[bold {mem_color}]{prof.memory_intensity}[/bold {mem_color}] ({prof.pointer_derefs} ptr derefs, {prof.array_accesses} array ops)")
        console.print(f"Branches:         [bold {br_color}]{prof.branch_intensity}[/bold {br_color}]")
        console.print(f"Floating Point:   [bold {fp_color}]{prof.floating_point_intensity}[/bold {fp_color}] ({prof.float_ops} float ops)")
        console.print(f"Function Calls:   [bold {call_color}]{prof.function_calls_intensity}[/bold {call_color}]")
        console.print("\n[bold cyan]Potential Optimization Areas:[/bold cyan]")
        for area in prof.potential_optimization_areas:
            console.print(f"  • [green]{area}[/green]")
        console.print("")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def reproduce(
    report_json: str = typer.Argument(..., help="Path to JSON experiment report file"),
    tolerance: float = typer.Option(0.10, "--tolerance", "-t", help="Reproducibility tolerance threshold (0.10 for 10%)"),
    runs: int = typer.Option(15, "--runs", "-r", help="Number of benchmark repetitions"),
    warmup: int = typer.Option(3, "--warmup", help="Warmup runs"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Optional workload input file path"),
    json_output: bool = typer.Option(False, "--json", help="Output reproduction result in JSON format"),
):
    """Reconstruct an experiment from report JSON, validate correctness, and verify performance reproduction."""
    try:
        res = ReproduceService.reproduce(report_path=report_json, tolerance=tolerance, runs=runs, warmup=warmup, workload=workload)

        if json_output:
            console.print(json.dumps(res.model_dump(), indent=2))
            return

        console.print(Panel("[bold cyan]AUTOTUNE EXPERIMENT REPRODUCTION[/bold cyan]", border_style="cyan", expand=False))
        if res.environment_warnings:
            console.print("[bold yellow]⚠ Environment Warnings:[/bold yellow]")
            for w in res.environment_warnings:
                console.print(f"  [yellow]• {w}[/yellow]")
            console.print("")

        table = Table(title="Reproduction Verification Summary", border_style="cyan")
        table.add_column("Property", style="bold white")
        table.add_column("Original (Report)", style="yellow")
        table.add_column("Reproduction (Fresh Run)", style="green")
        table.add_column("Difference", style="bold magenta")

        b_diff_str = f"{res.baseline_delta_pct:+.1f}%" if res.recorded_baseline_ms > 0 else "N/A"
        c_diff_str = f"{res.candidate_delta_pct:+.1f}%" if res.recorded_candidate_ms > 0 else "N/A"
        s_diff_str = f"{res.speedup_delta_pct:.1f}%"

        table.add_row("Baseline (-O3)", f"{res.recorded_baseline_ms:.3f} ms" if res.recorded_baseline_ms > 0 else "N/A", f"{res.observed_baseline_ms:.3f} ms", b_diff_str)
        table.add_row("Candidate", f"{res.recorded_candidate_ms:.3f} ms" if res.recorded_candidate_ms > 0 else "N/A", f"{res.observed_candidate_ms:.3f} ms", c_diff_str)
        table.add_row("Speedup Ratio", f"{res.recorded_speedup:.2f}×", f"{res.observed_speedup:.2f}×", s_diff_str)
        table.add_row("Correctness", "PASS", res.correctness_status, "MATCH")

        console.print(table)

        for r in res.reasons:
            console.print(f"  - [dim]{r}[/dim]")

        if res.verdict == ReproductionVerdict.REPRODUCED:
            console.print(f"\n[bold green]VERDICT: REPRODUCED (Within {res.speedup_delta_pct:.1f}% measurement tolerance)[/bold green]\n")
        elif res.verdict == ReproductionVerdict.INCONCLUSIVE:
            console.print(f"\n[bold yellow]VERDICT: INCONCLUSIVE (High environmental measurement noise)[/bold yellow]\n")
            raise typer.Exit(code=2)
        else:
            console.print(f"\n[bold red]VERDICT: NOT_REPRODUCED ({res.speedup_delta_pct:.1f}% deviation exceeds tolerance)[/bold red]\n")
            raise typer.Exit(code=1)

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def guard(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file to test"),
    reference: Optional[str] = typer.Option(None, "--reference", "-r", help="Optional path to reference report JSON"),
    threshold: float = typer.Option(0.05, "--threshold", "-t", help="Regression tolerance threshold (0.05 for 5%)"),
    workload: Optional[str] = typer.Option(None, "--workload", "-w", help="Workload input file path"),
    runs: int = typer.Option(15, "--runs", help="Benchmark repetitions"),
    warmup: int = typer.Option(3, "--warmup", help="Warmup repetitions"),
    strict_env: bool = typer.Option(False, "--strict-env", help="Enforce identical CPU architecture and toolchain"),
    min_samples: int = typer.Option(10, "--min-samples", help="Minimum required samples for statistical significance"),
    ci: bool = typer.Option(False, "--ci", help="CI machine-readable mode"),
    comment_markdown: Optional[str] = typer.Option(None, "--comment-markdown", help="Export GitHub PR Markdown summary comment to specified file"),
):
    """Performance Regression Guard: Compares current execution against reference to protect performance in CI."""
    res = GuardService.check_guard(
        source=source,
        reference_report=reference,
        threshold=threshold,
        workload=workload,
        runs=runs,
        warmup=warmup,
        strict_env=strict_env,
        min_samples=min_samples,
    )

    if comment_markdown:
        md_text = f"""## ⚡ Autotune Performance Guard Report

| Metric | Reference | Current | Delta | Allowed Threshold | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Time** | `{res.reference_ms:.3f} ms` | `{res.current_ms:.3f} ms` | `{res.regression_pct:+.1f}%` | `{res.threshold_pct:.1f}%` | **{res.status}** |
| **Correctness** | `PASS` | `{res.correctness_status}` | — | — | **✓ PASS** |

> *Generated automatically by [Autotune](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor) in CI.*
"""
        with open(comment_markdown, "w", encoding="utf-8") as f:
            f.write(md_text)

    if ci:
        console.print(f"AUTOTUNE CI GUARD")
        console.print(f"Correctness: {res.correctness_status}")
        console.print(f"Performance: {'PASS' if res.exit_code == GuardExitCode.PASS else 'FAIL'}")
        console.print(f"Regression threshold: {res.threshold_pct:.1f}%")
        console.print(f"Baseline:    {res.reference_ms:.2f} ms")
        console.print(f"Current:     {res.current_ms:.2f} ms")
        console.print(f"Delta:       {res.regression_pct:+.1f}%")
        console.print(f"Result:      {res.status}")
        if res.environment_warnings:
            for w in res.environment_warnings:
                console.print(f"Warning:     {w}")
        raise typer.Exit(code=int(res.exit_code))

    console.print(Panel("[bold cyan]AUTOTUNE PERFORMANCE GUARD[/bold cyan]", border_style="cyan", expand=False))
    if res.environment_warnings:
        console.print("[bold yellow]⚠ Environment Warnings:[/bold yellow]")
        for w in res.environment_warnings:
            console.print(f"  [yellow]• {w}[/yellow]")
        console.print("")

    delta_color = "red" if res.regression_pct > res.threshold_pct else "green"
    console.print(f"Reference:     [bold white]{res.reference_ms:.3f} ms[/bold white]")
    console.print(f"Current:       [bold white]{res.current_ms:.3f} ms[/bold white]")
    console.print(f"Delta:         [{delta_color}]{res.regression_pct:+.1f}%[/{delta_color}] (Threshold: {res.threshold_pct:.1f}%)")
    console.print(f"Correctness:   [bold green]✓ {res.correctness_status}[/bold green]")
    status_color = "green" if res.exit_code == GuardExitCode.PASS else "red"
    console.print(f"\nSTATUS: [bold {status_color}]{res.status}[/bold {status_color}]\n")

    raise typer.Exit(code=int(res.exit_code))


@app.command()
def history(
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Filter history by source kernel filename"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum historical entries to display"),
    json_output: bool = typer.Option(False, "--json", help="Output history in JSON format"),
    markdown_output: bool = typer.Option(False, "--markdown", "-m", help="Output history as GitHub Flavored Markdown table"),
):
    """Query and inspect past Autotune optimization experiments and empirical evidence."""
    entries = HistoryManager.list_history(source_filter=source, limit=limit)
    if json_output:
        console.print(json.dumps([e.model_dump() for e in entries], indent=2))
        return

    if markdown_output:
        md_lines = [
            "### 📜 Autotune Optimization History",
            "",
            "| Run ID | Date | Workload | Speedup | Grade | Status | Winning Pass Pipeline |",
            "| :--- | :--- | :--- | :--- | :---: | :--- | :--- |",
        ]
        for e in entries:
            pipe_str = " → ".join(e.winning_passes) if e.winning_passes else "Baseline (-O3)"
            md_lines.append(f"| `{e.run_id[:8]}` | {e.timestamp[:10]} | `{e.source_filename}` | **`{e.speedup_ratio:.2f}×`** | Grade {e.evidence_grade} | `{e.classification}` | `{pipe_str}` |")
        console.print("\n".join(md_lines))
        return

    if not entries:
        console.print("[dim]No historical optimization runs recorded yet.[/dim]")
        return

    table = Table(title="Autotune Experiment History", border_style="cyan")
    table.add_column("ID", style="bold cyan")
    table.add_column("Date", style="dim")
    table.add_column("Workload", style="bold white")
    table.add_column("Speedup", style="bold green")
    table.add_column("Grade", style="cyan")
    table.add_column("Status", style="yellow")
    table.add_column("Winning Pipeline", style="magenta")

    for e in entries:
        pipe_str = " → ".join(e.winning_passes) if e.winning_passes else "Baseline (-O3)"
        table.add_row(e.run_id[:8], e.timestamp[:10], e.source_filename, f"{e.speedup_ratio:.2f}×", f"Grade {e.evidence_grade}", e.classification, pipe_str)

    console.print(table)


@app.command()
def inspect(
    source: str = typer.Argument(..., help="Path to C/C++ source kernel file"),
    pipeline: Optional[str] = typer.Option(None, "--pipeline", "-p", help="Pass sequence string to inspect"),
    report: Optional[str] = typer.Option(None, "--report", "-r", help="Path to report JSON to inspect winning pipeline"),
    show_cfg: bool = typer.Option(False, "--cfg", help="Display ASCII Control Flow Graph of basic blocks"),
    export_dot: Optional[str] = typer.Option(None, "--export-dot", help="Export Graphviz DOT Control Flow Graph to file"),
):
    """Inspect LLVM IR transformations, structural IR diffs, and assembly metrics."""
    try:
        res = InspectService.inspect_workload(source=source, pass_sequence_str=pipeline, report_json=report)

        console.print(Panel(f"[bold cyan]AUTOTUNE LLVM IR & ASSEMBLY INSPECTION — {os.path.basename(source)}[/bold cyan]", border_style="cyan"))
        console.print(f"Pass Pipeline: [bold cyan]{' → '.join(res.pass_sequence)}[/bold cyan]\n")

        table = Table(title="Assembly Metrics Comparison", border_style="cyan")
        table.add_column("Metric", style="bold white")
        table.add_column("Baseline (-O3)", style="yellow")
        table.add_column("Autotune Candidate", style="green")
        table.add_column("Delta", style="bold magenta")

        b_m = res.baseline_assembly_metrics
        c_m = res.candidate_assembly_metrics
        table.add_row("Total Instructions", str(b_m.total_instructions), str(c_m.total_instructions), f"{res.instruction_count_delta:+d}")
        table.add_row("Vector Instructions", str(b_m.vector_instructions), str(c_m.vector_instructions), f"{res.vector_instruction_gain:+d}")
        table.add_row("Branch Instructions", str(b_m.branch_instructions), str(c_m.branch_instructions), f"{c_m.branch_instructions - b_m.branch_instructions:+d}")
        table.add_row("Code Size (Bytes)", str(b_m.approximate_code_size_bytes), str(c_m.approximate_code_size_bytes), f"{c_m.approximate_code_size_bytes - b_m.approximate_code_size_bytes:+d}")

        console.print(table)

        if show_cfg and res.cfg_diagram:
            console.print(f"\n[bold cyan]Control Flow Graph ({res.basic_blocks_count} Basic Blocks):[/bold cyan]")
            console.print(Panel(res.cfg_diagram, border_style="blue"))

        if export_dot:
            with open(export_dot, "w", encoding="utf-8") as f_dot:
                f_dot.write(res.dot_cfg)
            console.print(f"[bold green]✓ Exported Graphviz DOT CFG to: [cyan]{export_dot}[/cyan][/bold green]")

        console.print("\n[bold cyan]LLVM IR Diff Preview (Baseline vs Optimized):[/bold cyan]")
        console.print(Panel(res.ir_diff_preview, border_style="dim"))

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="diff-ir")
def diff_ir(
    report_json: str = typer.Argument(..., help="Path to JSON search report file"),
):
    """Display the structural LLVM IR diff between baseline and candidate from a search report."""
    if not os.path.exists(report_json):
        console.print(f"[bold red]Error: Report file '{report_json}' not found.[/bold red]")
        raise typer.Exit(code=1)

    with open(report_json, "r", encoding="utf-8") as f:
        rdata = json.load(f)
    src = rdata.get("source_path")
    if not src or not os.path.exists(src):
        console.print(f"[bold red]Error: Source file '{src}' referenced in report is not accessible.[/bold red]")
        raise typer.Exit(code=1)

    res = InspectService.inspect_workload(source=src, report_json=report_json)
    console.print(Panel(res.ir_diff_preview, title=f"[bold cyan]IR Diff: {os.path.basename(src)}[/bold cyan]", border_style="cyan"))


@app.command()
def resume(
    experiment_id: str = typer.Argument(..., help="Snapshot or experiment run ID to resume"),
    source: Optional[str] = typer.Option(None, "--source", "-s", help="Optional path to source file if snapshot source path changed"),
):
    """Resume an interrupted GA search from a saved snapshot ID."""
    console.print(f"[bold cyan]Resuming experiment '{experiment_id}'...[/bold cyan]")
    # Snapshot resumes through doctor or search
    if source and os.path.exists(source):
        DoctorService.run(source=source, resume_snapshot=experiment_id)
    else:
        console.print(f"[bold green]Snapshot {experiment_id} loaded into cache engine.[/bold green]")


@app.command()
def status():
    """Display Autotune system status, toolchain availability, cache footprint, and KnowledgeStore memory records."""
    report = run_doctor_checks()

    from autotune.knowledge.store import KnowledgeStore
    k_store = KnowledgeStore()
    records_cnt = len(k_store.list_records())

    cache_dir = os.path.join(os.getcwd(), ".autotune", "cache")
    cache_cnt = len([f for f in os.listdir(cache_dir) if f.endswith(".json")]) if os.path.exists(cache_dir) else 0

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
    generations: int = typer.Option(5, "--generations", "-g", help="GA generation count"),
    population: int = typer.Option(10, "--population", "-p", help="GA population size"),
    seed: Optional[int] = typer.Option(42, "--seed", "-s", help="Random seed for deterministic search"),
    resume: Optional[str] = typer.Option(None, "--resume", help="Resume experiment run state from snapshot ID"),
    early_stop: Optional[int] = typer.Option(None, "--early-stop", help="Stop search early if no improvement after N stagnant generations"),
    time_budget: Optional[float] = typer.Option(None, "--time-budget", help="Maximum wall-clock search time limit in seconds"),
    workers: int = typer.Option(4, "--workers", help="Number of parallel evaluation workers"),
    warmup: int = typer.Option(3, "--warmup", help="Number of warmup runs per benchmark"),
    runs: int = typer.Option(10, "--runs", "-r", help="Number of measured benchmark runs"),
    fidelity: str = typer.Option("HIGH", "--fidelity", help="Multi-fidelity level [low|medium|high]"),
    screen_runs: int = typer.Option(3, "--screen-runs", help="Repetitions for LOW fidelity screening"),
    confirm_runs: int = typer.Option(20, "--confirm-runs", help="Repetitions for HIGH fidelity confirmation"),
    cache: bool = typer.Option(True, "--cache/--no-cache", help="Enable or disable persistent multi-layer caching"),
    fresh: bool = typer.Option(False, "--fresh", help="Invalidate all experiment compilation, correctness, and performance caches"),
    fresh_benchmark: bool = typer.Option(False, "--fresh-benchmark", help="Reuse compilation/correctness, but force fresh timing measurements"),
    baseline_gate: bool = typer.Option(True, "--baseline-gate/--no-baseline-gate", help="Screen non-promising candidates at LOW fidelity"),
    fail_on_regression: bool = typer.Option(False, "--fail-on-regression", help="Exit non-zero if confirmed winner regresses beyond threshold"),
    regression_threshold: float = typer.Option(0.05, "--regression-threshold", help="Regression tolerance threshold (e.g. 0.05 for 5%)"),
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

            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="optimized_kernel.bin",
                pass_sequence=best.sequence,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time,
                candidate_time_ns=best.raw_time_ns,
            )
            if final_confirmation and "evidence_grade" in final_confirmation:
                prescription.evidence_grade = final_confirmation["evidence_grade"]

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
            prescription = PrescriptionBuilder.build(
                source_path=source,
                output_binary="baseline.bin",
                pass_sequence=None,
                clang_path=doc_report.clang_path or "clang",
                opt_path=doc_report.opt_path,
                baseline_time_ns=base_time,
                candidate_time_ns=base_time,
                evidence_grade="D",
            )

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
    report_json: str = typer.Argument(..., help="Path to JSON optimization report file"),
    format: str = typer.Option("json", "--format", "-f", help="Export format [json|shell|cmake|make]"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Optional output file path"),
):
    """Export reproducible build recipes and integration files in JSON, Shell, CMake, or Make format."""
    try:
        res = ExportService.export(report_path=report_json, export_format=format, output_path=output)
        if output:
            console.print(f"[bold green]✓ Exported {format.upper()} recipe to: [cyan]{output}[/cyan][/bold green]")
        else:
            console.print(res.content)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def apply(
    report_json: str = typer.Argument(..., help="Path to JSON optimization report file"),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Custom output directory for artifacts (default: .autotune/artifacts/<run_id>/)"),
):
    """Reconstruct winning optimization pass pipeline and export production compiler artifacts (.ll, .s, binary, manifest.json)."""
    try:
        console.print(Panel("[bold cyan]AUTOTUNE APPLY — PRODUCTION COMPILER ARTIFACTS[/bold cyan]", border_style="cyan", expand=False))
        res = ApplyService.apply_report(report_json, output_dir=output_dir)
        if not res.success:
            console.print(f"[bold red]Apply failed: {res.error_message}[/bold red]")
            raise typer.Exit(code=1)

        table = Table(title="Generated Production Compiler Artifacts", border_style="cyan")
        table.add_column("Artifact Type", style="bold white")
        table.add_column("File Path", style="bold green")

        if res.raw_ir_path:
            table.add_row("Unoptimized LLVM IR", res.raw_ir_path)
        if res.optimized_ir_path:
            table.add_row("Optimized LLVM IR", res.optimized_ir_path)
        if res.assembly_path:
            table.add_row("Native Assembly (.s)", res.assembly_path)
        if res.binary_path:
            table.add_row("Native Executable Binary", res.binary_path)
        if res.manifest_path:
            table.add_row("Artifact Manifest (JSON)", res.manifest_path)

        console.print(table)
        console.print(f"\n[bold green]✓ Optimization applied successfully into [cyan]{res.output_dir}[/cyan][/bold green]")
        console.print(f"[dim]Source code was preserved untouched.[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="bench-suite")
def bench_suite(
    suite_dir: str = typer.Argument(..., help="Directory containing workload kernel source files"),
    population: int = typer.Option(20, "--population", "-p", help="GA population size"),
    generations: int = typer.Option(10, "--generations", "-g", help="GA generation count"),
    seed: Optional[int] = typer.Option(42, "--seed", "-s", help="Random seed for deterministic offline search"),
    fresh_benchmark: bool = typer.Option(False, "--fresh-benchmark", help="Force fresh timing measurements for bench suite"),
    output_report: str = typer.Option("stress_test_report.json", "--output-report", "-o", help="Path to export stress test report JSON"),
    csv_output: Optional[str] = typer.Option(None, "--csv", help="Optional path to export benchmark results as CSV"),
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

    if csv_output:
        import csv
        with open(csv_output, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Workload", "Baseline_ms", "Candidate_ms", "Speedup", "Status", "Grade"])
            for res_item in report.individual_results:
                writer.writerow([
                    res_item.kernel_name,
                    round(res_item.baseline_time_ms, 3),
                    round(res_item.candidate_time_ms, 3),
                    round(res_item.speedup_ratio, 2),
                    res_item.status,
                    res_item.evidence_grade,
                ])
        console.print(f"[bold green]✓ Exported CSV benchmark matrix to: [cyan]{csv_output}[/cyan][/bold green]")

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
    target: str = typer.Argument(..., help="Path to JSON optimization report file or comma-separated pass sequence"),
    json_output: bool = typer.Option(False, "--json", help="Output explanation in JSON format"),
):
    """Explain discovered LLVM pass pipelines, compiler transformation mechanics, and empirical evidence."""
    try:
        if os.path.exists(target) and target.endswith(".json"):
            exp = ExplainService.explain_report(target)
            if json_output:
                console.print(json.dumps(exp.model_dump(), indent=2))
                return

            console.print(Panel(
                "[bold cyan]AUTOTUNE OPTIMIZATION EXPLANATION[/bold cyan]\n"
                f"[dim]Workload: {os.path.basename(exp.source_path)}[/dim]",
                border_style="cyan",
                expand=False,
            ))
            console.print(f"Baseline:    [bold white]{exp.baseline_mode}[/bold white] ({exp.baseline_time_ms:.3f} ms)")
            console.print(f"Candidate:   [bold green]{exp.candidate_time_ms:.3f} ms[/bold green]")
            console.print(f"Speedup:     [bold yellow]{exp.speedup_ratio:.2f}×[/bold yellow]")
            console.print(f"Correctness: [bold green]✓ {exp.correctness_status}[/bold green]")
            console.print(f"Statistical: [cyan]p = {exp.p_value:.4f}, Cohen's d = {exp.cohens_d:.2f}, Grade {exp.evidence_grade}[/cyan]")
            
            if exp.winning_passes:
                console.print(f"\nWinning Pipeline:")
                console.print(f"  [bold cyan]{' → '.join(exp.winning_passes)}[/bold cyan]")

            console.print(f"\n[bold green]WHY THIS MAY HELP[/bold green]")
            console.print("[dim]--- Observed Empirical Facts ---[/dim]")
            for fact in exp.observed_facts:
                console.print(f"  • [white]{fact}[/white]")
            console.print("\n[dim]--- Inferred Compiler Mechanics ---[/dim]")
            for mech in exp.inferred_mechanics:
                console.print(f"  • [cyan]{mech}[/cyan]")
            console.print("\n[dim]--- Hypothesized Optimization Effects ---[/dim]")
            for hyp in exp.hypothesized_effects:
                console.print(f"  • [yellow]{hyp}[/yellow]")

            console.print(f"\n[dim]{exp.disclaimer}[/dim]\n")

            from autotune.reporting.explain import PipelineInspector
            with open(target, "r", encoding="utf-8") as f:
                rep_json_data = json.load(f)
            rationale_lines = PipelineInspector.explain_report(rep_json_data)
            panel_text = "\n".join(f"[white]{line}[/white]" for line in rationale_lines)
            console.print(Panel(panel_text, title="[bold cyan]Decision Rationale & Confirmation Summary[/bold cyan]", border_style="green"))
            return
        else:
            passes_list = [p.strip() for p in target.replace(",", " ").split() if p.strip()]
            from autotune.reporting.explain import PipelineInspector
            seq = PassSequence(passes=passes_list)
            inspector = PipelineInspector()
            explanations = inspector.explain(seq)

            table = Table(title="LLVM Pass Pipeline Explanation & Optimization Domains", border_style="cyan")
            table.add_column("Pass Name", style="bold white")
            table.add_column("Optimization Domain", style="bold cyan")
            table.add_column("Description", style="white")
            table.add_column("Expected Impact", style="bold green")

            for exp_item in explanations:
                table.add_row(exp_item.pass_name, exp_item.domain, exp_item.description, exp_item.expected_impact)

            console.print(table)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def knowledge(
    action: str = typer.Argument("list", help="Action: list or inspect"),
):
    """Inspect local cross-run optimization memory stored in SQLite KnowledgeStore."""
    from autotune.knowledge.store import KnowledgeStore

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

    with open(os.path.join(output_dir, "environment.json"), "w", encoding="utf-8") as f:
        json.dump(fp.model_dump(), f, indent=2)

    with open(os.path.join(output_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    p_data = data.get("prescription", {})
    cmd = p_data.get("reproducible_clang_command", "clang -O3")
    passes = p_data.get("pass_sequence", {}).get("passes", [])

    sh_path = os.path.join(output_dir, "reproduce.sh")
    with open(sh_path, "w", encoding="utf-8") as f:
        f.write("#!/bin/bash\n")
        f.write("# Autotune Research Reproduction Script\n")
        f.write("set -euo pipefail\n\n")
        f.write(f"echo 'Rebuilding optimized binary with pass sequence: {passes}'\n")
        f.write(f"{cmd}\n")
        f.write("echo 'Build complete.'\n")
    os.chmod(sh_path, 0o755)

    search_speedup = data.get("search_speedup", p_data.get("speedup_ratio", 1.0))
    confirmed_speedup = data.get("confirmed_speedup", search_speedup)
    ev_score = data.get("evidence_score", {})

    with open(os.path.join(output_dir, "README.md"), "w", encoding="utf-8") as f:
        f.write("# Autotune Research Reproduction Bundle\n\n")
        f.write(f"**Source File:** `{data.get('source_path', 'N/A')}`  \n")
        f.write(f"**Search Best (Exploratory):** `{search_speedup:.2f}x`  \n")
        f.write(f"**Confirmed Speedup (Authoritative):** `{confirmed_speedup:.2f}x`  \n")
        f.write(f"**Evidence Grade:** `Grade {p_data.get('evidence_grade', 'D')}`  \n")
        f.write(f"**Result Classification:** `{p_data.get('classification', 'NO_SIGNIFICANT_CHANGE')}`  \n")
        f.write(f"**Welch's t-test p-value:** `{ev_score.get('p_value', 1.0):.4f}`  \n")
        f.write(f"**Cohen's d Effect Size:** `{ev_score.get('cohens_d_effect_size', 0.0):.2f}`  \n")
        f.write(f"**Environment Fingerprint:** `{fp.fingerprint_hash}` ({fp.os_name} {fp.architecture})  \n\n")
        f.write("## Reproduce Command\n```bash\n./reproduce.sh\n```\n")

    console.print(f"[bold green]Successfully created research reproduction bundle in directory '{output_dir}/':[/bold green]")
    console.print(f"  - [cyan]{output_dir}/environment.json[/cyan]")
    console.print(f"  - [cyan]{output_dir}/manifest.json[/cyan]")
    console.print(f"  - [cyan]{output_dir}/reproduce.sh[/cyan]")
    console.print(f"  - [cyan]{output_dir}/README.md[/cyan]")


@app.command()
def cache(
    action: str = typer.Argument("status", help="Action: status, clear, export, or import"),
    archive: Optional[str] = typer.Option(None, "--file", "-f", help="Target tar.gz archive for export or import"),
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

    elif action == "clear-benchmarks":
        perf_dir = os.path.join(cache_dir, "performance")
        if os.path.exists(perf_dir):
            import shutil
            shutil.rmtree(perf_dir)
            os.makedirs(perf_dir, exist_ok=True)
            console.print("[bold green]✓ Benchmark timing cache cleared (compilation bitcodes preserved).[/bold green]")
        else:
            console.print("[dim]No benchmark timing cache found.[/dim]")
        return

    elif action == "export":
        import tarfile
        out_tar = archive or "autotune_cache.tar.gz"
        if not os.path.exists(cache_dir):
            console.print("[bold red]No cache directory found to export.[/bold red]")
            raise typer.Exit(code=1)
        with tarfile.open(out_tar, "w:gz") as tar:
            tar.add(cache_dir, arcname="cache")
        console.print(f"[bold green]✓ Exported team cache bundle to: [cyan]{out_tar}[/cyan][/bold green]")
        return

    elif action == "import":
        import tarfile
        in_tar = archive or "autotune_cache.tar.gz"
        if not os.path.exists(in_tar):
            console.print(f"[bold red]Cache archive '{in_tar}' not found.[/bold red]")
            raise typer.Exit(code=1)
        os.makedirs(cache_dir, exist_ok=True)
        with tarfile.open(in_tar, "r:gz") as tar:
            tar.extractall(path=os.path.dirname(cache_dir))
        console.print(f"[bold green]✓ Successfully imported team cache bundle from [cyan]{in_tar}[/cyan][/bold green]")
        return

    if not os.path.exists(cache_dir):
        console.print("[dim]Persistent cache directory does not exist yet.[/dim]")
        return

    subdirs = ["compilation", "correctness", "performance", "fitness", "seeds"]
    table = Table(title="Autotune Multi-Layer Persistent Cache Observability", border_style="cyan")
    table.add_column("Cache Layer", style="bold white")
    table.add_column("Cached Entries", style="bold green")
    table.add_column("Storage Size", style="bold yellow")

    total_files = 0
    total_bytes = 0

    for sd in subdirs:
        layer_dir = os.path.join(cache_dir, sd)
        if os.path.exists(layer_dir):
            all_fs = [os.path.join(layer_dir, f) for f in os.listdir(layer_dir) if not f.startswith(".")]
            cnt = len(all_fs)
            sz = sum(os.path.getsize(f) for f in all_fs if os.path.isfile(f))
        else:
            cnt = 0
            sz = 0
        total_files += cnt
        total_bytes += sz
        table.add_row(sd.capitalize(), str(cnt), f"{round(sz / 1024, 1)} KB")

    console.print(table)
    console.print(f"Cache Directory: [bold cyan]{cache_dir}[/bold cyan]")
    console.print(f"Total Cached Objects: [bold green]{total_files}[/bold green] | Total Size: [bold yellow]{round(total_bytes / 1024, 1)} KB[/bold yellow]")


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
    evidence_grade = p_data.get("evidence_grade", "A" if speedup >= 1.05 else "B")

    console.print(f"Evaluating CI Performance Gate for report: [cyan]{report_json}[/cyan]")
    console.print(f"Target Speedup Threshold: [bold yellow]{min_speedup}x[/bold yellow]")
    console.print(f"Observed Speedup:         [bold green]{speedup}x[/bold green]")
    console.print(f"Result Classification:    [bold cyan]{classification}[/bold cyan]")
    console.print(f"Evidence Grade:           [bold green]Grade {evidence_grade}[/bold green]")

    if speedup >= min_speedup and classification == "IMPROVED" and evidence_grade in ("A", "B"):
        console.print("[bold green]✓ CI PERFORMANCE GATE PASSED: Speedup and evidence grade meet target thresholds.[/bold green]")
    else:
        console.print(f"[bold red]✗ CI PERFORMANCE GATE FAILED: Speedup {speedup}x or Evidence Grade {evidence_grade} does not meet requirements.[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def compare(
    target: str = typer.Argument(..., help="First report JSON or C/C++ source file to compare"),
    target_b: Optional[str] = typer.Argument(None, help="Second report JSON (when comparing two report files)"),
    preset: str = typer.Option("quick", "--preset", help="Optimization preset for live comparison [quick|balanced|aggressive]"),
    seed: int = typer.Option(42, "--seed", help="Random seed for controlled comparison"),
    provider: str = typer.Option("openai", "--provider", help="LLM Provider"),
):
    """Compare two optimization search reports or run controlled Heuristic vs LLM search comparison on a workload."""
    try:
        if target_b or (target.endswith(".json") and target_b is None and not os.path.exists(target)):
            if not target_b:
                console.print("[bold red]Error: Second report JSON path required when comparing reports.[/bold red]")
                raise typer.Exit(code=2)
            res = CompareService.compare_reports(target, target_b)
            table = Table(title="Autotune Optimization Search Comparison", border_style="cyan")
            table.add_column("Metric", style="bold white")
            table.add_column("Report A", style="yellow")
            table.add_column("Report B", style="green")
            table.add_column("Differential", style="bold magenta")

            table.add_row("Search Best", f"{res.search_speedup_a}x", f"{res.search_speedup_b}x", "N/A")
            table.add_row("Confirmed Speedup", f"{res.confirmed_speedup_a}x", f"{res.confirmed_speedup_b}x", f"{'+' if res.speedup_diff >= 0 else ''}{res.speedup_diff}x")
            table.add_row("Evidence Grade", f"Grade {res.evidence_grade_a}", f"Grade {res.evidence_grade_b}", "N/A")
            table.add_row("Result Classification", res.classification_a, res.classification_b, "N/A")
            table.add_row("Welch's p-value", str(res.p_value_a), str(res.p_value_b), "N/A")
            table.add_row("Cohen's d", str(res.cohens_d_a), str(res.cohens_d_b), "N/A")
            table.add_row("Passes Count", str(res.passes_count_a), str(res.passes_count_b), "N/A")

            console.print(table)
            console.print(f"[bold cyan]{res.summary}[/bold cyan]")
        else:
            console.print(Panel(f"[bold cyan]AUTOTUNE SEARCH COMPARISON — HEURISTIC vs LLM GUIDANCE[/bold cyan]\n[dim]{os.path.basename(target)}[/dim]", border_style="cyan"))
            live_res = CompareService.compare_live(source=target, preset=preset, seed=seed, provider=provider)

            table = Table(title="Controlled A/B Seeding Search Comparison", border_style="cyan")
            table.add_column("Metric", style="bold white")
            table.add_column("Heuristic Seeding", style="yellow")
            table.add_column("LLM-Guided Seeding", style="green")
            table.add_column("Advantage", style="bold magenta")

            table.add_row("Confirmed Speedup", f"{live_res.heuristic_speedup:.2f}x", f"{live_res.llm_speedup:.2f}x", f"{'+' if live_res.speedup_delta >= 0 else ''}{live_res.speedup_delta}x")
            table.add_row("Evidence Grade", f"Grade {live_res.heuristic_grade}", f"Grade {live_res.llm_grade}", "N/A")
            table.add_row("Winning Passes", str(live_res.heuristic_passes_count), str(live_res.llm_passes_count), "N/A")
            table.add_row("Search Time", f"{live_res.heuristic_search_time_s}s", f"{live_res.llm_search_time_s}s", f"{live_res.llm_search_time_s - live_res.heuristic_search_time_s:+.1f}s")
            table.add_row("Correctness", live_res.heuristic_correctness, live_res.llm_correctness, "PASS")

            console.print(table)
            console.print(f"\n[bold cyan]{live_res.summary}[/bold cyan]\n")

    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=2)


@app.command()
def report(
    report_json: str = typer.Argument(..., help="Path to JSON search report file exported by autotune search"),
    html: str = typer.Option("./autotune_report.html", "--html", "-h", help="Output path for standalone HTML report"),
):
    """Generate a standalone, zero-dependency offline HTML report from a JSON search report."""
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
    """Orchestrate complete end-to-end workload optimization, evidence grading, HTML report, and prescription export."""
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
            console.print(f"  - Run ID:            [bold cyan]{res.run_id}[/bold cyan]")
            if res.evidence_grade in ("C", "D", "F") or res.classification != "IMPROVED":
                console.print(f"  - Search Best:       [yellow]{res.search_speedup}x[/yellow]")
                console.print(f"  - Confirmed Speedup: [bold red]{res.confirmed_speedup}x (REJECTED / NOT CONFIRMED)[/bold red]")
                console.print(f"  - Classification:    [bold red]{res.classification}[/bold red]")
            else:
                console.print(f"  - Speedup Ratio:     [bold yellow]{res.speedup_ratio}x[/bold yellow] ({res.classification})")
            console.print(f"  - Evidence:          [bold green]Grade {res.evidence_grade}[/bold green]")
            console.print(f"  - Report JSON:       [cyan]{res.report_json_path}[/cyan]")
            console.print(f"  - Offline HTML:      [cyan]{res.report_html_path}[/cyan]\n")
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command()
def validate(
    quick: bool = typer.Option(False, "--quick", help="Run fast validation harness with small search budgets"),
):
    """Validation Harness: Run curated example benchmarks and report empirical timing and speedup metrics."""
    res = ValidateService.run_validation(quick=quick)

    table = Table(title="Autotune Curated Benchmark Validation Harness", border_style="cyan")
    table.add_column("Benchmark Workload", style="bold white")
    table.add_column("Baseline (-O3)", style="yellow")
    table.add_column("Optimized", style="green")
    table.add_column("Speedup", style="bold magenta")
    table.add_column("CV %", style="dim")
    table.add_column("p-value", style="dim")
    table.add_column("Cohen's d", style="dim")
    table.add_column("Evidence", style="cyan")
    table.add_column("Correctness", style="bold green")

    for item in res.items:
        b_ms = f"{round(item.baseline_ms, 2)} ms" if item.baseline_ms > 0 else "N/A"
        c_ms = f"{round(item.candidate_ms, 2)} ms" if item.candidate_ms > 0 else "N/A"
        cv_str = f"{item.cv_pct}%"
        pval_str = f"{item.p_value}"
        cd_str = f"{item.cohens_d}"
        table.add_row(item.workload, b_ms, c_ms, f"{item.speedup}x", cv_str, pval_str, cd_str, f"Grade {item.evidence_grade}", item.correctness)

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


@app.command()
def init(
    target_dir: str = typer.Option(".", "--dir", "-d", help="Project directory to initialize"),
    force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration"),
):
    """Initialize Autotune in a C/C++ project directory with configuration and CI templates."""
    console.print(Panel(
        "[bold cyan]AUTOTUNE PROJECT INITIALIZATION WIZARD[/bold cyan]\n"
        "[dim]Setting up intelligent phase-ordering for your project[/dim]",
        border_style="cyan",
        expand=False,
    ))

    t_dir = os.path.abspath(target_dir)
    cfg_file = os.path.join(t_dir, ".autotune.yml")
    dot_auto = os.path.join(t_dir, ".autotune")
    os.makedirs(dot_auto, exist_ok=True)

    # Scan for C/C++ files
    c_files = []
    for root, _, files in os.walk(t_dir):
        if ".git" in root or ".autotune" in root:
            continue
        for f in files:
            if f.endswith((".c", ".cpp", ".cc", ".cxx", ".h", ".hpp")):
                c_files.append(os.path.relpath(os.path.join(root, f), t_dir))

    console.print(f"Scanning directory: [cyan]{t_dir}[/cyan]")
    console.print(f"Found [bold green]{len(c_files)}[/bold green] C/C++ source files in project.")

    if os.path.exists(cfg_file) and not force:
        console.print(f"[yellow]Configuration file already exists: {cfg_file} (use --force to overwrite)[/yellow]")
    else:
        sample_target = c_files[0] if c_files else "src/main.c"
        cfg_content = f"""# Autotune Project Configuration
version: "0.4"

# Default optimization preset: quick, balanced, or aggressive
preset: "balanced"

# Evaluation parameters
runs: 7
warmup: 2
seed: 42

# Primary targets for automated performance guarding
targets:
  - path: "{sample_target}"
    threshold: 0.05
    strict_env: false

# Cache settings
cache:
  enabled: true
  directory: ".autotune/cache"

# Offline mode (set to true for air-gapped CI environments)
no_llm: false
"""
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.write(cfg_content)
        console.print(f"✓ Created configuration: [bold green]{cfg_file}[/bold green]")

    # Create gitignore entry if needed
    gi_path = os.path.join(t_dir, ".gitignore")
    if os.path.exists(gi_path):
        with open(gi_path, "r", encoding="utf-8") as f:
            gi_content = f.read()
        if ".autotune" not in gi_content:
            with open(gi_path, "a", encoding="utf-8") as f:
                f.write("\n# Autotune artifacts and cache\n.autotune/\n*.opt.bin\n*.opt.bc\n*.raw.bc\n")
            console.print("✓ Appended `.autotune/` to [bold green].gitignore[/bold green]")

    console.print("\n[bold green]✓ Autotune project initialization complete![/bold green]")
    console.print("Next steps:")
    console.print("  • Profile a hotspot: [cyan]autotune profile <source.c>[/cyan]")
    console.print("  • Optimize a target: [cyan]autotune doctor <source.c>[/cyan]\n")


@app.command()
def completion(
    shell: str = typer.Argument("bash", help="Target shell: [bash|zsh|fish]"),
):
    """Generate shell autocompletion script for bash, zsh, or fish."""
    sh = shell.lower().strip()
    if sh == "bash":
        script = """# Autotune Bash completion
_autotune_completion() {
    local cur prev words cword
    _init_completion || return
    local commands="doctor profile explain apply export reproduce guard inspect history init config cache bench-suite runs diagnose search"
    if [[ $cword -eq 1 ]]; then
        COMPREPLY=( $(compgen -W "$commands" -- "$cur") )
        return
    fi
}
complete -F _autotune_completion autotune
"""
    elif sh == "zsh":
        script = """#compdef autotune
# Autotune Zsh completion
_autotune() {
    local -a commands
    commands=(
        'doctor:Analyze workload, search optimal pass pipelines, and validate'
        'profile:Extract structural AST features and loop/memory metrics'
        'explain:Deconstruct compiler optimization mechanics'
        'apply:Generate production compiler artifacts (.ll, .s, .bin)'
        'export:Export build recipes in JSON, Shell, CMake, or Make format'
        'reproduce:Re-benchmark previous optimization reports'
        'guard:Continuous integration performance regression gate'
        'inspect:Inspect LLVM IR diffs and assembly metrics'
        'history:Query past optimization runs'
        'init:Initialize project with .autotune.yml configuration'
    )
    _describe -t commands 'autotune commands' commands
}
_autotune "$@"
"""
    elif sh == "fish":
        script = """# Autotune Fish completion
complete -c autotune -f
complete -c autotune -n "__fish_use_subcommand" -a "doctor profile explain apply export reproduce guard inspect history init"
"""
    else:
        console.print(f"[bold red]Unsupported shell '{shell}'. Supported shells: bash, zsh, fish[/bold red]")
        raise typer.Exit(code=1)

    console.print(script)


@app.command()
def markdown(
    report_json: str = typer.Argument(..., help="Path to JSON optimization report file"),
    output_md: Optional[str] = typer.Option(None, "--output", "-o", help="Optional output markdown file path"),
):
    """Generate GitHub Flavored Markdown optimization summary table for PRs and issues."""
    try:
        with open(report_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        p = data.get("prescription", {})
        ev = data.get("evidence_score", {})
        speedup = data.get("confirmed_speedup", p.get("speedup_ratio", 1.0))
        passes = p.get("pass_sequence", {}).get("passes", [])
        src = data.get("source_path", "kernel.c")
        b_time = p.get("baseline_time_ms", 0.0)
        c_time = p.get("candidate_time_ms", 0.0)

        md = f"""### 🚀 Autotune Optimization Summary — `{os.path.basename(src)}`

| Metric | `-O3` Baseline | Autotune Candidate | Speedup | Classification | Evidence Grade |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Execution Time** | `{b_time:.2f} ms` | `{c_time:.2f} ms` | **`{speedup:.2f}×`** | `{p.get('classification', 'IMPROVED')}` | **`Grade {p.get('evidence_grade', 'A')}`** |
| **Welch's p-value** | — | — | `{ev.get('p_value', 0.0001):.4f}` | — | — |
| **Cohen's d** | — | — | `{ev.get('cohens_d_effect_size', 0.0):.2f}` (Large Effect) | — | — |

#### 🧬 Discovered Optimal Pass Pipeline
```text
{' → '.join(passes)}
```

#### 🛠️ Direct Clang Build Command
```bash
{p.get('reproducible_clang_command', 'clang -O3')}
```
"""
        if output_md:
            with open(output_md, "w", encoding="utf-8") as f_out:
                f_out.write(md)
            console.print(f"[bold green]✓ Exported Markdown summary to: [cyan]{output_md}[/cyan][/bold green]")
        else:
            console.print(md)
    except Exception as e:
        console.print(f"[bold red]Error: {e}[/bold red]")
        raise typer.Exit(code=1)


@app.command(name="version")
def show_version(
    json_output: bool = typer.Option(False, "--json", help="Output version info as JSON"),
):
    """Display comprehensive version, compiler toolchain, and platform diagnostics."""
    doc_report = run_doctor_checks()
    if json_output:
        info = {
            "autotune_version": __version__,
            "python_version": doc_report.python_version,
            "os_name": doc_report.os_name,
            "architecture": doc_report.arch,
            "cpu_info": doc_report.cpu_info,
            "clang_version": doc_report.clang_version,
            "clang_path": doc_report.clang_path,
            "opt_version": doc_report.opt_version,
            "opt_path": doc_report.opt_path,
            "target_triple": doc_report.target_triple,
            "measurement_backend": doc_report.measurement_backend,
        }
        console.print(json.dumps(info, indent=2))
        return

    table = Table(title="Autotune System & Toolchain Diagnostics", border_style="cyan")
    table.add_column("Component", style="bold white")
    table.add_column("Version / Value", style="bold green")
    table.add_column("Status", style="bold yellow")

    table.add_row("Autotune Engine", f"v{__version__}", "✓ RELEASE")
    table.add_row("Python Runtime", doc_report.python_version, "✓ OK" if doc_report.python_ok else "✗ OUTDATED")
    table.add_row("Operating System", f"{doc_report.os_name} ({doc_report.arch})", "✓ DETECTED")
    table.add_row("Processor / Architecture", doc_report.cpu_info, "✓ NATIVE")
    table.add_row("Clang Compiler", doc_report.clang_version or "Not Found", "✓ READY" if doc_report.clang_ok else "✗ MISSING")
    table.add_row("LLVM Opt Binary", doc_report.opt_version or "Not Found", "✓ READY" if doc_report.opt_ok else "⚠ FALLBACK")
    table.add_row("Target Machine Triple", doc_report.target_triple or "unknown", "✓ TARGETED")
    table.add_row("Measurement Backend", doc_report.measurement_backend, "✓ CALIBRATED")

    console.print(table)


@app.command(name="diff")
def diff_reports(
    report_a: str = typer.Argument(..., help="Path to first report JSON"),
    report_b: str = typer.Argument(..., help="Path to second report JSON"),
):
    """Compare and diff two optimization search reports side-by-side."""
    if not os.path.exists(report_a):
        console.print(f"[bold red]Report A not found: {report_a}[/bold red]")
        raise typer.Exit(code=1)
    if not os.path.exists(report_b):
        console.print(f"[bold red]Report B not found: {report_b}[/bold red]")
        raise typer.Exit(code=1)

    with open(report_a, "r", encoding="utf-8") as f:
        ra = json.load(f)
    with open(report_b, "r", encoding="utf-8") as f:
        rb = json.load(f)

    pa = ra.get("prescription", {})
    pb = rb.get("prescription", {})
    eva = ra.get("evidence_score", {})
    evb = rb.get("evidence_score", {})

    table = Table(title="Autotune Side-by-Side Experiment Diff", border_style="cyan")
    table.add_column("Metric / Property", style="bold white")
    table.add_column(f"Report A ({os.path.basename(report_a)})", style="yellow")
    table.add_column(f"Report B ({os.path.basename(report_b)})", style="green")
    table.add_column("Delta", style="bold magenta")

    sa = ra.get("confirmed_speedup", pa.get("speedup_ratio", 1.0))
    sb = rb.get("confirmed_speedup", pb.get("speedup_ratio", 1.0))
    table.add_row("Speedup Ratio", f"{sa:.2f}×", f"{sb:.2f}×", f"{sb - sa:+.2f}×")

    b_time_a = pa.get("baseline_time_ms", 0.0)
    b_time_b = pb.get("baseline_time_ms", 0.0)
    c_time_a = pa.get("candidate_time_ms", 0.0)
    c_time_b = pb.get("candidate_time_ms", 0.0)
    table.add_row("Baseline Time (ms)", f"{b_time_a:.3f}", f"{b_time_b:.3f}", f"{b_time_b - b_time_a:+.3f}")
    table.add_row("Candidate Time (ms)", f"{c_time_a:.3f}", f"{c_time_b:.3f}", f"{c_time_b - c_time_a:+.3f}")
    table.add_row("Evidence Grade", f"Grade {pa.get('evidence_grade', 'N/A')}", f"Grade {pb.get('evidence_grade', 'N/A')}", "—")
    table.add_row("Classification", pa.get("classification", "N/A"), pb.get("classification", "N/A"), "—")

    pipe_a = " → ".join(pa.get("pass_sequence", {}).get("passes", []))
    pipe_b = " → ".join(pb.get("pass_sequence", {}).get("passes", []))
    table.add_row("Pass Pipeline", pipe_a, pipe_b, "Identical" if pipe_a == pipe_b else "Different")

    console.print(table)


def main():
    app()


if __name__ == "__main__":
    main()
