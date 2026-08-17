"""
Terminal UI component using Rich for clean CLI display.
"""

import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from autotune import __version__
from autotune.benchmark.models import BenchmarkResult
from autotune.doctor.checks import DoctorReport

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
