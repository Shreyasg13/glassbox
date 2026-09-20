"""OpenAI-compatible chat providers -- one class, many services.

Almost every LLM host worth using as a free/cheap failover speaks the same
`POST {base}/chat/completions` protocol, so each is just a CompatSpec (base
URL, which env var holds the key, default models) instead of a new adapter:

  openrouter  free aggregator (the "omniroute"-style option): its `:free`
              models and the `openrouter/free` meta-model that auto-routes to
              whichever free model is up. Free models churn constantly, so the
              currently-free list is DISCOVERED from its public catalogue, not
              hardcoded.
  groq        fast free tier (Llama, Qwen, DeepSeek-distill ...). NOT xAI Grok.
  cerebras    generous free tier (Llama, Qwen).
  github      GitHub Models (free with a GitHub account, rate-limited).
  qwen        Alibaba DashScope international endpoint (new-account free quota).
  deepseek    DeepSeek's own API (paid, very cheap; no free tier).
  xai         xAI Grok (paid).
  gateway     ANY OpenAI-compatible gateway you run or subscribe to: OmniRoute,
              LiteLLM proxy, vLLM, a corporate router... set LLM_GATEWAY_BASE_URL.

Secrets: keys travel only in the Authorization header. Error messages are built
from the provider name and HTTP status ONLY -- never from the request URL,
headers or response body -- so nothing sensitive can reach llm_calls.error, job
logs or the admin UI. Model names defaults are best-effort and change over time:
override with <NAME>_MODELS (comma-separated); each provider's own /models list
is used (fail-open) to drop names the key can't call, and a 404 is remembered.
"""
from __future__ import annotations

import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx

from . import gemini_quota
from .base import BaseProvider, ModelUnavailableError, NotConfiguredError, OnToken, RateLimitedError

_CATALOGUE_TTL_S = 6 * 60 * 60.0
_CATALOGUE_FAIL_TTL_S = 5 * 60.0
_RETRYABLE = {429, 503}
_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
_NOT_TEXT_CHAT = re.compile(r"(safety|guard|embed|image|audio|tts|lyria|-vl\b|vision)", re.I)
_PREFERRED_FAMILY = re.compile(r"(qwen|deepseek|llama|gemma|nemotron|glm|mistral)", re.I)


@dataclass(frozen=True)
class CompatSpec:
    name: str
    label: str
    base_url: str
    key_env: Tuple[str, ...]
    models: Tuple[str, ...]
    tier: str  # free | freemium | paid | custom
    signup: str = ""
    key_required: bool = True
    discover_free: bool = False
    headers: Tuple[Tuple[str, str], ...] = ()

    @property
    def env_prefix(self) -> str:
        return "LLM_GATEWAY" if self.name == "gateway" else self.name.upper()


SPECS: Dict[str, CompatSpec] = {
    s.name: s
    for s in (
        CompatSpec("openrouter", "OpenRouter (free models)", "https://openrouter.ai/api/v1", ("OPENROUTER_API_KEY",),
                   ("openrouter/free",), "free", "https://openrouter.ai/keys", discover_free=True, headers=(("X-Title", "GlassBox"),)),
        CompatSpec("groq", "Groq", "https://api.groq.com/openai/v1", ("GROQ_API_KEY",),
                   ("llama-3.3-70b-versatile", "llama-3.1-8b-instant"), "freemium", "https://console.groq.com/keys"),
        CompatSpec("cerebras", "Cerebras", "https://api.cerebras.ai/v1", ("CEREBRAS_API_KEY",),
                   ("llama-3.3-70b", "qwen-3-32b", "llama3.1-8b"), "freemium", "https://cloud.cerebras.ai"),
        CompatSpec("github", "GitHub Models", "https://models.github.ai/inference", ("GITHUB_MODELS_TOKEN", "GITHUB_TOKEN"),
                   ("openai/gpt-4o-mini", "meta/llama-3.3-70b-instruct"), "freemium", "https://github.com/marketplace/models"),
        CompatSpec("qwen", "Qwen (Alibaba DashScope)", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1", ("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
                   ("qwen-plus", "qwen-flash"), "freemium", "https://www.alibabacloud.com/help/en/model-studio/get-api-key"),
        CompatSpec("deepseek", "DeepSeek", "https://api.deepseek.com", ("DEEPSEEK_API_KEY",),
                   ("deepseek-chat",), "paid", "https://platform.deepseek.com/api_keys"),
        CompatSpec("xai", "xAI Grok", "https://api.x.ai/v1", ("XAI_API_KEY",),
                   ("grok-3-mini",), "paid", "https://console.x.ai"),
        CompatSpec("gateway", "Custom gateway (OmniRoute / LiteLLM / ...)", "", ("LLM_GATEWAY_API_KEY",),
                   (), "custom", key_required=False),
    )
}


