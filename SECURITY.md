# Security Policy & Execution Model

## Reporting Vulnerabilities
If you discover a security vulnerability in Autotune, please report it securely via [GitHub Security Advisories](https://github.com/youknowme19/Autotune-The-Phase-Ordering-CLI-Doctor/security/advisories).

## Execution Security & Isolation Model

1. **Subprocess Isolation**: Candidate binaries are executed in isolated temporary directories using strict `execve` argument structures (`shell=False`) to prevent command line shell injection vulnerabilities.
2. **Stream Truncation Caps**: Candidate `stdout` and `stderr` execution streams are capped at **10MB** to prevent unbounded memory amplification or log disk-filling attacks.
3. **Environment Sanitization**: `EnvironmentFingerprint` captures non-sensitive system metadata (OS, CPU, Clang/Opt versions) and explicitly excludes usernames, home directory paths, and environment secrets.
4. **Signal & Timeout Safeguards**: Execution timeouts are enforced via POSIX signal handlers (`SIGTERM`, `SIGKILL`) to prevent zombie candidate processes.
