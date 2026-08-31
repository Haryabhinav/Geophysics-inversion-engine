"""Tests for the Data Cleaning Agent (app/agent/data_cleaner.py).

LLMDataCleaner is tested with a stubbed LLMClient — no network, no API key —
same style as test_interpreter.py's LLMInterpreter tests. There is no
offline/rule-based double to test here: this stage is deliberately LLM-only
(see the module docstring for why), so `build_data_cleaner()` without a key
configured is itself a test case, not a gap.
"""

import pytest
from pydantic import ValidationError

from app.agent.data_cleaner import CleaningUnavailableError, LLMDataCleaner, build_data_cleaner
from app.schemas_cleaning import CleaningResult


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply


def test_cleans_valid_reply():
    reply = (
        '{"timeSteps": [1, 2, 3], "amplitudes": [0.1, 0.2, 0.3], '
        '"droppedCount": 1, "summary": "Removed one spike.", '
        '"actions": ["removed 1 outlier spike at index 4"]}'
    )
    cleaner = LLMDataCleaner(client=_StubClient(reply))
    result = cleaner.clean("TDEM", "field.csv", "raw garbage text")

    assert result["timeSteps"] == [1.0, 2.0, 3.0]
    assert result["amplitudes"] == [0.1, 0.2, 0.3]
    assert result["droppedCount"] == 1
    assert result["originalCount"] == 4  # 3 kept + 1 dropped
    assert "spike" in result["actions"][0]


def test_defaults_missing_optional_fields():
    """A reply that omits droppedCount/actions shouldn't crash — it means
    the model didn't remove anything or didn't itemize what it did."""
    reply = '{"timeSteps": [1, 2], "amplitudes": [5, 6], "summary": "No changes needed."}'
    cleaner = LLMDataCleaner(client=_StubClient(reply))
    result = cleaner.clean("GRAVITY_SPHERE", "clean.csv", "1,5\n2,6")

    assert result["droppedCount"] == 0
    assert result["originalCount"] == 2
    assert result["actions"] == []


def test_raises_on_malformed_reply_rather_than_returning_garbage():
    """Unlike the Interpretation Agent, a malformed reply here must not
    degrade to a best-effort placeholder — that placeholder would otherwise
    be validated as real cleaned data and fed into the inversion pipeline."""
    cleaner = LLMDataCleaner(client=_StubClient("not json at all"))
    with pytest.raises(Exception):
        cleaner.clean("TDEM", "bad.csv", "garbage")


def test_mismatched_array_lengths_are_not_silently_accepted():
    """The reply parses as JSON fine but the arrays disagree in length —
    schemas_cleaning.CleaningResult's validator is what actually catches
    this at the FastAPI boundary; clean() itself just returns the raw dict,
    so this test documents that the dict is NOT validated at this layer."""
    reply = '{"timeSteps": [1, 2, 3], "amplitudes": [1, 2], "summary": "x"}'
    cleaner = LLMDataCleaner(client=_StubClient(reply))
    result = cleaner.clean("TDEM", "f.csv", "raw")
    assert len(result["timeSteps"]) != len(result["amplitudes"])


def test_cleaning_result_schema_rejects_mismatched_lengths():
    """This is the actual guard: the FastAPI route validates the cleaner's
    raw dict against CleaningResult, and THIS is what would reject the
    length mismatch clean() itself lets through (see the test above)."""
    with pytest.raises(ValidationError):
        CleaningResult(
            timeSteps=[1.0, 2.0, 3.0],
            amplitudes=[1.0, 2.0],
            originalCount=3,
            droppedCount=0,
            summary="x",
            actions=[],
        )


def test_build_data_cleaner_without_api_key_raises_clear_error(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(CleaningUnavailableError, match="GEMINI_API_KEY"):
        build_data_cleaner()
