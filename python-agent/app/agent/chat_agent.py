"""The Site Chat Agent — natural-language Q&A over one site's own run and
interpretation history.

Scoped per-site by design: a site's run history (a handful to a few dozen
inversion results, each a small JSON model) comfortably fits in a single LLM
context window, so this stays a direct "stuff the history into the prompt"
agent rather than needing a vector store or retrieval pipeline — the same
reasoning app/agent/joint_interpreter.py already relies on for synthesizing
across methods at one site.

No offline fallback, by the same deliberate choice as
app/agent/data_cleaner.py: a rule-based test double can restate numbers but
cannot answer an open-ended question, and a plausible-sounding fabricated
answer is a worse failure mode than the feature being unavailable. So
build_chat_agent() requires a Gemini key and raises ChatUnavailableError
(surfaced as a clear 503, not a crash) when one isn't configured.
"""

from __future__ import annotations

import json
import logging
import os
import re

from ..schemas import MethodResultInput
from ..schemas_chat import ChatResponse, ChatTurn
from .llm_client import LLMClient, build_llm_client

logger = logging.getLogger("python-agent.chat_agent")

SYSTEM_PROMPT = """\
You are a geophysics assistant answering questions about ONE survey site's \
own run and interpretation history. You are given every stored run for this \
site (method, status, final model, misfit, and — if available — that run's \
own interpretation), a free-text site note, and the conversation so far.

Your job:
1. Answer ONLY from the provided run history, site note, and conversation —
   never invent a run, a number, or a finding that isn't in the data given
   to you.
2. If the data doesn't contain enough to answer confidently, say so plainly
   rather than guessing.
3. When your answer draws on a specific run, cite its job id inline (e.g.
   "the TDEM run (job abc123) converged at L2=0.04").
4. Keep answers concise and in plain language a field geophysicist would
   find useful — a few sentences unless the question asks for more detail.

Respond with ONLY a single JSON object (no markdown fences, no prose outside
it) with exactly these keys:
{"answer": str, "citedRuns": [str, ...], "confidence": "high"|"medium"|"low"}

"citedRuns" is the list of job ids your answer actually relies on (empty if
none). "confidence" reflects how well-supported the answer is by the given
data, not how fluent the answer sounds.
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class ChatUnavailableError(RuntimeError):
    """Raised when the Site Chat Agent has no LLM client to work with."""


def _extract_json(text: str) -> dict:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in chat agent reply: {text!r}")
    return json.loads(match.group(0))


def _run_history_block(run_history: list[MethodResultInput]) -> str:
    if not run_history:
        return "(no stored runs for this site)"
    lines = []
    for r in run_history:
        lines.append(f"Method: {r.dataType} (job {r.jobId}, status={r.status})")
        lines.append(f"  Final model: {json.dumps(r.finalModel)}")
        if r.l2NormError is not None:
            lines.append(f"  Misfit (relative L2): {r.l2NormError}")
        if r.interpretation is not None:
            lines.append(
                f"  Interpretation: summary={r.interpretation.summary!r}, "
                f"confidence={r.interpretation.confidence}, "
                f"flagged_anomaly={r.interpretation.flagged_anomaly}"
            )
    return "\n".join(lines)


def _user_prompt(
    question: str,
    history: list[ChatTurn],
    run_history: list[MethodResultInput],
    site_note: str | None,
) -> str:
    lines = [f"Site note: {site_note or '(none provided)'}", "", "Run history:", _run_history_block(run_history)]
    if history:
        lines.append("")
        lines.append("Conversation so far:")
        for turn in history:
            lines.append(f"  {turn.role}: {turn.content}")
    lines.append("")
    lines.append(f"Question: {question}")
    lines.append("")
    lines.append("Respond with the JSON object described in your instructions.")
    return "\n".join(lines)


class SiteChatAgent:
    def __init__(self, client: LLMClient | None = None, model: str | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None.
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ChatUnavailableError(
                    "Site chat requires GEMINI_API_KEY to be configured on the server."
                )
            from ..config import settings

            self._client = build_llm_client("gemini", model or settings.gemini_model)

    def answer(
        self,
        site_id: str,
        question: str,
        history: list[ChatTurn],
        run_history: list[MethodResultInput],
        site_note: str | None,
    ) -> ChatResponse:
        from ..config import settings

        prompt = _user_prompt(question, history, run_history, site_note)
        chat_history = [{"role": "user", "parts": [{"text": prompt}]}]
        text = self._client.generate(SYSTEM_PROMPT, chat_history, settings.gemini_max_tokens)
        parsed = _extract_json(text)
        return ChatResponse(
            answer=str(parsed["answer"]),
            citedRuns=[str(j) for j in parsed.get("citedRuns", [])],
            confidence=parsed["confidence"],
        )


def build_chat_agent() -> SiteChatAgent:
    """No mode toggle, unlike build_interpreter/build_joint_interpreter —
    this stage is LLM-only by deliberate choice (see module docstring).
    Raises ChatUnavailableError (not a generic exception) so main.py can
    translate it into a clear 503 rather than a 500."""
    return SiteChatAgent()
