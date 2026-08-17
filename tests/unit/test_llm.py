"""
Unit tests for LLVM structured schema parsing, MockLLMClient, and hallucinated pass filtering.
"""

import pytest
from autotune.analysis.features import FeatureExtractor
from autotune.llm.client import MockLLMClient, get_llm_client
from autotune.llm.schema import LLMPassPipelineCandidate, LLMPipelineResponseSchema
from autotune.llvm.passes import PassSequence, PassValidator


def test_llm_schema_models():
    cand = LLMPassPipelineCandidate(
        name="Test Pipeline",
        rationale="Unrolls innermost loop",
        passes=["mem2reg", "loop-unroll"],
    )
    schema = LLMPipelineResponseSchema(candidates=[cand])

    assert len(schema.candidates) == 1
    assert schema.candidates[0].name == "Test Pipeline"
    assert schema.candidates[0].passes == ["mem2reg", "loop-unroll"]


def test_mock_llm_client_generation():
    extractor = FeatureExtractor()
    features = extractor.extract_from_file("examples/simple_loop/kernel.c")

    client = MockLLMClient()
    candidates = client.generate_candidates(features, count=4)

    assert len(candidates) > 0
    for seq in candidates:
        assert isinstance(seq, PassSequence)
        assert len(seq.passes) > 0


def test_pass_validation_gate_rejects_hallucinated_passes():
    validator = PassValidator()
    client = MockLLMClient(validator=validator)

    hallucinated_candidate = LLMPassPipelineCandidate(
        name="Hallucinated Proposal",
        rationale="Uses fake optimization passes",
        passes=["mem2reg", "fake-pass-alpha", "gvn", "super-magic-pass-999"],
    )

    clean_sequences = client.filter_and_validate_candidates([hallucinated_candidate])

    assert len(clean_sequences) == 1
    # Only valid passes ('mem2reg', 'gvn') remain; fake passes are dropped
    assert clean_sequences[0].passes == ["mem2reg", "gvn"]
    assert "fake-pass-alpha" not in clean_sequences[0].passes
    assert "super-magic-pass-999" not in clean_sequences[0].passes
