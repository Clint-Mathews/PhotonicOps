"""Instructor-bound triage engine
Prompts a local Ollama instance
and returns a schema valid RemediationDecision. 
Does not implement fail-safe branching - see safety.opy
for the state machine wrapping this call."""

from __future__ import annotations

import instructor
from openai import OpenAI, APIConnectionError, APITimeoutError

from src.agent.exceptions import (
    OllamaTimeoutError,
    OllamaUnreachableError,
    SchemaValidationExhaustedError
)
from src.agent.schema import RemediationDecision

OLLAMA_BASE_URL = "http://localhost:11434/v1"
MODEL_NAME = "llama3.1:8b"
REQUEST_TIMEOUT_S = 2.0
MAX_SCHEMA_RETRIES = 2

_client = instructor.from_openai(
    OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=REQUEST_TIMEOUT_S),
    mode=instructor.Mode.JSON,
)

_SYSTEM_PROMPT = (
    "You are a hardware diagnostics agent for a silicon photonic biosensor. "
    "Given a flagged optical telemetry window, classify the failure and "
    "propose exactly one remediation action. Be conservative with "
    "confidence_score: only report high confidence when the signal pattern "
    "unambiguously matches one failure category."
)

def triage_anomaly(sensor_id: str, wavelength_shift_pm: list[float]) -> RemediationDecision:
    """Prompts the local LLM with a flagged anomaly window and returns a
    schema-valid RemediationDecision. 
    Raises OllamaUnreachableError, or SchemaValidationExhaustedError on failure -
    callers (saftey.py) must catch all three and route to REQUIRES_MANUAL_REVIEW rather than letting them
    propagate to hardware-actuation code.
    """
    user_prompt = (
        f"sensor_id={sensor_id}\n"
        f"wavelength_shift_pm={wavelength_shift_pm}\n"
        "Classify this anomaly and propose a remediation action."
    )
    try:
        return _client.chat.completions.create(
            model=MODEL_NAME,
            response_model=RemediationDecision,
            max_retries=MAX_SCHEMA_RETRIES,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ]
        )
    except APITimeoutError as exc:
        raise OllamaTimeoutError(f"triage call exceeded {REQUEST_TIMEOUT_S}s budget") from exc
    except APIConnectionError as exc:
        raise OllamaUnreachableError(f"count not reach Ollama at {OLLAMA_BASE_URL}") from exc
    except instructor.exceptions.InstructorRetryException as exc:
        raise SchemaValidationExhaustedError(f"no schema-valid response after {MAX_SCHEMA_RETRIES} retries") from exc
