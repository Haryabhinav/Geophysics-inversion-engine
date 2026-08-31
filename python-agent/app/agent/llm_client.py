"""Provider-agnostic LLM client.

A minimal interface — send a system instruction + conversation history, get
text back — so both the inversion modeler and the interpretation agent can
share one retry/backoff implementation and swap providers (Gemini, Claude,
OpenAI, ...) by adding one adapter class, without touching call sites.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Protocol

logger = logging.getLogger("python-agent.llm_client")

Message = dict[str, Any]

_RETRY_RE = re.compile(r"(?:retry in |retryDelay['\"]?:?\s*['\"]?)([\d.]+)s", re.IGNORECASE)


def _retry_after_seconds(exc: Exception, attempt: int) -> float:
    """Honor the server's suggested retry delay if present, else back off."""
    match = _RETRY_RE.search(str(exc))
    if match:
        return min(65.0, float(match.group(1)) + 2.0)
    return min(60.0, 15.0 * (2**attempt))


class LLMClient(Protocol):
    def generate(self, system: str, history: list[Message], max_tokens: int) -> str: ...


class GeminiClient:
    """Wraps google-genai. Lazy import so non-LLM paths need no key/package."""

    def __init__(self, model: str) -> None:
        from google import genai

        self._model = model
        self._client = genai.Client()

    def generate(self, system: str, history: list[Message], max_tokens: int) -> str:
        from google.genai import types

        return self._generate_with_retry(system, history, max_tokens, types)

    def _generate_with_retry(
        self, system: str, history: list[Message], max_tokens: int, types: Any, max_attempts: int = 5
    ) -> str:
        from google.genai import errors as genai_errors

        config = types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens)
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                resp = self._client.models.generate_content(
                    model=self._model, contents=history, config=config
                )
                return resp.text or ""
            except genai_errors.ClientError as exc:
                if getattr(exc, "code", None) == 429 and attempt < max_attempts - 1:
                    wait = _retry_after_seconds(exc, attempt)
                    logger.warning(
                        "Gemini rate-limited (429); sleeping %.0fs then retrying (attempt %d/%d)",
                        wait, attempt + 1, max_attempts,
                    )
                    time.sleep(wait)
                    last_exc = exc
                    continue
                raise
        assert last_exc is not None
        raise last_exc


def build_llm_client(provider: str, model: str) -> LLMClient:
    """Select a client by provider name. Only 'gemini' is wired today; adding
    Claude/OpenAI means adding one class above and one branch here — call
    sites (GeminiModeler, the interpretation agent) never change."""
    provider = provider.lower()
    if provider == "gemini":
        return GeminiClient(model)
    raise ValueError(f"Unknown LLM provider: {provider!r}")
