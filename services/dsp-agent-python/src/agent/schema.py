"""Pydantic contract for LLM triage output. No raw free-text generation
is ever accepted downstream of this module - every LLM call binds to one of
these models via Instructor."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator

class FailureCategory(str, Enum):
    MICROFLUIDIC_BUBBLE = "MICROFLUIDIC_BUBBLE"
    THERMAL_DRIFT = "THERMAL_DRIFT"
    PHOTONIC_ALIGNMENT_LOSS = "PHOTONIC_ALIGNMENT_LOSS"
    NORMAL_NOISE = "NORMAL_NOISE"
    UNKNOWN = "UNKNOWN"
    
class RemediationAction(str, Enum):
    FLUSH_VALVE = "FLUSH_VALVE"
    RECALIBRATE_BASELINE = "RECALIBRATE_BASELINE"
    REALIGN_OPTICAL_PATH = "REALIGN_OPTICAL_PATH"
    NO_ACTION = "NO_ACTION"

class RemediationDecision(BaseModel):
    """ The structured output Instructor binds the Ollama call to. 
    This model alone does not decide whether an action executes - see TriageOutcome."""
    
    failure_category: FailureCategory
    confidence_score: float = Field(ge=0.0, le=1.0)
    remediation_action: RemediationAction
    reasoning: str = Field(min_length=1, max_length=500)

class TriageStatus(str, Enum):
    AUTO_EXECUTED = "AUTO_EXECUTED"
    REQUIRES_MANUAL_REVIEW = "REQUIRES_MANUAL_REVIEW"

class TriageOutcome(BaseModel):
    """Result of running a RemediationDecision through the fail-safe 
    state machine. This not RemediationDecision, is what gets persisted
    to the audit log and the incident feed."""
    id: str | None = None
    status: TriageStatus
    decision: RemediationDecision | None
    reason: str
    sensor_id: str
    window_start_ns: int
    evaluated_at: datetime

    @model_validator(mode="after")
    def assign_stable_id(self) -> "TriageOutcome":
        if self.id is None:
            value = f"{self.sensor_id}:{self.window_start_ns}:{self.evaluated_at.isoformat()}"
            self.id = sha256(value.encode("utf-8")).hexdigest()[:24]
        return self
