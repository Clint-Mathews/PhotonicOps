"""Minimal REQUIRES_MANUAL_REVIEW surface. 
Append-only JSONL - intentionally not a database; promotes this into the full dashboard incident queue later."""
from __future__ import annotations

import json
from pathlib import Path

from src.agent.schema import TriageOutcome

INCIDENT_LOG_PATH = Path("var/incidents.jsonl")

def record_manual_review(outcome: TriageOutcome) -> None:
    """Appends a REQUIRES_MANUAL_REVIEW outcome to the incident feed."""
    INCIDENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with INCIDENT_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(outcome.model_dump_json() + "\n")

def list_pending_reviews() -> List[TriageOutcome]:
    """Reads all recorded manual-review incidents. CLI facing for now."""
    if not INCIDENT_LOG_PATH.exists():
        return []
    with INCIDENT_LOG_PATH.open("r", encoding="utf-8") as f:
        return [TriageOutcome.model_validate_json(line) for line in f if line.strip()]