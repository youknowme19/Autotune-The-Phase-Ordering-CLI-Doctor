"""
ExportService: Exports reproducible build configurations and compilation recipes
in JSON, Shell, CMake, and Make formats for integrating Autotune optimizations into real projects.
Supports exporting single recipe files or full directory bundles (prescription.txt, reproduce.sh, prescription.json).
"""

import json
import os
from typing import Optional
from pydantic import BaseModel


class ExportResult(BaseModel):
    format: str
    content: str
    output_path: Optional[str] = None


class ExportService:
    """Exports optimization reports into build system scripts and configurations."""

    @staticmethod
    def export(
        report_path: str,
        export_format: str = "json",
        output_path: Optional[str] = None,
    ) -> ExportResult:
        if not os.path.exists(report_path):
            raise FileNotFoundError(f"Optimization report '{report_path}' not found.")

        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fmt = export_format.lower().strip()
        source = data.get("source_path", "kernel.c")
        source_name = os.path.basename(source)
        stem = os.path.splitext(source_name)[0]
        run_id = data.get("run_id", "run_unknown")
        src_hash = data.get("source_hash", "unknown")
        p_data = data.get("prescription", {})
        doc_data = data.get("doctor_report", {})
        passes = p_data.get("pass_sequence", {}).get("passes", [])
        passes_str = ",".join(passes)
        clang_bin = doc_data.get("clang_path", "clang")
        opt_bin = doc_data.get("opt_path", "opt")
        arch = doc_data.get("arch", "native")
        triple = doc_data.get("target_triple", "native")
        speedup = data.get("confirmed_speedup", p_data.get("speedup_ratio", 1.0))
        clang_cmd = p_data.get("reproducible_clang_command", f"clang -O0 -emit-llvm {source} ...")

        # Build individual representations
        json_dict = {
            "experiment_id": run_id,
            "source_file": source,
            "source_hash": src_hash,
            "target_arch": arch,
            "target_triple": triple,
            "compiler": clang_bin,
            "optimizer": opt_bin,
            "pass_pipeline": passes,
            "confirmed_speedup": speedup,
            "reproducible_clang_command": clang_cmd,
        }
        json_content = json.dumps(json_dict, indent=2)

        shell_content = f"""#!/usr/bin/env bash
# ==============================================================================
# Autotune Reproducible Compilation Script
# Experiment ID: {run_id}
# Target:        {source_name} (SHA256: {src_hash[:16]}...)
# Speedup:       {speedup:.2f}x over -O3
# ==============================================================================
set -euo pipefail

CLANG="{clang_bin}"
OPT="{opt_bin}"
SOURCE="{source}"
OUTPUT="{stem}.opt.bin"
PASSES="{passes_str}"

echo "[Autotune] Lowering source to unoptimized LLVM IR..."
$CLANG -O0 -Xclang -disable-O0-optnone -emit-llvm -c "$SOURCE" -o "{stem}.raw.bc"

echo "[Autotune] Applying custom pass pipeline: $PASSES..."
$OPT -passes="$PASSES" "{stem}.raw.bc" -o "{stem}.opt.bc"

echo "[Autotune] Emitting native binary $OUTPUT..."
$CLANG "{stem}.opt.bc" -o "$OUTPUT"

echo "[Autotune] Done. Optimized binary created at $OUTPUT"
"""

        cmake_content = f"""# ==============================================================================
# Autotune CMake Build Integration
# Experiment ID: {run_id} | Source: {source_name} | Speedup: {speedup:.2f}x
# ==============================================================================
cmake_minimum_required(VERSION 3.20)

find_program(AUTOTUNE_CLANG NAMES clang REQUIRED)
find_program(AUTOTUNE_OPT NAMES opt REQUIRED)

set(AUTOTUNE_PASS_PIPELINE "{passes_str}")

function(add_autotune_executable TARGET_NAME SOURCE_FILE)
    get_filename_component(SRC_NAME ${{SOURCE_FILE}} NAME_WE)
    set(RAW_BC "${{CMAKE_CURRENT_BINARY_DIR}}/${{SRC_NAME}}.raw.bc")
    set(OPT_BC "${{CMAKE_CURRENT_BINARY_DIR}}/${{SRC_NAME}}.opt.bc")

    add_custom_command(
        OUTPUT ${{RAW_BC}}
        COMMAND ${{AUTOTUNE_CLANG}} -O0 -Xclang -disable-O0-optnone -emit-llvm -c ${{SOURCE_FILE}} -o ${{RAW_BC}}
        DEPENDS ${{SOURCE_FILE}}
        COMMENT "Autotune: Lowering ${{SOURCE_FILE}} to LLVM IR"
    )

    add_custom_command(
        OUTPUT ${{OPT_BC}}
        COMMAND ${{AUTOTUNE_OPT}} -passes=${{AUTOTUNE_PASS_PIPELINE}} ${{RAW_BC}} -o ${{OPT_BC}}
        DEPENDS ${{RAW_BC}}
        COMMENT "Autotune: Running optimization pipeline (${{AUTOTUNE_PASS_PIPELINE}})"
    )

    add_executable(${{TARGET_NAME}} ${{OPT_BC}})
    set_target_properties(${{TARGET_NAME}} PROPERTIES LINKER_LANGUAGE C)
endfunction()
"""

        make_content = f"""# ==============================================================================
# Autotune Makefile Integration
# Experiment ID: {run_id} | Source: {source_name} | Speedup: {speedup:.2f}x
# ==============================================================================
CLANG ?= {clang_bin}
OPT ?= {opt_bin}
AUTOTUNE_PASSES := {passes_str}

%.raw.bc: %.c
\t$(CLANG) -O0 -Xclang -disable-O0-optnone -emit-llvm -c $< -o $@

%.opt.bc: %.raw.bc
\t$(OPT) -passes="$(AUTOTUNE_PASSES)" $< -o $@

%.opt.bin: %.opt.bc
\t$(CLANG) $< -o $@

.PHONY: clean-autotune
clean-autotune:
\trm -f *.raw.bc *.opt.bc *.opt.bin
"""

        txt_content = f"""AUTOTUNE COMPILER PRESCRIPTION
==============================
Source Path:     {source}
Speedup Ratio:   {speedup:.2f}x
Pass Sequence:   {passes}

Reproducible Compiler Command:
{clang_cmd}
"""

        ninja_content = f"""# ==============================================================================
# Autotune Ninja Build Rules
# Experiment ID: {run_id} | Source: {source_name} | Speedup: {speedup:.2f}x
# ==============================================================================
ninja_required_version = 1.10

clang = {clang_bin}
opt = {opt_bin}
passes = {passes_str}

rule emit_bc
  command = $clang -O0 -Xclang -disable-O0-optnone -emit-llvm -c $in -o $out
  description = Autotune: Compiling $in to raw bitcode

rule optimize_bc
  command = $opt -passes=$passes $in -o $out
  description = Autotune: Optimizing $in with ($passes)

rule link_bin
  command = $clang $in -o $out
  description = Autotune: Linking native binary $out

build {stem}.raw.bc: emit_bc {source}
build {stem}.opt.bc: optimize_bc {stem}.raw.bc
build {stem}.opt.bin: link_bin {stem}.opt.bc

default {stem}.opt.bin
"""

        meson_content = f"""# ==============================================================================
# Autotune Meson Build Definition
# Experiment ID: {run_id} | Source: {source_name} | Speedup: {speedup:.2f}x
# ==============================================================================
project('autotune-{stem}', 'c', version: '0.4.0')

clang = find_program('clang')
opt = find_program('opt')

raw_bc = custom_target('{stem}_raw_bc',
  input: '{source}',
  output: '{stem}.raw.bc',
  command: [clang, '-O0', '-Xclang', '-disable-O0-optnone', '-emit-llvm', '-c', '@INPUT@', '-o', '@OUTPUT@']
)

opt_bc = custom_target('{stem}_opt_bc',
  input: raw_bc,
  output: '{stem}.opt.bc',
  command: [opt, '-passes={passes_str}', '@INPUT@', '-o', '@OUTPUT@']
)

executable('{stem}.opt.bin', opt_bc)
"""

        format_map = {
            "json": json_content,
            "shell": shell_content,
            "cmake": cmake_content,
            "make": make_content,
            "ninja": ninja_content,
            "meson": meson_content,
        }

        content = format_map.get(fmt, json_content)

        if output_path:
            is_file_path = any(output_path.endswith(ext) for ext in [".json", ".sh", ".cmake", ".make", ".txt", ".mk"])
            
            if is_file_path:
                os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(content)
                if output_path.endswith(".sh"):
                    os.chmod(output_path, 0o755)
            else:
                # Output path is a directory: generate complete bundle
                os.makedirs(output_path, exist_ok=True)
                with open(os.path.join(output_path, "prescription.txt"), "w", encoding="utf-8") as f:
                    f.write(txt_content)
                sh_file = os.path.join(output_path, "reproduce.sh")
                with open(sh_file, "w", encoding="utf-8") as f:
                    f.write(shell_content)
                os.chmod(sh_file, 0o755)
                with open(os.path.join(output_path, "prescription.json"), "w", encoding="utf-8") as f:
                    json.dump(p_data if p_data else json_dict, f, indent=2)
                with open(os.path.join(output_path, "CMakeLists.txt"), "w", encoding="utf-8") as f:
                    f.write(cmake_content)
                with open(os.path.join(output_path, "Makefile"), "w", encoding="utf-8") as f:
                    f.write(make_content)

        return ExportResult(
            format=fmt,
            content=content,
            output_path=output_path,
        )
