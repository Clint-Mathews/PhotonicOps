""" Fail-safe state machine. This module is the single authorized caller of the triage_anomaly - 
nothing else in the codebase may invoke the LLM triage path directly,
so every hardware-actuation decision is guaranteed to pass through this gate."""
from __future__ import annotations

from datetime import datetime, timezone

from src.agent.exceptions import (
    OllamaTimeoutError,
    OllamaUnreachableError,
    SchemaValidationExhaustedError
)
from src.agent.schema import (
RemediationDecision, TriageOutcome, TriageStatus)
from src.agent.tracer import triage_anomaly

from src.agent.incident_feed import record_manual_review

CONFIDENCE_THRESHOLD = 0.7

def evaluate(sensor_id: str, window_start_ns: int, wavelength_shift_pm: list[float]) -> TriageOutcome:
    """Runs the LLM triage call and applies the fail-safe rules. 
    returns a TriageOutcome; never raises - every failure modde of
    triage_anomaly is caught here and converted into REQUIRES_MANUAL_REVIEW
    so a caller can persist the outcome unconditionally."""
    now = datetime.now(timezone.utc)

    try:
        decision: RemediationDecision = triage_anomaly(sensor_id, wavelength_shift_pm)
    except OllamaUnreachableError:
        return _manual_review(sensor_id, window_start_ns, now, None, "ollama unreachable")
    except OllamaTimeoutError:
        return _manual_review(sensor_id, window_start_ns, now, None, "ollama call timed out")
    except SchemaValidationExhaustedError:
        return _manual_review(sensor_id, window_start_ns, now, None, "response failed schema validation")
    
    if decision.confidence_score < CONFIDENCE_THRESHOLD:
        return _manual_review(sensor_id, window_start_ns, now, decision, f"confidence {decision.confidence_score: .2f} below threshold {CONFIDENCE_THRESHOLD}")
    return TriageOutcome(
        status = TriageStatus.AUTO_EXECUTED,
        decision = decision,
        reason = "schema-valid and confidence threshold cleared",
        sensor_id = sensor_id,
        window_start_ns = window_start_ns,
        evaluated_at = now,
    )

def _manual_review(
    sensor_id: str,
    window_start_ns: int,
    now: datetime,
    decision: RemediationDecision | None,
    reason: str
    ) -> TriageOutcome:
    outcome = TriageOutcome(
        status = TriageStatus.REQUIRES_MANUAL_REVIEW,
        decision = decision,
        reason = reason,
        sensor_id = sensor_id,
        window_start_ns = window_start_ns,
        evaluated_at = now,
    )
    record_manual_review(outcome)
    return outcome
