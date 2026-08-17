"""
Configuration module for Autotune using Pydantic.
"""

from typing import Optional
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()


class AutotuneConfig(BaseModel):
    """Global configuration settings for Autotune."""

    clang_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_CLANG_PATH")
    )
    opt_path: Optional[str] = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_OPT_PATH")
    )
    opt_level: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_OPT_LEVEL", "-O3")
    )

    # Search parameters
    population_size: int = Field(
        default_factory=lambda: int(os.getenv("AUTOTUNE_POPULATION_SIZE", "20"))
    )
    generations: int = Field(
        default_factory=lambda: int(os.getenv("AUTOTUNE_GENERATIONS", "40"))
    )
    timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("AUTOTUNE_TIMEOUT", "5.0"))
    )
    benchmark_repetitions: int = Field(
        default_factory=lambda: int(
            os.getenv("AUTOTUNE_BENCHMARK_REPETITIONS", "10")
        )
    )
    noise_threshold: float = Field(
        default_factory=lambda: float(os.getenv("AUTOTUNE_NOISE_THRESHOLD", "0.05"))
    )
    random_seed: Optional[int] = Field(
        default_factory=lambda: (
            int(os.getenv("AUTOTUNE_RANDOM_SEED"))
            if os.getenv("AUTOTUNE_RANDOM_SEED")
            else None
        )
    )

    # LLM Settings
    llm_provider: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_LLM_PROVIDER", "mock")
    )
    llm_model: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_LLM_MODEL", "mock-model")
    )
    llm_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_LLM_API_KEY")
    )

    # Measurement backend: auto, macos_timing, linux_perf
    measurement_backend: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_MEASUREMENT_BACKEND", "auto")
    )


def get_default_config() -> AutotuneConfig:
    return AutotuneConfig()
