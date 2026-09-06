"""Instructor-bound triage engine
Prompts a local Ollama instance
and returns a schema valid RemediationDecision. 
Does not implement fail-safe branching - see safety.opy
for the state machine wrapping this call."""

from __future__ import annotations

import instructor
from instructor.core.exceptions import InstructorRetryException
from openai import OpenAI, APIConnectionError, APITimeoutError

from src.agent.exceptions import (
    OllamaTimeoutError,
    OllamaUnreachableError,
    SchemaValidationExhaustedError
)
from src.agent.schema import RemediationDecision

OLLAMA_BASE_URL = "http://localhost:11434/v1"
MODEL_NAME = "llama3.2:3b"
REQUEST_TIMEOUT_S = 2.0
MAX_SCHEMA_RETRIES = 2

_client = instructor.from_openai(
    OpenAI(base_url=OLLAMA_BASE_URL, api_key="ollama", timeout=REQUEST_TIMEOUT_S),
    mode=instructor.Mode.JSON,
)

_SYSTEM_PROMPT = (
    "You are a hardware diagnostics agent for a silicon photonic biosensor. "
    "Given a flagged optical telemetry window (a list of wavelength shifts in pm), "
    "classify the failure and propose exactly one remediation action.\n\n"
    "Diagnostic Rules:\n"
    "1. MICROFLUIDIC_BUBBLE: A sudden, large positive spike (e.g., reaching ~+400 to +500pm) that quickly returns near baseline. Action: FLUSH_VALVE.\n"
    "2. THERMAL_DRIFT: A slow, continuous drift near the +/- 5pm envelope without abrupt spikes. Action: RECALIBRATE_BASELINE.\n"
    "3. NORMAL_NOISE: Pure baseline noise, small random fluctuations (e.g., +/- 0.5pm). Action: NO_ACTION.\n"
    "4. PHOTONIC_ALIGNMENT_LOSS: A significant, unrecoverable loss of signal (e.g., constant large negative drops or zeros). Action: REALIGN_OPTICAL_PATH.\n\n"
    "Confidence Scoring (CRITICAL):\n"
    "- Report high confidence (>= 0.70) ONLY for unambiguous cases (e.g., a clear +500pm spike-and-decay bubble).\n"
    "- For ambiguous mid-magnitude spikes (e.g. 15-60pm), implausible flat plateaus, or unclear drift, you MUST set confidence_score < 0.70 (e.g. 0.40).\n"
    "- For THERMAL_DRIFT and NORMAL_NOISE, set confidence_score < 0.70 to ensure they are routed for manual review.\n\n"
    "Constraints:\n"
    "- For empty arrays [] or flat plateaus (e.g. [500, 500, 500, 500, 500]), you MUST output UNKNOWN and NO_ACTION.\n"
    "- You MUST strictly use exact enum strings for failure_category and remediation_action.\n\n"
    "Examples:\n"
    "Input: sensor_id=ring-01\\nwavelength_shift_pm=[0.1, -0.2, 0.15, -0.1, 0.05]\n"
    "Output: {\"failure_category\": \"NORMAL_NOISE\", \"confidence_score\": 0.60, \"remediation_action\": \"NO_ACTION\", \"reasoning\": \"Small random baseline fluctuations\"}\n\n"
    "Input: sensor_id=ring-03\\nwavelength_shift_pm=[0.8, 1.9, 380, 470, 510, 300, 40]\n"
    "Output: {\"failure_category\": \"MICROFLUIDIC_BUBBLE\", \"confidence_score\": 0.85, \"remediation_action\": \"FLUSH_VALVE\", \"reasoning\": \"Clear positive spike reaching >500pm with some noise\"}\n\n"
    "Input: sensor_id=ring-04\\nwavelength_shift_pm=[4.9, 5.1, 4.8, 5.3, 5, 4.95]\n"
    "Output: {\"failure_category\": \"THERMAL_DRIFT\", \"confidence_score\": 0.65, \"remediation_action\": \"RECALIBRATE_BASELINE\", \"reasoning\": \"Slow continuous drift near 5pm\"}\n\n"
    "Input: sensor_id=ring-05\\nwavelength_shift_pm=[2, 15, 40, 25, 8]\n"
    "Output: {\"failure_category\": \"UNKNOWN\", \"confidence_score\": 0.40, \"remediation_action\": \"NO_ACTION\", \"reasoning\": \"Ambiguous mid-magnitude spike (15-40pm), not a clear bubble or drift\"}\n\n"
    "Input: sensor_id=ring-06\\nwavelength_shift_pm=[3, 3.2, 3.1, 60, 58, 3.3]\n"
    "Output: {\"failure_category\": \"UNKNOWN\", \"confidence_score\": 0.40, \"remediation_action\": \"NO_ACTION\", \"reasoning\": \"Ambiguous mid-magnitude spike (60pm)\"}\n\n"
    "Input: sensor_id=ring-08\\nwavelength_shift_pm=[]\n"
    "Output: {\"failure_category\": \"UNKNOWN\", \"confidence_score\": 0.0, \"remediation_action\": \"NO_ACTION\", \"reasoning\": \"Empty input window\"}\n"
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
    except InstructorRetryException as exc:
        raise SchemaValidationExhaustedError(f"no schema-valid response after {MAX_SCHEMA_RETRIES} retries") from exc
