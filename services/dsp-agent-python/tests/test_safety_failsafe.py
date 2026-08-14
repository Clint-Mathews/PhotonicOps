from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agent.exceptions import (
    OllamaTimeoutError,
    OllamaUnreachableError,
    SchemaValidationExhaustedError,
)
from src.agent.safety import evaluate
from src.agent.schema import FailureCategory, RemediationAction, RemediationDecision, TriageStatus

SENSOR_ID = "ring-01"
WINDOW_START_NS = 1_700_000_000_000_000_000
FRAME = [0.1, 0.2, 480.0, 490.0]


def _make_decision(confidence: float) -> RemediationDecision:
    return RemediationDecision(
        failure_category=FailureCategory.MICROFLUIDIC_BUBBLE,
        confidence_score=confidence,
        remediation_action=RemediationAction.FLUSH_VALVE,
        reasoning="rate of change exceeds bubble threshold",
    )


@patch("src.agent.safety.triage_anomaly")
def test_low_confidence_does_not_auto_execute(mock_triage):
    mock_triage.return_value = _make_decision(confidence=0.4)
    outcome = evaluate(SENSOR_ID, WINDOW_START_NS, FRAME)
    assert outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW


@patch("src.agent.safety.triage_anomaly", side_effect=OllamaUnreachableError("down"))
def test_unreachable_does_not_auto_execute(mock_triage):
    outcome = evaluate(SENSOR_ID, WINDOW_START_NS, FRAME)
    assert outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW


@patch("src.agent.safety.triage_anomaly", side_effect=OllamaTimeoutError("slow"))
def test_timeout_does_not_auto_execute(mock_triage):
    outcome = evaluate(SENSOR_ID, WINDOW_START_NS, FRAME)
    assert outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW


@patch("src.agent.safety.triage_anomaly", side_effect=SchemaValidationExhaustedError("bad json"))
def test_schema_invalid_does_not_auto_execute(mock_triage):
    outcome = evaluate(SENSOR_ID, WINDOW_START_NS, FRAME)
    assert outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW


@patch("src.agent.safety.triage_anomaly")
def test_high_confidence_auto_executes(mock_triage):
    mock_triage.return_value = _make_decision(confidence=0.92)
    outcome = evaluate(SENSOR_ID, WINDOW_START_NS, FRAME)
    assert outcome.status == TriageStatus.AUTO_EXECUTED
    assert outcome.decision is not None