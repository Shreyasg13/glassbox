"""Resolves an agent's configured `provider` string to a live adapter.

Swapping a per-agent provider (Ollama -> Gemini, say) is purely a config
change on the `AgentConfig` row -- this factory is the only place that
maps that string to a concrete class.
"""
from __future__ import annotations

from functools import lru_cache

from ..models import Provider
from .base import LLMProvider
from .claude import ClaudeProvider
from .gemini import GeminiProvider
from .ollama import OllamaProvider
from .vllm import VLLMProvider

_REGISTRY = {
    "ollama": OllamaProvider,
    "vllm": VLLMProvider,
    "gemini": GeminiProvider,
    "claude": ClaudeProvider,
}


@lru_cache(maxsize=None)
def get_provider(name: Provider) -> LLMProvider:
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"Unknown provider: {name}")
    return cls()
