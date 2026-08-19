# Security Policy & Responsible Use

## Supported Versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |
| < 0.1.0 | No |

---

## Reporting a Vulnerability

We take the security and safety of compiler optimization toolchains seriously.

If you discover a security issue, credential leakage vulnerability, or process sandbox escape in Autotune:

1. **Do NOT open a public GitHub issue.**
2. Send a report via email to `security@autotune.dev` with:
   - Description of the vulnerability.
   - Steps or proof-of-concept script to reproduce.
   - Potential impact on system or credentials.
3. We will acknowledge receipt within 48 hours and work on a fix promptly.

---

## Keyring Credential Safety

Autotune uses standard operating system Keyrings (macOS Keychain / Linux SecretService) via the Python `keyring` library to store API keys securely.

- API keys are **never** logged to stdout/stderr.
- API keys are **never** written to experiment manifest JSON files or reports.
- Users can run Autotune 100% offline using `--no-llm` without supplying any credentials.
