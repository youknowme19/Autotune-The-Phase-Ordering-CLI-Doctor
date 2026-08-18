"""
LLM Client abstractions, provider clients (OpenAI, Anthropic, Gemini, Heuristic), and JSON schema validation gate.
"""

from abc import ABC, abstractmethod
import json
import os
import urllib.request
from typing import List, Optional
from autotune.analysis.features import CompactCodeFeatures
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from autotune.llm.schema import LLMPassPipelineCandidate, LLMPipelineResponseSchema


class LLMClient(ABC):
    """Abstract interface for LLM pass sequence generators with structured JSON validation gate."""

    def __init__(self, validator: Optional[PassValidator] = None):
        self.validator = validator or PassValidator()

    def filter_and_validate_candidates(self, raw_candidates: List[LLMPassPipelineCandidate]) -> List[PassSequence]:
        """Pass Validation Gate: Intercept LLM proposals and filter out hallucinated passes before GA seeding."""
        validated_sequences: List[PassSequence] = []

        for cand in raw_candidates:
            raw_seq = PassSequence(passes=cand.passes)
            clean_seq = self.validator.filter_sequence(raw_seq)
            if clean_seq.passes:
                validated_sequences.append(clean_seq)

        return validated_sequences

    @abstractmethod
    def generate_candidates(
        self, features: CompactCodeFeatures, count: int = 4
    ) -> List[PassSequence]:
        """Generate validated LLVM pass sequences based on compact code features."""
        pass


class HeuristicSeedClient(LLMClient):
    """Zero-API offline heuristic seed generator deriving pass sequences from AST code features."""

    def generate_candidates(
        self, features: CompactCodeFeatures, count: int = 4
    ) -> List[PassSequence]:
        candidates: List[LLMPassPipelineCandidate] = []
        summary = features.summary

        # 1. Loop-heavy sequence
        if summary.loop_count > 0:
            candidates.append(
                LLMPassPipelineCandidate(
                    name="Loop Optimization Pipeline",
                    rationale="LICM, Loop Rotate, and Loop Unrolling for loop nests.",
                    passes=["mem2reg", "sroa", "loop-rotate", "licm", "instcombine", "loop-unroll"],
                )
            )

        # 2. Vectorization & SIMD sequence
        if summary.has_arrays_or_pointers or summary.float_ops > 0:
            candidates.append(
                LLMPassPipelineCandidate(
                    name="Vectorization Pipeline",
                    rationale="SROA, GVN, and Loop Vectorize for SIMD utilization.",
                    passes=["mem2reg", "sroa", "early-cse", "gvn", "loop-vectorize", "slp-vectorize"],
                )
            )

        # 3. Scalar cleanup sequence
        candidates.append(
            LLMPassPipelineCandidate(
                name="Scalar DCE Pipeline",
                rationale="SimplifyCFG and DCE for scalar cleanup.",
                passes=["mem2reg", "simplifycfg", "sccp", "dce", "memcpyopt", "gvn"],
            )
        )

        # 4. Inlining & Reassociation sequence
        candidates.append(
            LLMPassPipelineCandidate(
                name="Inline & Reassociation Pipeline",
                rationale="Inlining and arithmetic reassociation.",
                passes=["mem2reg", "inline", "reassociate", "instcombine", "loop-simplify", "indvars"],
            )
        )

        return self.filter_and_validate_candidates(candidates[:count])


class MockLLMClient(HeuristicSeedClient):
    """Mock LLM provider returning realistic seed pass sequences for testing."""
    pass


class OpenAIClient(LLMClient):
    """OpenAI API provider for structured pass pipeline generation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o", validator: Optional[PassValidator] = None):
        super().__init__(validator=validator)
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model

    def generate_candidates(self, features: CompactCodeFeatures, count: int = 4) -> List[PassSequence]:
        if not self.api_key:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)

        # Fallback to heuristic if API key is missing or offline
        try:
            prompt = USER_PROMPT_TEMPLATE.format(compact_json_features=features.to_compact_json(), count=count)
            url = "https://api.openai.com/v1/chat/completions"
            payload = {
                "model": self.model,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.7,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                content = data["choices"][0]["message"]["content"]
                parsed = LLMPipelineResponseSchema.model_validate_json(content)
                return self.filter_and_validate_candidates(parsed.candidates[:count])
        except Exception:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)


class AnthropicClient(LLMClient):
    """Anthropic API provider for structured pass pipeline generation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022", validator: Optional[PassValidator] = None):
        super().__init__(validator=validator)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.model = model

    def generate_candidates(self, features: CompactCodeFeatures, count: int = 4) -> List[PassSequence]:
        if not self.api_key:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)

        try:
            prompt = USER_PROMPT_TEMPLATE.format(compact_json_features=features.to_compact_json(), count=count)
            url = "https://api.anthropic.com/v1/messages"
            payload = {
                "model": self.model,
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": prompt}],
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["content"][0]["text"]
                parsed = LLMPipelineResponseSchema.model_validate_json(text)
                return self.filter_and_validate_candidates(parsed.candidates[:count])
        except Exception:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)


class GeminiClient(LLMClient):
    """Gemini API provider for structured pass pipeline generation."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-1.5-pro", validator: Optional[PassValidator] = None):
        super().__init__(validator=validator)
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        self.model = model

    def generate_candidates(self, features: CompactCodeFeatures, count: int = 4) -> List[PassSequence]:
        if not self.api_key:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)

        try:
            prompt = f"{SYSTEM_PROMPT}\n\n" + USER_PROMPT_TEMPLATE.format(compact_json_features=features.to_compact_json(), count=count)
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json"},
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                parsed = LLMPipelineResponseSchema.model_validate_json(text)
                return self.filter_and_validate_candidates(parsed.candidates[:count])
        except Exception:
            return HeuristicSeedClient(validator=self.validator).generate_candidates(features, count)


def get_llm_client(
    provider: str = "heuristic",
    use_llm: bool = False,
    api_key: Optional[str] = None,
    validator: Optional[PassValidator] = None,
) -> LLMClient:
    """Factory for selecting LLM / Heuristic provider."""
    if not use_llm or provider in ["heuristic", "none", "no-llm"]:
        return HeuristicSeedClient(validator=validator)

    prov_lower = provider.lower()
    if prov_lower == "openai":
        return OpenAIClient(api_key=api_key, validator=validator)
    elif prov_lower == "anthropic":
        return AnthropicClient(api_key=api_key, validator=validator)
    elif prov_lower == "gemini":
        return GeminiClient(api_key=api_key, validator=validator)
    else:
        return HeuristicSeedClient(validator=validator)
