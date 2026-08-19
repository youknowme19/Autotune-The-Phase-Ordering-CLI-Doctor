"""
Isolated subprocess sandbox executor.
"""

import os
import subprocess
import tempfile
from typing import Optional
from pydantic import BaseModel

from autotune.doctor.errors import DoctorError, ErrorCode
from autotune.sandbox.timeout import kill_process_group


class SandboxExecutionResult(BaseModel):
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    error_message: Optional[str] = None


class SandboxExecutor:
    """Executes candidate binaries in an isolated process sandbox with strict timeouts."""

    def __init__(self, default_timeout_seconds: float = 5.0):
        self.default_timeout_seconds = default_timeout_seconds

    def execute(
        self,
        binary_path: str,
        workload_path: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        cwd: Optional[str] = None,
    ) -> SandboxExecutionResult:
        timeout = (
            timeout_seconds
            if timeout_seconds is not None
            else self.default_timeout_seconds
        )
        if not os.path.exists(binary_path):
            return SandboxExecutionResult(
                success=False,
                exit_code=-1,
                error_message=f"Binary not found: {binary_path}",
            )

        cmd = [os.path.abspath(binary_path)]
        stdin_data: Optional[str] = None

        if workload_path and os.path.exists(workload_path):
            with open(workload_path, "r", encoding="utf-8") as f:
                stdin_data = f.read()

        execution_dir = cwd or os.path.dirname(os.path.abspath(binary_path))

        proc = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if stdin_data else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=execution_dir,
                start_new_session=True,  # Isolate into new process group
            )

            stdout, stderr = proc.communicate(input=stdin_data, timeout=timeout)

            err_msg: Optional[str] = None
            if proc.returncode != 0:
                import signal

                sig_details = ""
                if proc.returncode < 0:
                    try:
                        sig_details = f" ({signal.Signals(-proc.returncode).name})"
                    except Exception:
                        sig_details = ""
                elif proc.returncode > 128:
                    signum = proc.returncode - 128
                    try:
                        sig_details = f" ({signal.Signals(signum).name})"
                    except Exception:
                        sig_details = ""

                err_msg = f"Executable exited with non-zero return code {proc.returncode}{sig_details}."
                if stderr and stderr.strip():
                    err_msg += f" Stderr: {stderr.strip()}"

            return SandboxExecutionResult(
                success=(proc.returncode == 0),
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=proc.returncode,
                timed_out=False,
                error_message=err_msg,
            )

        except subprocess.TimeoutExpired:
            if proc:
                kill_process_group(proc)
            e02 = DoctorError(
                ErrorCode.E02,
                f"Candidate binary execution timed out after {timeout} seconds.",
            )
            return SandboxExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=True,
                error_message=str(e02),
            )
        except Exception as e:
            if proc:
                kill_process_group(proc)
            return SandboxExecutionResult(
                success=False,
                stdout="",
                stderr="",
                exit_code=-1,
                timed_out=False,
                error_message=f"Execution exception: {str(e)}",
            )
