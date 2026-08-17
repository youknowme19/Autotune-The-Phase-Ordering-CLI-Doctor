"""
Process group signal management and cleanup.
"""

import os
import signal
import subprocess
from typing import Optional


def kill_process_group(proc: subprocess.Popen) -> None:
    """Kill process group cleanly using SIGKILL."""
    try:
        if proc.poll() is None:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
