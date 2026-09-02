# Security Policy

## Supported Versions

We actively support security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.3.x   | :white_check_mark: |
| < 0.3.0 | :x:                |

---

## Security Invariants in Autotune

Autotune is designed with strict security invariants for enterprise and research compiler environments:

1. **Zero Secret Leakage**:
   - LLM API keys configured via `autotune config keyring` or environment variables are stored in the operating system's native secret storage (`Keychain` on macOS, `SecretService` on Linux).
   - Secret keys are stripped and filtered from all standard output, console panels, JSON reports, HTML artifacts, and generated build scripts.
2. **Process Sandboxing**:
   - Candidate executions are run under strict time limits (`--timeout`) and resource constraints to prevent denial-of-service or infinite loops caused by pathological pass combinations.
3. **Non-Destructive Workflows**:
   - `autotune apply` and `autotune doctor` generate artifacts into dedicated directories (`.autotune/artifacts/` or specified directories) and **never overwrite or modify original user source files**.

---

## Reporting a Vulnerability

If you discover a security vulnerability in Autotune, please do **NOT** open a public GitHub issue.

Instead, please send a report to:
`security@autotune.dev`

Please include:
* Description of the vulnerability.
* Steps or minimal code snippet to reproduce.
* Potential impact.
* Suggested fix (if known).

You will receive an acknowledgment within 48 hours, followed by regular updates until a patch is released.
