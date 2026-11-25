"""Append-only local incident storage shared by safety and the dashboard API."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from src.agent.schema import TriageOutcome, TriageStatus

log = logging.getLogger(__name__)
INCIDENT_LOG_PATH = Path(os.environ.get("INCIDENT_LOG_PATH", "var/incidents.jsonl"))
ACK_LOG_PATH = Path(os.environ.get("INCIDENT_ACK_LOG_PATH", "var/incidents-acked.jsonl"))
_LOCK = RLock()


def record_outcome(outcome: TriageOutcome) -> None:
    """Persist every outcome without rewriting prior telemetry or decisions."""
    _append_json(INCIDENT_LOG_PATH, outcome.model_dump(mode="json"))


def record_manual_review(outcome: TriageOutcome) -> None:
    """Compatibility wrapper for the Phase 3 incident-feed API."""
    record_outcome(outcome)


def list_pending_reviews() -> list[TriageOutcome]:
    """Return unacknowledged manual-review incidents, newest first."""
    acknowledged = _acknowledged_ids()
    outcomes: list[TriageOutcome] = []
    if not INCIDENT_LOG_PATH.exists():
        return outcomes
    with _LOCK, INCIDENT_LOG_PATH.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                outcome = TriageOutcome.model_validate_json(line)
            except ValueError:
                log.warning("ignoring malformed incident record")
                continue
            if outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW and outcome.id not in acknowledged:
                outcomes.append(outcome)
    return list(reversed(outcomes))


def acknowledge_incident(incident_id: str, actor: str = "dashboard") -> bool:
    """Append an operator acknowledgment event; return false for unknown IDs."""
    if not any(
        outcome.id == incident_id and outcome.status == TriageStatus.REQUIRES_MANUAL_REVIEW
        for outcome in _read_outcomes()
    ):
        return False
    if incident_id in _acknowledged_ids():
        return True
    _append_json(
        ACK_LOG_PATH,
        {
            "id": incident_id,
            "actor": actor,
            "acknowledged_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return True


def _read_outcomes() -> list[TriageOutcome]:
    if not INCIDENT_LOG_PATH.exists():
        return []
    with _LOCK, INCIDENT_LOG_PATH.open("r", encoding="utf-8") as stream:
        outcomes: list[TriageOutcome] = []
        for line in stream:
            if line.strip():
                try:
                    outcomes.append(TriageOutcome.model_validate_json(line))
                except ValueError:
                    continue
        return outcomes


def _acknowledged_ids() -> set[str]:
    if not ACK_LOG_PATH.exists():
        return set()
    with _LOCK, ACK_LOG_PATH.open("r", encoding="utf-8") as stream:
        return {
            record["id"]
            for line in stream
            if line.strip()
            for record in [_safe_json(line)]
            if record is not None and "id" in record
        }


def _safe_json(line: str) -> dict[str, str] | None:
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _append_json(path: Path, value: dict[str, object]) -> None:
    with _LOCK:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(value, separators=(",", ":")) + "\n")
