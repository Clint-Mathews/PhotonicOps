"""Langfuse tracing for triage calls. 
Local langfuse instance only - see docker-compose.yml
for the self-hosted servcie."""
from __future__ import annotations

from langfuse.decorators import langfuse_context, observe

from src.agent.schema import RemediationDecision
from src.agent.triage import triage_anomaly as _triage_anomaly

PROMPT_VERSION = "v1"

@observe(name="triage_anomaly")
def triage_anomaly(sensor_id: str, wavelength_shift_pm: list[float]) -> RemediationDecision:
    """Traced wrapper around triage.triage_anomaly. Logs prompt version
    Let Langfuse's OpenAI instrumentation capture token usage/latency from the underlying Instructor call automatically."""
    langfuse_context.update_current_observation(
        metadata={"prompt_version": PROMPT_VERSION, "sensor_id": sensor_id}
    )
    return _triage_anomaly(sensor_id, wavelength_shift_pm)