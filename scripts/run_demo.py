#!/usr/bin/env python3
"""
Baseline demo script running Autotune diagnosis flow.
"""

import os
from autotune.benchmark import get_performance_runner
from autotune.doctor import run_doctor_checks
from autotune.llvm import CompilerDriver
from autotune.ui import print_diagnose_summary

def main():
    kernel = "examples/simple_loop/kernel.c"
    workload = "examples/simple_loop/input.txt"

    if not os.path.exists(kernel):
        print(f"Kernel file {kernel} not found.")
        return

    doc_report = run_doctor_checks()
    compiler = CompilerDriver(clang_path=doc_report.clang_path, opt_path=doc_report.opt_path)
    runner = get_performance_runner(
        platform_name=doc_report.os_name,
        architecture=doc_report.arch,
        compiler_version=doc_report.clang_version or "Clang",
        cpu_info=doc_report.cpu_info,
    )

    out_bin = "/tmp/autotune_demo_kernel.bin"
    comp_res = compiler.compile_baseline(kernel, out_bin, opt_level="-O3")
    if not comp_res.success:
        print(f"Compilation failed: {comp_res.error_message}")
        return

    bench_res = runner.run_benchmark(out_bin, workload_path=workload, repetitions=10)
    print_diagnose_summary(kernel, doc_report, baseline_result=bench_res)

if __name__ == "__main__":
    main()
