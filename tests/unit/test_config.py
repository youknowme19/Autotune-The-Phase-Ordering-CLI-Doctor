"""
Unit tests for configuration system, CredentialStore keyring resolution, and provider selection.
"""

import os
from unittest.mock import patch
import pytest
from autotune.config import AutotuneConfig, CredentialStore, get_default_config
from autotune.llm import HeuristicSeedClient, OpenAIClient, get_llm_client


def test_default_config():
    cfg = get_default_config()
    assert cfg.population_size > 0
    assert cfg.generations > 0
    assert cfg.opt_level == "-O3"


def test_env_var_wins_over_keyring(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env_secret_key_123")
    with patch("keyring.get_password", return_value="keyring_secret_456"):
        key = CredentialStore.get_api_key("openai")
        assert key == "env_secret_key_123"


def test_keyring_works_when_env_absent(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUNE_LLM_API_KEY", raising=False)
    with patch("keyring.get_password", return_value="keyring_secret_456"):
        key = CredentialStore.get_api_key("openai")
        assert key == "keyring_secret_456"


def test_no_credential_returns_none(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AUTOTUNE_LLM_API_KEY", raising=False)
    with patch("keyring.get_password", return_value=None):
        key = CredentialStore.get_api_key("openai")
        assert key is None


def test_get_llm_client_routing(monkeypatch):
    # 1. Offline mode ignores keys
    client_off = get_llm_client(provider="openai", use_llm=False, api_key="secret")
    assert isinstance(client_off, HeuristicSeedClient)

    # 2. Online mode with provider openai returns OpenAIClient
    client_on = get_llm_client(provider="openai", use_llm=True, api_key="secret")
    assert isinstance(client_on, OpenAIClient)

    # 3. Provider heuristic returns HeuristicSeedClient
    client_heur = get_llm_client(provider="heuristic", use_llm=True, api_key="secret")
    assert isinstance(client_heur, HeuristicSeedClient)


def test_set_api_key_keyring():
    with patch("keyring.set_password", return_value=None) as mock_set:
        ok = CredentialStore.set_api_key("openai", "my_secret_key")
        assert ok
        mock_set.assert_called_once_with("autotune", "openai", "my_secret_key")
