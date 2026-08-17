"""
LLM Response schema for structured pass pipeline generation.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class LLMPassPipelineCandidate(BaseModel):
    name: str = Field(description="Name or title for candidate pipeline")
    rationale: str = Field(description="1-line rationale explaining why this pass sequence fits the code features")
    passes: List[str] = Field(
        description="Ordered list of valid LLVM pass names e.g. ['mem2reg', 'gvn', 'instcombine']"
    )


class LLMPipelineResponseSchema(BaseModel):
    candidates: List[LLMPassPipelineCandidate]
