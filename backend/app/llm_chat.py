"""A LangChain chat model that speaks through GlassBox's own failover router.

LangChain's building blocks (prompt templates, output parsers, `prompt | model | parser`
chains, callbacks) want a `BaseChatModel`. Our providers are reached through
`llm_router.complete_routed`, which already knows the things a generic wrapper would not:
free-tier quota cooldowns, per-provider model chains, failover to OpenRouter/Groq/... and
the LLM-call ledger the admin observability page reads. So instead of re-implementing any
of that on top of a stock LangChain integration, this class is a thin adapter: LangChain
composes, the router delivers.

Async only -- every caller in this app is async, and a sync path would need its own event
loop. The winning provider and model are returned in `response_metadata` so a chain can
record which provider actually answered.
"""
from __future__ import annotations

from typing import Any, List, Optional

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from . import llm_router


def _text(message: BaseMessage) -> str:
    c = message.content
    return c if isinstance(c, str) else "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in c)


class RoutedChatModel(BaseChatModel):
    provider: str
    model_id: str
    agent_id: Optional[str] = None
    temperature: float = 0.3
    top_p: float = 1.0
    max_tokens: int = 700
    fallback_models: List[str] = Field(default_factory=list)
    allow_failover: bool = True

    @property
    def _llm_type(self) -> str:
        return "glassbox-routed"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        raise NotImplementedError("RoutedChatModel is async-only: use ainvoke / astream")

    async def _agenerate(
        self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Optional[AsyncCallbackManagerForLLMRun] = None, **kwargs: Any
    ) -> ChatResult:
        system = "\n\n".join(_text(m) for m in messages if isinstance(m, SystemMessage)) or None
        prompt = "\n\n".join(_text(m) for m in messages if not isinstance(m, SystemMessage))
        routed = await llm_router.complete_routed(
            self.provider,
            self.model_id,
            prompt,
            agent_id=self.agent_id,
            system=system,
            temperature=self.temperature,
            top_p=self.top_p,
            max_tokens=self.max_tokens,
            fallback_models=self.fallback_models,
            allow_failover=self.allow_failover,
        )
        message = AIMessage(content=routed.text, response_metadata={"provider": routed.provider, "model": routed.model, "tried": routed.tried})
        return ChatResult(generations=[ChatGeneration(message=message)])
