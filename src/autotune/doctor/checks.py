"""
Environment toolchain and system diagnostic checks.
"""

import os
import platform
import shutil
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel

from autotune.doctor.errors import DoctorError, ErrorCode


class DoctorReport(BaseModel):
    python_version: str
    python_ok: bool

    os_name: str
    arch: str
    cpu_info: str

    clang_path: Optional[str] = None
    clang_version: Optional[str] = None
    clang_ok: bool = False

    opt_path: Optional[str] = None
    opt_version: Optional[str] = None
    opt_ok: bool = False

    llvm_version: Optional[str] = None

    measurement_backend: str
    warnings: List[str] = []
    errors: List[str] = []

    @property
    def is_healthy(self) -> bool:
        return self.python_ok and self.clang_ok


def find_tool(
    tool_name: str, custom_path: Optional[str] = None
) -> Optional[str]:
    """Find absolute path of a tool, prioritizing matching LLVM toolchain paths."""
    if custom_path and os.path.exists(custom_path) and os.access(custom_path, os.X_OK):
        return custom_path

    # Prioritize matching LLVM Homebrew & Linux toolchain paths first for clang/opt version parity
    candidate_paths = [
        f"/opt/homebrew/opt/llvm/bin/{tool_name}",
        f"/usr/local/opt/llvm/bin/{tool_name}",
        f"/usr/lib/llvm-19/bin/{tool_name}",
        f"/usr/lib/llvm-18/bin/{tool_name}",
        f"/usr/lib/llvm-17/bin/{tool_name}",
        f"/usr/lib/llvm-16/bin/{tool_name}",
        f"/usr/lib/llvm-15/bin/{tool_name}",
        f"/usr/lib/llvm-14/bin/{tool_name}",
    ]
    for candidate in candidate_paths:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate

    # Standard PATH search
    which_path = shutil.which(tool_name)
    if which_path:
        return which_path

    if os.path.exists(f"/usr/bin/{tool_name}") and os.access(f"/usr/bin/{tool_name}", os.X_OK):
        return f"/usr/bin/{tool_name}"

    return None


def get_command_output(cmd: List[str]) -> Optional[str]:
    try:
        res = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5
        )
        if res.returncode == 0:
            return res.stdout.strip()
    except Exception:
        pass
    return None


def run_doctor_checks(
    custom_clang: Optional[str] = None, custom_opt: Optional[str] = None
) -> DoctorReport:
    """Run complete environment diagnostic checks."""
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 11)

    os_name = platform.system()
    arch = platform.machine()
    cpu_info = platform.processor() or arch
    if os_name == "Darwin" and arch == "arm64":
        cpu_info = "Apple Silicon (ARM64)"

    warnings: List[str] = []
    errors: List[str] = []

    # 1. Opt check first to locate LLVM toolchain dir
    opt_path = find_tool("opt", custom_opt)

    # 2. Clang check (prefer matching clang from same directory as opt if found)
    if opt_path and not custom_clang:
        same_dir_clang = os.path.join(os.path.dirname(opt_path), "clang")
        if os.path.exists(same_dir_clang) and os.access(same_dir_clang, os.X_OK):
            custom_clang = same_dir_clang

    clang_path = find_tool("clang", custom_clang)
    clang_version = None
    clang_ok = False
    if clang_path:
        out = get_command_output([clang_path, "--version"])
        if out:
            clang_version = out.splitlines()[0]
            clang_ok = True
        else:
            errors.append(f"Clang binary at {clang_path} failed execution check.")
    else:
        errors.append("Clang executable not found in PATH or standard LLVM installation paths.")

    opt_version = None
    opt_ok = False
    llvm_version = None
    if opt_path:
        out = get_command_output([opt_path, "--version"])
        if out:
            opt_version = out.splitlines()[0]
            opt_ok = True
            for line in out.splitlines():
                if "LLVM version" in line or "version" in line:
                    llvm_version = line.strip()
                    break
        else:
            warnings.append(f"Opt binary at {opt_path} failed execution check.")
    else:
        warnings.append(
            "LLVM 'opt' binary not found. Clang pipeline fallback will be used if needed."
        )

    # 3. Measurement backend determination
    if os_name == "Linux":
        measurement_backend = "Linux performance counters (perf_event_open)"
    elif os_name == "Darwin":
        measurement_backend = "macOS high-precision timing"
        e01 = DoctorError(
            ErrorCode.E01,
            "Hardware performance counters are not available through the Linux backend on macOS.",
            "Using macOS timing backend for development.",
        )
        warnings.append(e01.format_warning())
    else:
        measurement_backend = f"{os_name} standard timing backend"

    return DoctorReport(
        python_version=py_ver,
        python_ok=py_ok,
        os_name=os_name,
        arch=arch,
        cpu_info=cpu_info,
        clang_path=clang_path,
        clang_version=clang_version,
        clang_ok=clang_ok,
        opt_path=opt_path,
        opt_version=opt_version,
        opt_ok=opt_ok,
        llvm_version=llvm_version or clang_version,
        measurement_backend=measurement_backend,
        warnings=warnings,
        errors=errors,
    )
