"""Tests for the Interpretation Agent (app/agent/interpreter.py).

RuleBasedInterpreter is exercised directly (deterministic, no stubbing
needed). LLMInterpreter is tested with a stubbed LLMClient so these run
instantly with no network/API key, same style as test_orchestrator.py.
"""

from app.agent.interpreter import LLMInterpreter, RuleBasedInterpreter
from app.schemas import InversionResult

CONVERGED_SIMPLE = InversionResult(
    jobId="job",
    status="converged",
    final_model={"res": [50, 200], "depth": [40]},
    l2_norm_error=0.03,
    iterations=3,
    equivalent_models=[],
)

CONVERGED_CONDUCTIVE = InversionResult(
    jobId="job",
    status="converged",
    final_model={"res": [8, 200], "depth": [40]},
    l2_norm_error=0.03,
    iterations=3,
    equivalent_models=[],
)

CONVERGED_AMBIGUOUS = InversionResult(
    jobId="job",
    status="max_iterations_reached",
    final_model={"res": [50, 200], "depth": [40]},
    l2_norm_error=0.06,
    iterations=6,
    equivalent_models=[
        {"model": {"res": [50, 200], "depth": [40]}, "l2_norm_error": 0.06},
        {"model": {"res": [45, 210], "depth": [38]}, "l2_norm_error": 0.07},
    ],
)


def test_rule_based_flags_anomaly_when_model_and_note_agree():
    interp = RuleBasedInterpreter()
    result = interp.interpret("site-1", CONVERGED_CONDUCTIVE, "Driller reported wet clay at 35-45m.")
    assert result.flagged_anomaly is True
    assert result.confidence == "high"


def test_rule_based_low_confidence_without_note():
    interp = RuleBasedInterpreter()
    result = interp.interpret("site-1", CONVERGED_CONDUCTIVE, None)
    assert result.confidence == "medium"
    assert result.flagged_anomaly is True  # model alone still says conductive


def test_rule_based_reports_ambiguity_when_no_context():
    interp = RuleBasedInterpreter()
    result = interp.interpret("site-1", CONVERGED_AMBIGUOUS, None)
    assert result.confidence == "low"
    assert result.flagged_anomaly is False
    assert "no site context was available" in result.summary


def test_rule_based_does_not_claim_missing_context_when_a_note_exists():
    """A note that this coarse rule can't act on still isn't 'no context'.

    The equivalence branch used to hard-code 'no site context was available'
    regardless, so a site with a driller's log on record was reported as
    having none — and that sentence is quoted verbatim into the multi-method
    Joint Interpretation report.
    """
    interp = RuleBasedInterpreter()
    note = "Historical workings mention a dense, magnetite-bearing ore body at 25-40 m."
    result = interp.interpret("site-1", CONVERGED_AMBIGUOUS, note)

    # Still unresolved (the note has no conductive keyword to match) ...
    assert result.confidence == "low"
    assert result.flagged_anomaly is False
    # ... but it must not claim the note doesn't exist.
    assert "no site context was available" not in result.summary
    assert "does not decide between them" in result.summary


def test_rule_based_well_constrained_no_ambiguity():
    interp = RuleBasedInterpreter()
    result = interp.interpret("site-1", CONVERGED_SIMPLE, None)
    assert result.confidence == "medium"
    assert result.flagged_anomaly is False


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply


def test_llm_interpreter_parses_valid_json_reply():
    reply = (
        '{"summary": "Likely a clay aquitard.", "confidence": "high", '
        '"flagged_anomaly": true, "reasoning": "Low resistivity matches drill note."}'
    )
    interp = LLMInterpreter(client=_StubClient(reply))
    result = interp.interpret("site-1", CONVERGED_CONDUCTIVE, "wet clay noted")
    assert result.confidence == "high"
    assert result.flagged_anomaly is True
    assert "clay" in result.summary.lower()


def test_llm_interpreter_degrades_gracefully_on_bad_reply():
    interp = LLMInterpreter(client=_StubClient("not json at all"))
    result = interp.interpret("site-1", CONVERGED_SIMPLE, None)
    assert result.confidence == "low"
    assert result.flagged_anomaly is False
    assert "unavailable" in result.summary.lower()
