"""
Unit tests for configuration system.
"""

from autotune.config import AutotuneConfig, get_default_config


def test_default_config():
    cfg = get_default_config()
    assert cfg.population_size > 0
    assert cfg.generations > 0
    assert cfg.opt_level == "-O3"
    assert cfg.llm_provider in ["mock", "openai", "anthropic", "custom"]
