# Release Readiness & Verification Manifest

This document records the official release readiness audit and automated validation gate matrix for **Autotune — The Phase-Ordering CLI Doctor**.

---

## 📦 Package Metadata

- **Package Name**: `autotune-doctor`
- **Current Version**: `0.3.0`
- **Build Backend**: `flit_core.buildapi`
- **CLI Entrypoint**: `autotune = "autotune.cli:app"`
- **License**: Apache-2.0
- **Supported Python Versions**: $\ge 3.10$ (Tested on 3.11 & 3.12)

---

## 🔍 Automated Verification Gate Matrix

| Audit Dimension | Status | Verification Method |
| :--- | :--- | :--- |
| **Unit Test Suite** | `AUTOMATEDLY VERIFIED` | 119/119 unit tests passing cleanly (`.venv/bin/pytest -v`). |
| **Scientific Integrity** | `AUTOMATEDLY VERIFIED` | `Search Best` (exploratory) strictly separated from `Confirmed Speedup` (authoritative evidence). |
| **Evidence Evaluator** | `AUTOMATEDLY VERIFIED` | Deterministic decision tree enforced (`Grade A/B/C/D/F`). Boundary tests passing. |
| **Anti-Fabrication** | `AUTOMATEDLY VERIFIED` | All $p$-values, $CV\%$, and Cohen's $d$ metrics derived from raw timing samples. Zero hardcoded defaults. |
| **Prescription Safety** | `AUTOMATEDLY VERIFIED` | `PrescriptionBuilder` never generates positive recommendations for Grades C, D, or F. |
| **KnowledgeStore Filter**| `AUTOMATEDLY VERIFIED` | SQLite memory persists Grade A and Grade B entries only. Grades C, D, and F are rejected. |
| **CI Performance Gate** | `AUTOMATEDLY VERIFIED` | `autotune gate` requires BOTH speedup threshold AND Grade A/B evidence grade. |
| **Subprocess Security** | `AUTOMATEDLY VERIFIED` | `shell=False`, argument array execution, POSIX signal timeouts (`SIGTERM`/`SIGKILL`), 10MB stream caps. |
| **HTML Report Security**| `AUTOMATEDLY VERIFIED` | `HTMLReportGenerator` escapes user-controlled strings using HTML entity encoding. XSS tests passed. |
| **Path Link Hygiene** | `AUTOMATEDLY VERIFIED` | Zero tracked secrets or absolute local machine paths (`/Volumes/`, `/Users/`, `file:///`). |
| **Packaging Build** | `AUTOMATEDLY VERIFIED` | Clean `sdist` (`tar.gz`) and `wheel` (`.whl`) build via `python -m build`. |

---

## 🔑 Human Actions Required for Distribution

| Task | Status | Requirement |
| :--- | :--- | :--- |
| **PyPI Package Publishing** | `HUMAN ACTION REQUIRED` | Requires maintainer PyPI API token / credentials (`flit publish` or `twine upload`). |
| **GitHub Branch Protection** | `HUMAN ACTION REQUIRED` | Maintainer can enable branch protection on `main` via GitHub web settings. |

---

## ⚖️ Final Release Verdict

**RELEASE READY WITH HUMAN ACTION REQUIRED**
