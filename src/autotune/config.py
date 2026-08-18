"""
Configuration module for Autotune with secure keyring credential management.
"""

from typing import Optional
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

KEYRING_SERVICE_NAME = "autotune"


class CredentialStore:
    """Manages secure resolution and storage of API credentials via environment and OS keyring."""

    @staticmethod
    def get_api_key(provider: str = "openai") -> Optional[str]:
        """
        Resolution Order:
        1. Environment variable (e.g. OPENAI_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY, AUTOTUNE_LLM_API_KEY)
        2. OS Keyring (service="autotune", username=provider)
        """
        prov_upper = provider.upper()
        env_vars = [
            f"{prov_upper}_API_KEY",
            "AUTOTUNE_LLM_API_KEY",
        ]
        if prov_upper == "GEMINI":
            env_vars.append("GOOGLE_API_KEY")

        for env_var in env_vars:
            val = os.getenv(env_var)
            if val and val.strip():
                return val.strip()

        # Check OS keyring
        try:
            import keyring
            key = keyring.get_password(KEYRING_SERVICE_NAME, provider.lower())
            if key and key.strip():
                return key.strip()
        except Exception:
            pass

        return None

    @staticmethod
    def set_api_key(provider: str, secret_key: str) -> bool:
        """Securely store API key in OS keyring."""
        try:
            import keyring
            keyring.set_password(KEYRING_SERVICE_NAME, provider.lower(), secret_key.strip())
            return True
        except Exception:
            return False


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
        default_factory=lambda: os.getenv("AUTOTUNE_LLM_PROVIDER", "openai")
    )
    llm_model: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_LLM_MODEL", "gpt-4o")
    )

    # Measurement backend: auto, macos_timing, linux_perf
    measurement_backend: str = Field(
        default_factory=lambda: os.getenv("AUTOTUNE_MEASUREMENT_BACKEND", "auto")
    )

    def get_llm_api_key(self, provider: Optional[str] = None) -> Optional[str]:
        return CredentialStore.get_api_key(provider or self.llm_provider)


def get_default_config() -> AutotuneConfig:
    return AutotuneConfig()
