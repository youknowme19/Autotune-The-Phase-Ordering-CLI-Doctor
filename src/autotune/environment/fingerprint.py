"""
System and Toolchain Environment Fingerprinting for Scientific Reproducibility.
Captures non-sensitive, serializable system and compiler environment metadata.
"""

import hashlib
import os
import platform
import sys
from typing import Optional
from pydantic import BaseModel, Field

from autotune import __version__ as AUTOTUNE_VERSION
from autotune.doctor.checks import find_tool, get_command_output


class EnvironmentFingerprint(BaseModel):
    """Non-sensitive system and toolchain environment fingerprint."""

    os_name: str
    os_release: str
    architecture: str
    cpu_info: str
    logical_cpu_count: int
    physical_cpu_count: int
    clang_path: str
    clang_version: str
    opt_version: str
    target_triple: str = "unknown"
    python_version: str
    autotune_version: str = AUTOTUNE_VERSION
    fingerprint_hash: str = ""

    def compute_hash(self) -> str:
        data = f"{self.os_name}:{self.architecture}:{self.cpu_info}:{self.clang_version}:{self.target_triple}:{self.autotune_version}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()[:16]


class EnvironmentFingerprinter:
    """Collects system environment metadata."""

    @staticmethod
    def capture(clang_path: Optional[str] = None) -> EnvironmentFingerprint:
        os_name = platform.system()
        os_rel = platform.release()
        arch = platform.machine()

        logical_cpus = os.cpu_count() or 1
        physical_cpus = logical_cpus

        cpu_info = "Unknown CPU"
        if os_name == "Darwin":
            cpu_info = "Apple Silicon" if arch == "arm64" else "Intel Mac"
        elif os_name == "Linux":
            cpu_info = f"Linux {arch}"

        c_path = find_tool("clang", clang_path) or "clang"
        c_ver = get_command_output([c_path, "--version"]) or "Clang Unknown"
        if "\n" in c_ver:
            c_ver = c_ver.splitlines()[0]

        target_triple = get_command_output([c_path, "-dumpmachine"]) or f"{arch}-{os_name.lower()}"

        o_path = find_tool("opt") or "opt"
        o_ver = get_command_output([o_path, "--version"]) or "Opt Unknown"
        if "\n" in o_ver:
            o_ver = o_ver.splitlines()[0]

        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"

        fp = EnvironmentFingerprint(
            os_name=os_name,
            os_release=os_rel,
            architecture=arch,
            cpu_info=cpu_info,
            logical_cpu_count=logical_cpus,
            physical_cpu_count=physical_cpus,
            clang_path=c_path,
            clang_version=c_ver,
            opt_version=o_ver,
            target_triple=target_triple,
            python_version=py_ver,
            autotune_version=AUTOTUNE_VERSION,
        )
        fp.fingerprint_hash = fp.compute_hash()
        return fp
