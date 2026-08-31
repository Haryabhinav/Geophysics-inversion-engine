"""Tests for the Joint Interpretation capstone (app/agent/joint_interpreter.py).

RuleBasedJointInterpreter is exercised directly (deterministic corroboration
counting). LLMJointInterpreter is tested with a stubbed LLMClient, same
style as test_interpreter.py.
"""

from app.agent.joint_interpreter import LLMJointInterpreter, RuleBasedJointInterpreter
from app.schemas import InterpretationResult, MethodResultInput

GRAVITY_FLAGGED = MethodResultInput(
    jobId="job-g",
    dataType="GRAVITY_SPHERE",
    status="converged",
    finalModel={"params": {"K": 8000, "z": 25, "x0": 0}},
    l2NormError=0.03,
    interpretation=InterpretationResult(
        siteId="site-1", summary="Dense body detected.", confidence="medium",
        flagged_anomaly=True, reasoning="Low L2 fit to a shallow dense body.",
    ),
)

MAGNETICS_FLAGGED = MethodResultInput(
    jobId="job-m",
    dataType="MAGNETICS_DIPOLE",
    status="converged",
    finalModel={"params": {"K": 50000, "z": 20, "x0": 0}},
    l2NormError=0.02,
    interpretation=InterpretationResult(
        siteId="site-1", summary="Magnetic body detected.", confidence="medium",
        flagged_anomaly=True, reasoning="Consistent with the gravity anomaly.",
    ),
)

LITHOLOGY_QUIET = MethodResultInput(
    jobId="job-l",
    dataType="LITHOLOGY",
    status="converged",
    finalModel={"predicted_labels": ["Shale"] * 10, "accuracy": 0.9},
    interpretation=InterpretationResult(
        siteId="site-1", summary="Shale-dominated interval.", confidence="medium",
        flagged_anomaly=False, reasoning="No target lithology detected.",
    ),
)

NO_INTERPRETATION = MethodResultInput(
    jobId="job-x",
    dataType="ERT_WENNER",
    status="max_iterations_reached",
    finalModel={"params": {"rho1": 60, "rho2": 90, "h": 15}},
)


def test_rule_based_consistent_high_when_two_methods_agree():
    interp = RuleBasedJointInterpreter()
    result = interp.interpret("site-1", [GRAVITY_FLAGGED, MAGNETICS_FLAGGED], None)
    assert result.corroboration == "consistent"
    assert result.confidence == "high"
    assert result.flagged_anomaly is True
    assert len(result.methodContributions) == 2


def test_rule_based_conflicting_when_methods_disagree():
    interp = RuleBasedJointInterpreter()
    result = interp.interpret("site-1", [GRAVITY_FLAGGED, LITHOLOGY_QUIET], None)
    assert result.corroboration == "conflicting"
    assert result.confidence == "medium"
    assert result.flagged_anomaly is True
    assert len(result.conflicts) == 1


def test_rule_based_consistent_medium_when_all_quiet():
    interp = RuleBasedJointInterpreter()
    result = interp.interpret("site-1", [LITHOLOGY_QUIET], None)
    # n_flag == 0 is "consistent — nothing flagged" regardless of how many
    # methods were considered; "inconclusive" is reserved for the single
    # method THAT DID flag with no second method to corroborate it.
    assert result.corroboration == "consistent"
    assert result.confidence == "medium"
    assert result.flagged_anomaly is False


def test_rule_based_inconclusive_with_no_determinable_verdicts():
    interp = RuleBasedJointInterpreter()
    result = interp.interpret("site-1", [NO_INTERPRETATION], None)
    assert result.corroboration == "inconclusive"
    assert result.confidence == "low"
    assert result.flagged_anomaly is False


def test_rule_based_methods_considered_lists_every_input():
    interp = RuleBasedJointInterpreter()
    result = interp.interpret("site-1", [GRAVITY_FLAGGED, MAGNETICS_FLAGGED, NO_INTERPRETATION], None)
    assert set(result.methodsConsidered) == {"GRAVITY_SPHERE", "MAGNETICS_DIPOLE", "ERT_WENNER"}


class _StubClient:
    def __init__(self, reply: str) -> None:
        self._reply = reply

    def generate(self, system, history, max_tokens):
        return self._reply


def test_llm_joint_interpreter_parses_valid_json_reply():
    reply = (
        '{"summary": "Gravity and magnetics jointly support a dense, magnetic body.", '
        '"confidence": "high", "flagged_anomaly": true, '
        '"reasoning": "Both anomalies co-locate.", "corroboration": "consistent", '
        '"conflicts": [], "methodContributions": ['
        '{"jobId": "job-g", "dataType": "GRAVITY_SPHERE", "contributesTo": "dense body", "corroboration": "consistent"},'
        '{"jobId": "job-m", "dataType": "MAGNETICS_DIPOLE", "contributesTo": "magnetic body", "corroboration": "consistent"}]}'
    )
    interp = LLMJointInterpreter(client=_StubClient(reply))
    result = interp.interpret("site-1", [GRAVITY_FLAGGED, MAGNETICS_FLAGGED], None)
    assert result.confidence == "high"
    assert result.corroboration == "consistent"
    assert len(result.methodContributions) == 2


def test_llm_joint_interpreter_degrades_gracefully_on_bad_reply():
    interp = LLMJointInterpreter(client=_StubClient("not json"))
    result = interp.interpret("site-1", [GRAVITY_FLAGGED], None)
    assert result.confidence == "low"
    assert result.corroboration == "inconclusive"
    assert "unavailable" in result.summary.lower()
