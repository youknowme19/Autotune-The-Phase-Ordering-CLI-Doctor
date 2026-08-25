# Configuration Reference

Autotune parameters can be configured via CLI flags, environment variables, or configuration files.

---

## ⚙️ Search Parameters

| Parameter | Type | Default | Allowed Values | Source File / Implementation | Description |
|---|---|---|---|---|---|
| `population_size` | `int` | `10` | $\ge 2$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Number of candidate pass sequences in GA population. |
| `generations` | `int` | `5` | $\ge 1$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Number of generational evolution cycles. |
| `seed` | `int` | `42` | Any int | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Random seed for population initialization and mutation operators. |
| `workers` | `int` | `4` | $\ge 1$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Parallel evaluation workers (`ThreadPoolExecutor`). |
| `fidelity` | `str` | `LOW` | `LOW`, `MEDIUM`, `HIGH` | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Evaluation fidelity stage. |
| `screen_runs` | `int` | `3` | $\ge 1$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Number of timing repetitions during `LOW` fidelity screening. |
| `confirm_runs` | `int` | `20` | $\ge 1$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Number of timing repetitions during final confirmation. |
| `baseline_gate` | `bool` | `True` | `True`, `False` | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Enable baseline gate candidate pruning. |
| `gate_threshold` | `float` | `0.80` | $> 0.0$ | [`GeneticAlgorithmEngine`](../src/autotune/search/genetic.py) | Pruning cutoff threshold ($\text{normalized\_speed} < 0.80$). |

---

## 🔑 Credential & LLM Parameters

| Parameter / Env Var | Type | Default | Keyring Service Name | Description |
|---|---|---|---|---|
| `OPENAI_API_KEY` | `str` | `None` | `autotune-openai` | API key for OpenAI LLM seed generation. |
| `ANTHROPIC_API_KEY` | `str` | `None` | `autotune-anthropic` | API key for Anthropic LLM seed generation. |
| `GEMINI_API_KEY` | `str` | `None` | `autotune-gemini` | API key for Google Gemini LLM seed generation. |

Credential resolution order:
1. Environment variable (`OPENAI_API_KEY`, etc.)
2. OS Keyring (`keyring.get_password("autotune-<provider>", "default")`)
3. Offline AST heuristic fallback

---

## 🗄️ Cache Directory Structure

Default cache directory: `.autotune/cache/` (or custom path passed to `PersistentCacheManager`):

```text
.autotune/cache/
├── compilation/   # SHA256(source + pipeline + toolchain).json & .bin
├── correctness/   # SHA256(compilation_key + strategy + workload).json
├── performance/   # SHA256(compilation_key + workload + backend + warmup + runs).json
├── fitness/       # Cached individual evaluation records
└── seeds/         # Confirmed speedup seed pipelines
```
