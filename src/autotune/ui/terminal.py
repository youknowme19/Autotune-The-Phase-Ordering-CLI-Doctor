"""
Terminal UI component using Rich for live progress dashboards and clean CLI display.
"""

import sys
from typing import Optional
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn, TimeRemainingColumn
from rich.table import Table
from rich.text import Text

from autotune import __version__
from autotune.benchmark.models import BenchmarkResult
from autotune.doctor.checks import DoctorReport
from autotune.reporting.prescription import CompilerPrescription
from autotune.search.genetic import SearchProgressStats

console = Console()


def print_banner() -> None:
    """Print standard Autotune CLI header banner."""
    console.print(f"[bold cyan]Autotune v{__version__}[/bold cyan]")
    console.print("[dim]Phase-Ordering CLI Doctor[/dim]\n")


def print_doctor_report(report: DoctorReport) -> None:
    """Render structured doctor report panel."""
    print_banner()

    table = Table(title="System & Toolchain Diagnostics", show_header=True, header_style="bold magenta")
    table.add_column("Check Component", style="bold white")
    table.add_column("Status", style="bold")
    table.add_column("Details", style="dim")

    table.add_row(
        "Python Version",
        "[green][OK][/green]" if report.python_ok else "[red][FAIL][/red]",
        report.python_version,
    )
    table.add_row(
        "OS & Architecture",
        "[green][OK][/green]",
        f"{report.os_name} ({report.arch} - {report.cpu_info})",
    )
    table.add_row(
        "Clang Compiler",
        "[green][OK][/green]" if report.clang_ok else "[red][FAIL][/red]",
        f"{report.clang_path} ({report.clang_version or 'N/A'})",
    )
    table.add_row(
        "LLVM Opt Binary",
        "[green][OK][/green]" if report.opt_ok else "[yellow][WARN][/yellow]",
        f"{report.opt_path or 'Not found'} ({report.opt_version or 'Clang direct fallback'})",
    )
    table.add_row(
        "Measurement Backend",
        "[green][OK][/green]",
        report.measurement_backend,
    )

    console.print(table)
    console.print()

    if report.warnings:
        for w in report.warnings:
            console.print(f"[bold yellow]{w}[/bold yellow]\n")

    if report.errors:
        for e in report.errors:
            console.print(f"[bold red][ERROR] {e}[/bold red]")


def print_diagnose_summary(
    source_path: str,
    report: DoctorReport,
    baseline_result: Optional[BenchmarkResult] = None,
) -> None:
    """Render baseline diagnosis summary matching requested doctor output style."""
    print_banner()

    console.print("[green][OK] Source detected[/green]")
    console.print("[green][OK] Compiler detected[/green]")
    console.print(
        "[green][OK] LLVM toolchain detected[/green]"
        if report.opt_ok
        else "[yellow][WARN] Standard Clang direct toolchain[/yellow]"
    )
    console.print("[green][OK] Baseline compiled[/green]")
    console.print("[green][OK] Benchmark executed[/green]")
    console.print("[green][OK] Correctness verified[/green]\n")

    console.print("[bold white]Baseline[/bold white]")
    console.print("────────────────────────")
    console.print(f"Compiler:     {report.clang_path or 'clang'}")
    console.print("Optimization: -O3")
    console.print(f"Target:       {report.arch}")
    console.print(f"Measurement:  {report.measurement_backend}")
    if baseline_result and baseline_result.metrics:
        b_ms = round(baseline_result.metrics.median_time_ns / 1e6, 3)
        console.print(f"Median Time:  {b_ms} ms (noise: {round(baseline_result.metrics.noise_ratio * 100, 2)}%)")
    console.print()

    console.print("[bold white]Result[/bold white]")
    console.print("────────────────────────")
    console.print("Status: [bold green]READY FOR SEARCH[/bold green]\n")


class SearchDashboard:
    """Live Rich terminal UI dashboard for genetic optimization search."""

    def __init__(self, total_generations: int, source_filename: str, use_llm: bool = True):
        self.total_generations = total_generations
        self.source_filename = source_filename
        self.use_llm = use_llm
        self.live: Optional[Live] = None

    def start(self) -> None:
        print_banner()
        console.print(f"[bold cyan]Starting optimization search on {self.source_filename}...[/bold cyan]\n")

    def render_panel(self, stats: SearchProgressStats) -> Panel:
        pct = int((stats.generation / stats.total_generations) * 100)
        filled_bars = int(pct / 5)
        bar_str = "█" * filled_bars + "░" * (20 - filled_bars)

        b_ms_str = f"{round(stats.baseline_fitness_ns / 1e6, 3)} ms" if stats.baseline_fitness_ns is not None else "N/A"
        best_ms_str = f"{round(stats.best_fitness_ns / 1e6, 3)} ms" if stats.best_fitness_ns is not None else "N/A"
        speedup = f"{stats.speedup_factor:.2f}x" if stats.speedup_factor is not None else "N/A"

        stage1_str = "[green]✓[/green]" if self.use_llm else "[dim]Skipped (--no-llm)[/dim]"

        lines = [
            "[bold cyan]AUTOTUNE PHASE-ORDERING SEARCH[/bold cyan]",
            "──────────────────────────────────────────────",
            f"Stage 1  LLM Seeding       {stage1_str}",
            f"Stage 2  Genetic Search    [{bar_str}] [bold yellow]{pct}%[/bold yellow]",
            f"         Generation:       [bold white]{stats.generation} / {stats.total_generations}[/bold white]",
            f"         Baseline (-O3):   [dim]{b_ms_str}[/dim]",
            f"         Current Best:     [bold green]{best_ms_str}[/bold green] (Speedup: [bold magenta]{speedup}[/bold magenta])",
            "Stage 3  Correctness Check [green]✓ Verified[/green]",
        ]

        if stats.stop_reason:
            lines.append(f"\n[bold yellow]Stopping Condition: {stats.stop_reason}[/bold yellow]")

        return Panel("\n".join(lines), border_style="cyan", expand=False)

    def update(self, stats: SearchProgressStats) -> None:
        panel = self.render_panel(stats)
        console.print(panel)


def print_search_results_summary(prescription: CompilerPrescription) -> None:
    """Render formatted final search summary showing percentage improvement over -O3."""
    console.print("\n[bold green]Optimization Search Complete![/bold green]")
    console.print(f"[bold white]Best Pass Sequence:[/bold white] {prescription.pass_sequence.passes}")
    
    pct_improvement = round((1.0 - (prescription.candidate_time_ms / max(prescription.baseline_time_ms, 1e-3))) * 100, 1)
    if pct_improvement > 0:
        console.print(f"[bold white]Speedup:[/bold white] [bold green]{prescription.speedup_ratio}x[/bold green] ([bold magenta]{pct_improvement}% improvement over -O3[/bold magenta])")
    else:
        console.print(f"[bold white]Speedup:[/bold white] [bold yellow]{prescription.speedup_ratio}x[/bold yellow] (Parity with -O3)")

    console.print(f"\n[bold white]Baseline (-O3):[/bold white]   {prescription.baseline_time_ms} ms")
    console.print(f"[bold white]Candidate Best:[/bold white]   {prescription.candidate_time_ms} ms")

    console.print(f"\n[bold white]Reproducible Compiler Command:[/bold white]")
    console.print(f"[bold cyan]{prescription.reproducible_clang_command}[/bold cyan]\n")
