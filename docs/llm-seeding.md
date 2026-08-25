# LLM-Guided Seeding

This document details Autotune's optional LLM seed generation client, AST feature prompt formatting, and fallback mechanisms.

---

## 🤖 Role of LLMs in Autotune

LLMs (OpenAI, Anthropic, Gemini) act strictly as **Generation 0 seed proposal generators**.

- **What LLMs Do**: Analyze AST structural features (loop nest depth, array access indices, math intensity) and propose initial pass sequences tailored to the code structure.
- **What LLMs DO NOT Do**: LLMs do **never** declare a winner or guarantee performance gains. All proposals must pass compilation, correctness checks, and empirical timing evaluations.

---

## 🔍 AST Feature Prompt Extraction ([`src/autotune/analysis/features.py`](../src/autotune/analysis/features.py))

Before invoking an LLM, `FeatureExtractor` extracts compact structural metadata from Clang AST dumps:

```json
{
  "functions": 1,
  "loops": 2,
  "max_loop_depth": 2,
  "array_subscripts": 8,
  "float_ops": 4,
  "branch_statements": 0,
  "memory_ops": 12
}
```

This structural JSON is passed to the LLM client to generate context-aware pass sequences.

---

## 🔀 Fallback Heuristics & `--no-llm` Mode

If no API key is configured or if `--no-llm` is specified:
- Autotune bypasses LLM network calls entirely.
- Uses offline AST heuristics and deterministic random seeding (`--seed 42`).
- Ensures 100% reproducible population initialization.
