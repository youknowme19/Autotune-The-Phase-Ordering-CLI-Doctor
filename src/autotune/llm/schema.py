"""
LLM Response schema for structured pass pipeline generation.
"""

from typing import List
from pydantic import BaseModel, Field


class LLMPassPipelineCandidate(BaseModel):
    name: str = Field(description="Name or rationale for candidate pipeline")
    passes: List[str] = Field(
        description="Ordered list of valid LLVM pass names e.g. ['mem2reg', 'gvn', 'instcombine']"
    )


class LLMPipelineResponseSchema(BaseModel):
    candidates: List[LLMPassPipelineCandidate]
