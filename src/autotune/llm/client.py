"""
LLM Client abstractions and Mock implementation.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from autotune.analysis.features import CompactCodeFeatures
from autotune.llvm.passes import PassSequence, PassValidator
from autotune.llm.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE
from autotune.llm.schema import LLMPassPipelineCandidate, LLMPipelineResponseSchema


class LLMClient(ABC):
    """Abstract interface for LLM pass sequence generators."""

    def __init__(self, validator: Optional[PassValidator] = None):
        self.validator = validator or PassValidator()

    @abstractmethod
    def generate_candidates(
        self, features: CompactCodeFeatures, count: int = 4
    ) -> List[PassSequence]:
        """Generate validated LLVM pass sequences based on code features."""
        pass


class MockLLMClient(LLMClient):
    """Mock LLM provider returning realistic seed pass sequences without requiring API keys."""

    def generate_candidates(
        self, features: CompactCodeFeatures, count: int = 4
    ) -> List[PassSequence]:
        # Pre-curated candidates tuned for different workload features
        seeds = [
            ["mem2reg", "loop-rotate", "licm", "instcombine", "loop-unroll"],
            ["mem2reg", "sroa", "early-cse", "gvn", "loop-vectorize", "slp-vectorize"],
            ["mem2reg", "reassociate", "instcombine", "loop-simplify", "indvars", "loop-unroll"],
            ["mem2reg", "simplifycfg", "sccp", "dce", "memcpyopt", "gvn"],
            ["mem2reg", "inline", "sroa", "gvn", "licm", "loop-vectorize"],
        ]

        results: List[PassSequence] = []
        for raw in seeds[:count]:
            seq = PassSequence(passes=raw)
            # Filter out any pass not recognized by validator
            validated = self.validator.filter_sequence(seq)
            if validated.passes:
                results.append(validated)

        return results


def get_llm_client(
    provider: str = "mock",
    model: str = "mock",
    api_key: Optional[str] = None,
    validator: Optional[PassValidator] = None,
) -> LLMClient:
    """Factory for selecting LLM provider."""
    # For now, default to mock client to keep offline and testable
    return MockLLMClient(validator=validator)
