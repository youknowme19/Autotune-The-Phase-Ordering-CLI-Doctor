"""
LLM Client abstractions, JSON schema validation gate, and Mock implementation.
"""

from abc import ABC, abstractmethod
import json
from typing import List, Optional
from autotune.analysis.features import CompactCodeFeatures
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from autotune.llm.schema import LLMPassPipelineCandidate, LLMPipelineResponseSchema


class LLMClient(ABC):
    """Abstract interface for LLM pass sequence generators with structured JSON validation gate."""

    def __init__(self, validator: Optional[PassValidator] = None):
        self.validator = validator or PassValidator()

    def filter_and_validate_candidates(self, raw_json_or_candidates: List[LLMPassPipelineCandidate]) -> List[PassSequence]:
        """Pass Validation Gate: Intercept LLM proposals and filter out hallucinated passes before GA seeding."""
        validated_sequences: List[PassSequence] = []

        for cand in raw_json_or_candidates:
            raw_seq = PassSequence(passes=cand.passes)
            # Filter out any pass name not recognized by local PassValidator
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


class MockLLMClient(LLMClient):
    """Mock LLM provider returning realistic seed pass sequences without requiring API keys."""

    def generate_candidates(
        self, features: CompactCodeFeatures, count: int = 4
    ) -> List[PassSequence]:
        raw_candidates = [
            LLMPassPipelineCandidate(
                name="Loop Canonicalization & Unrolling",
                rationale="Unrolls innermost loops and canonicalizes induction variables.",
                passes=["mem2reg", "loop-rotate", "licm", "instcombine", "loop-unroll"],
            ),
            LLMPassPipelineCandidate(
                name="Vectorization & SROA",
                rationale="Splits scalar aggregates and vectorizes memory access loops.",
                passes=["mem2reg", "sroa", "early-cse", "gvn", "loop-vectorize", "slp-vectorize", "hallucinated-pass-999"],
            ),
            LLMPassPipelineCandidate(
                name="Floating Point & Arithmetic Reassociation",
                rationale="Reassociates arithmetic operations to maximize vector SIMD utilization.",
                passes=["mem2reg", "reassociate", "instcombine", "loop-simplify", "indvars", "loop-unroll"],
            ),
            LLMPassPipelineCandidate(
                name="Dead Code & Memory Opt",
                rationale="Eliminates dead stores and optimizes memcpy operations.",
                passes=["mem2reg", "simplifycfg", "sccp", "dce", "memcpyopt", "gvn"],
            ),
        ]

        # Filter candidates through Pass Validation Gate (drops 'hallucinated-pass-999')
        return self.filter_and_validate_candidates(raw_candidates[:count])


def get_llm_client(
    provider: str = "mock",
    model: str = "mock",
    api_key: Optional[str] = None,
    validator: Optional[PassValidator] = None,
) -> LLMClient:
    """Factory for selecting LLM provider."""
    return MockLLMClient(validator=validator)