def _split(value: Optional[str]) -> List[str]:
    return [p.strip() for p in (value or "").split(",") if p.strip()]


class OpenAICompatProvider(BaseProvider):
    def __init__(self, spec: CompatSpec, api_key: Optional[str] = None, base_url: Optional[str] = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.spec = spec
        self.name = spec.name  # type: ignore[assignment]
        self._api_key_override = api_key
        self._base_url_override = base_url
        self._catalogue: Optional[Tuple[float, Optional[List[Dict[str, Any]]]]] = None  # (fetched_at, models-or-None)

    # ------------------------------------------------------------ config --

    @property
    def api_key(self) -> Optional[str]:
        if self._api_key_override is not None:
            return self._api_key_override or None
        for env in self.spec.key_env:
            v = os.environ.get(env, "").strip()
            if v:
                return v
        return None

    @property
    def base_url(self) -> str:
        if self._base_url_override is not None:
            return self._base_url_override.rstrip("/")
        return (os.environ.get(f"{self.spec.env_prefix}_BASE_URL", "").strip() or self.spec.base_url).rstrip("/")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url) and (bool(self.api_key) or not self.spec.key_required)

    def _missing_what(self) -> str:
        if not self.base_url:
            return f"{self.spec.env_prefix}_BASE_URL not set"
        return f"{self.spec.key_env[0]} not set"

    def _headers(self) -> Dict[str, str]:
        h = {"Content-Type": "application/json", **dict(self.spec.headers)}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        domain = os.environ.get("APP_DOMAIN")
        if self.spec.name == "openrouter" and domain:
            h["HTTP-Referer"] = f"https://{domain}"
        return h

    # -------------------------------------------------------- completion --

    async def _do_complete(
        self,
        prompt: str,
        *,
        model: str,
        temperature: float,
        top_p: float,
        max_tokens: int,
        system: Optional[str],
        on_token: Optional[OnToken],
        retry: bool = True,
    ) -> str:
        if not self.is_configured:
            raise NotConfiguredError(self._missing_what())
        messages: List[Dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {"model": model, "messages": messages, "temperature": temperature, "top_p": top_p, "max_tokens": max_tokens, "stream": False}
        attempts = 3 if retry else 1
        async with httpx.AsyncClient(timeout=None) as client:
            for attempt in range(1, attempts + 1):
                try:
                    resp = await client.post(f"{self.base_url}/chat/completions", headers=self._headers(), json=payload)
                except httpx.HTTPError as exc:
                    raise RuntimeError(f"{self.name} request failed: {exc.__class__.__name__}") from None
                if resp.status_code == 200:
                    text = self._parse(resp)
                    if on_token:
                        await on_token(text)
                    return text
                if resp.status_code in _RETRYABLE and attempt < attempts:
                    await asyncio.sleep(min(self._retry_after(resp) or 2.0 * attempt, 8.0))
                    continue
                raise self._error_for(resp, model)
        raise RuntimeError(f"{self.name} request failed")  # unreachable; keeps every path an exit

    @staticmethod
    def _retry_after(resp: httpx.Response) -> Optional[float]:
        v = resp.headers.get("retry-after", "")
        return float(v) if v.replace(".", "", 1).isdigit() else None

    def _error_for(self, resp: httpx.Response, model: str) -> Exception:
        status = resp.status_code
        body = (resp.text or "").lower()
        if status == 401:
            return NotConfiguredError(f"{self.name}: API key rejected (HTTP 401)")
        if status == 402:
            return RateLimitedError(f"{self.name}: out of credits (HTTP 402)", daily=True)
        if status == 404:
            gemini_quota.mark_unavailable(f"{self.name}:{model}")
            return ModelUnavailableError(f"{self.name}: model not found (HTTP 404)")
        if status == 429:
            daily = any(k in body for k in ("per day", "perday", "daily", "credit", "quota"))
            return RateLimitedError(f"{self.name} API error: HTTP 429", retry_after_s=self._retry_after(resp), daily=daily)
        return RuntimeError(f"{self.name} API error: HTTP {status}")

    def _parse(self, resp: httpx.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            raise RuntimeError(f"{self.name} returned invalid JSON") from None
        err = data.get("error") if isinstance(data, dict) else None
        if err:  # some gateways report failures inside a 200 body
            code = err.get("code") if isinstance(err, dict) else None
            if str(code) == "429":
                raise RateLimitedError(f"{self.name} API error: HTTP 429")
            raise RuntimeError(f"{self.name} API error: {code or 'error'}")
        try:
            content = data["choices"][0]["message"].get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise RuntimeError(f"{self.name} returned an unexpected response") from None
        if isinstance(content, list):  # content-parts form
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        text = _THINK_RE.sub("", content or "").strip()
        if not text:
            # Reasoning models can spend the whole budget "thinking" and return
            # nothing visible. That is a failure to fail OVER on, not an answer.
            raise RuntimeError(f"{self.name} returned an empty response")
        return text

    # --------------------------------------------------------- discovery --

    async def _fetch_catalogue(self) -> Optional[List[Dict[str, Any]]]:
        """The provider's own model list (cached). None = unknown, never "none"."""
        if not self.is_configured and self.spec.key_required and not self.spec.discover_free:
            return None
        now = time.monotonic()
        if self._catalogue is not None:
            fetched, value = self._catalogue
            if now - fetched < (_CATALOGUE_TTL_S if value is not None else _CATALOGUE_FAIL_TTL_S):
                return value
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                resp = await client.get(f"{self.base_url}/models", headers=self._headers())
                resp.raise_for_status()
                models = resp.json().get("data", [])
                value: Optional[List[Dict[str, Any]]] = [m for m in models if isinstance(m, dict) and m.get("id")] or None
        except (httpx.HTTPError, ValueError, AttributeError, TypeError):
            value = None
        self._catalogue = (now, value)
        return value

    async def available_models(self) -> Optional[Set[str]]:
        cat = await self._fetch_catalogue()
        return {m["id"] for m in cat} if cat else None

    async def free_models(self) -> List[str]:
        """Currently-free text-chat models (OpenRouter's public catalogue lists
        prices), best-looking first. Empty when not applicable / unknown."""
        cat = await self._fetch_catalogue()
        out = []
        for m in cat or []:
            p = m.get("pricing") or {}
            try:
                free = float(p.get("prompt", 1)) == 0 and float(p.get("completion", 1)) == 0
            except (TypeError, ValueError):
                free = False
            modality = str((m.get("architecture") or {}).get("modality", "text->text"))
            mid = str(m["id"])
            if free and modality.startswith("text") and modality.endswith("->text") and not _NOT_TEXT_CHAT.search(mid) and mid != "openrouter/free":
                out.append((0 if _PREFERRED_FAMILY.search(mid) else 1, -int(m.get("context_length") or 0), mid))
        return [mid for _a, _b, mid in sorted(out)]

    async def candidate_models(self) -> List[str]:
        """Models to try, in order, when this provider is used as a failover
        target: env override, else the spec's defaults (+ discovered free ones
        for OpenRouter), narrowed to what the key can call (fail-open)."""
        env = _split(os.environ.get(f"{self.spec.env_prefix}_MODELS"))
        base = env or list(self.spec.models)
        if self.spec.discover_free and not env:
            base += [m for m in (await self.free_models())[:5] if m not in base]
        offered = await self.available_models()
        if offered:
            if not base:  # a custom gateway with no configured models: use what it offers
                base = sorted(offered)[:4]
            else:
                narrowed = [m for m in base if m in offered]
                base = narrowed or base
        usable = [m for m in base if not gemini_quota.is_unavailable(f"{self.name}:{m}")]
        return usable or base

    async def _do_health_check(self) -> str:
        if not self.is_configured:
            raise NotConfiguredError(self._missing_what())
        cat = await self._fetch_catalogue()
        if cat is None:
            raise RuntimeError(f"{self.name} model list unavailable")
        if self.spec.discover_free:
            return f"{len(await self.free_models())} free model(s) available"
        return f"{len(cat)} model(s) available"
