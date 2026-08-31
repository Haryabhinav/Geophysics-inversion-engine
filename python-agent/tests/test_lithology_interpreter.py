"""Tests for the LITHOLOGY interpreter — mirrors test_interpreter.py's style."""

from app.agent.lithology_interpreter import LLMLithologyInterpreter, RuleBasedLithologyInterpreter
from app.schemas import InversionResult

CLASSIFIED_HIGH_ACCURACY = InversionResult(
    jobId="job",
    status="converged",
    final_model={
        "predicted_labels": ["Coal", "Coal", "Coal", "Shale"],
        "accuracy": 0.92,
    },
)

CLASSIFIED_LOW_ACCURACY = InversionResult(
    jobId="job",
    status="converged",
    final_model={"predicted_labels": ["Sandstone", "Shale"], "accuracy": 0.4},
)


def test_rule_based_flags_when_dominant_label_matches_note():
    interp = RuleBasedLithologyInterpreter()
    result = interp.interpret("site-1", CLASSIFIED_HIGH_ACCURACY, "Historical records mention coal seams here.")
    assert result.flagged_anomaly is True
    assert result.confidence == "high"


def test_rule_based_no_flag_without_note():
    interp = RuleBasedLithologyInterpreter()
    result = interp.interpret("site-1", CLASSIFIED_HIGH_ACCURACY, None)
    assert result.flagged_anomaly is False
    assert result.confidence == "medium"


def test_rule_based_low_confidence_with_no_predictions():
    interp = RuleBasedLithologyInterpreter()
    empty = InversionResult(jobId="job", status="error", final_model={})
    result = interp.interpret("site-1", empty, None)
    assert result.confidence == "low"
    assert result.flagged_anomaly is False


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply


def test_llm_interpreter_parses_valid_json_reply():
    reply = (
        '{"summary": "Coal-dominated interval.", "confidence": "high", '
        '"flagged_anomaly": true, "reasoning": "Matches the site note."}'
    )
    interp = LLMLithologyInterpreter(client=_StubClient(reply))
    result = interp.interpret("site-1", CLASSIFIED_HIGH_ACCURACY, "coal seams reported")
    assert result.confidence == "high"
    assert result.flagged_anomaly is True


def test_llm_interpreter_degrades_gracefully_on_bad_reply():
    interp = LLMLithologyInterpreter(client=_StubClient("not json"))
    result = interp.interpret("site-1", CLASSIFIED_LOW_ACCURACY, None)
    assert result.confidence == "low"
    assert "unavailable" in result.summary.lower()
