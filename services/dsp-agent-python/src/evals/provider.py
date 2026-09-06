"""Promptfoo Python provider. Wraps src.agent.safety.evaluate so the eval
suite exercises the fails-safe pipeline, not just a raw LLM call - requires the fail-safe
paths to be covered, and those only exist at the safety.py layer, not inside triage.py alone.
"""
from __future__ import annotations

import os
import sys

# provider.py lives at src/evals/, so three dirname() calls reach services/dsp-agent-python,
# the root from which `from src.agent...` imports resolve correctly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import httpx
import json
import time
from typing import Any
from unittest.mock import patch

from src.agent.exceptions import OllamaTimeoutError, OllamaUnreachableError
from src.agent.safety import evaluate
import src.agent.triage

# Relax the production 2.0s timeout to 60s for local evaluation so the test suite
# does not fail when Ollama is running on a slow local dev container.
client = src.agent.triage._client.client
assert client is not None
client.timeout = httpx.Timeout(60.0) 

def call_api(prompt: str, options: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    """Promptfoo's required entry point.

    When a JSON array is loaded via file://, promptfoo assigns each element as
    the value of the named var key. So context["vars"]["sensor_id"] holds the
    entire test case object, not just the sensor_id string.
    """
    # With `tests: file://test_cases.json`, each object in the array becomes one
    # test run and its fields land directly in context["vars"].
    case = context["vars"]
    sensor_id: str = case["sensor_id"]
    wavelength_shift_pm: list[float] = case["wavelength_shift_pm"]
    
    start = time.perf_counter()

    if case.get("simulate_ollama_unreachable"):
        with patch("src.agent.safety.triage_anomaly", side_effect=OllamaUnreachableError("simulated")):
            outcome = evaluate(
                sensor_id=sensor_id,
                window_start_ns=0,
                wavelength_shift_pm=wavelength_shift_pm
            )
    elif case.get("simulate_timeout"):
        with patch("src.agent.safety.triage_anomaly", side_effect=OllamaTimeoutError("simulated")):
            outcome = evaluate(sensor_id, window_start_ns=0, wavelength_shift_pm=wavelength_shift_pm)
    else:
        outcome = evaluate(sensor_id, window_start_ns=0, wavelength_shift_pm=wavelength_shift_pm) 

    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "output": {
            "status": outcome.status.value,
            "failure_category": outcome.decision.failure_category.value if outcome.decision else None,
            "remediation_action": outcome.decision.remediation_action.value if outcome.decision else None,
            "confidence_score": outcome.decision.confidence_score if outcome.decision else None,
            "reason": outcome.reason,
        },
        "latencyMs": latency_ms,
    }