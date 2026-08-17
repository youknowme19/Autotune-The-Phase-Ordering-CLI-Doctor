"""
Sandbox isolation metadata and platform security context.
"""

import platform
from pydantic import BaseModel


class SandboxCapabilities(BaseModel):
    os_name: str
    has_cgroups: bool = False
    has_namespaces: bool = False
    has_process_group_isolation: bool = True
    has_timeout_enforcement: bool = True
    isolation_level: str = "Standard Process Group Isolation"


def get_sandbox_capabilities() -> SandboxCapabilities:
    os_name = platform.system()
    if os_name == "Linux":
        return SandboxCapabilities(
            os_name=os_name,
            has_cgroups=True,
            has_namespaces=True,
            has_process_group_isolation=True,
            has_timeout_enforcement=True,
            isolation_level="Linux Namespace & Process Group Sandbox",
        )
    else:
        return SandboxCapabilities(
            os_name=os_name,
            has_cgroups=False,
            has_namespaces=False,
            has_process_group_isolation=True,
            has_timeout_enforcement=True,
            isolation_level="macOS Process Group Sandbox with Signal Timeout",
        )
