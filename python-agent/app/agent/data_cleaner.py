"""The Data Cleaning Agent.

Runs *before* ingestion, on genuinely raw, unstructured field data — a CSV
export with no header, a mix of units, a garbled extra column, drift, or
spikes. This is deliberately upstream of everything else in the pipeline:
`node-ingestion`'s `sanitize.ts` already handles the mechanical case (drop
`NaN`/`null`/`±Inf`/unpaired samples) for data that's already shaped as
`{time, amplitude}` — this agent handles the judgment call of producing that
shape in the first place from something messier, plus outlier/drift/unit
issues a purely mechanical pass can't recognize.

No offline fallback, by deliberate choice (unlike every other LLM stage in
this platform): identifying which column is time vs. amplitude in an
unlabeled file, or telling a real spike from a real geological anomaly, is
exactly the kind of judgment call a rule-based test double can't credibly
fake — a wrong "offline" guess here would silently corrupt the data flowing
into every downstream stage. So `build_data_cleaner()` requires a Gemini key
and raises `CleaningUnavailableError` (surfaced as a clear 4xx, not a crash)
when one isn't configured, rather than pretending to clean data it can't.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from .llm_client import LLMClient, build_llm_client
from .methods import METHOD_REGISTRY

logger = logging.getLogger("python-agent.data_cleaner")

# Bounds how much raw text reaches the prompt — large uploads are truncated
# (with the model told so) rather than blowing the token budget or cost.
_MAX_PROMPT_CHARS = 12_000

SYSTEM_PROMPT = """\
You are a data-cleaning assistant for a geophysical inversion pipeline. You \
are given RAW, possibly messy field data as plain text — it may or may not \
have a header row, may have extra junk columns, inconsistent units, missing \
values, or outlier spikes that aren't physically plausible for this method.

You are also told which geophysical method this data is for, and the \
expected x-axis and y-axis quantities.

Your job:
1. Identify which column (or comma/tab/space-separated field) is the x-axis \
(time/offset/distance) and which is the y-axis (amplitude/response) value. \
Ignore columns that are clearly neither (row indices, comments, station \
names).
2. Normalize units to the expected quantity if you can tell they differ \
(e.g. milliseconds mixed with seconds).
3. Remove samples that are physically implausible outliers/spikes for this \
kind of measurement, or that are clearly corrupted (garbage text in a \
numeric field, duplicated timestamps). Do NOT remove real geological \
signal just because it looks unusual — only remove what a field \
geophysicist would call bad data.
4. If the y-axis values show a slow linear/constant baseline drift or \
offset unrelated to the expected signal shape, correct it.
5. Keep every point you're not confident is bad — when in doubt, keep it.

Respond with ONLY a single JSON object (no markdown fences, no prose \
outside it) with exactly these keys:
{"timeSteps": [numbers], "amplitudes": [numbers], "droppedCount": int, \
"summary": str, "actions": [str, ...]}

"summary" is one sentence a geophysicist would find useful. "actions" is a \
short list of concrete things you did (e.g. "removed 3 outlier spikes at \
indices 12, 45, 46", "detected time column was in ms, converted to s", \
"corrected a linear baseline drift of ~0.02/sample"). If you did nothing, \
say so plainly rather than inventing an action.
"""

_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


class CleaningUnavailableError(RuntimeError):
    """Raised when the Cleaning Agent has no LLM client to work with."""


def _extract_json(text: str) -> dict[str, Any]:
    match = _JSON_OBJECT.search(text)
    if not match:
        raise ValueError(f"no JSON object found in cleaning agent reply: {text!r}")
    return json.loads(match.group(0))


def _user_prompt(data_type: str, file_name: str, raw_text: str) -> str:
    spec = METHOD_REGISTRY.get(data_type)
    method_context = (
        f"Method: {spec.display_name} ({data_type}). Expected x-axis: {spec.x_label}. "
        f"Expected y-axis: {spec.d_label}."
        if spec is not None
        else f"Method: {data_type} (no further metadata available)."
    )

    truncated = len(raw_text) > _MAX_PROMPT_CHARS
    body = raw_text[:_MAX_PROMPT_CHARS]
    truncation_note = (
        f"\n[NOTE: file truncated to the first {_MAX_PROMPT_CHARS} characters of a larger upload — "
        "clean what you can see and say so in the summary.]"
        if truncated
        else ""
    )

    return (
        f"{method_context}\n"
        f"Source file: {file_name}{truncation_note}\n\n"
        f"Raw data:\n{body}\n\n"
        "Respond with the JSON object described in your instructions."
    )


class LLMDataCleaner:
    def __init__(self, client: LLMClient | None = None, model: str | None = None) -> None:
        # `client` is injectable for testing; production callers leave it None.
        if client is not None:
            self._client = client
        else:
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise CleaningUnavailableError(
                    "AI data cleaning requires GEMINI_API_KEY to be configured on the server."
                )
            from ..config import settings

            self._client = build_llm_client("gemini", model or settings.gemini_model)

    def clean(self, data_type: str, file_name: str, raw_text: str) -> dict[str, Any]:
        from ..config import settings

        history = [{"role": "user", "parts": [{"text": _user_prompt(data_type, file_name, raw_text)}]}]
        text = self._client.generate(SYSTEM_PROMPT, history, settings.gemini_max_tokens)
        parsed = _extract_json(text)

        time_steps = [float(v) for v in parsed["timeSteps"]]
        amplitudes = [float(v) for v in parsed["amplitudes"]]
        dropped_count = int(parsed.get("droppedCount") or 0)
        return {
            "timeSteps": time_steps,
            "amplitudes": amplitudes,
            "originalCount": len(time_steps) + dropped_count,
            "droppedCount": dropped_count,
            "summary": str(parsed.get("summary") or ""),
            "actions": [str(a) for a in (parsed.get("actions") or [])],
        }


def build_data_cleaner() -> LLMDataCleaner:
    """No mode toggle, unlike build_modeler/build_interpreter — this stage is
    LLM-only by deliberate choice (see module docstring). Raises
    CleaningUnavailableError (not a generic exception) so main.py can
    translate it into a clear 4xx rather than a 500."""
    return LLMDataCleaner()
