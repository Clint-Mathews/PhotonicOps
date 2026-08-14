"""Diagnostics audit trail."""
from __future__ import annotations

import os
import psycopg

from src.agent.schema import TriageOutcome

_DSN = os.environ["AUDIT_LOG_DSN"] # e.g. postgresql://photonicops:***@localhost:5432/audit

def audit_log(outcome: TriageOutcome) -> None:
    """Persists a TriageOutcome unconditionally regardless of status."""
    with psycopg.connect(_DSN) as conn, conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO triage_audit_log(sensor_id, window_start_ns, status, reason, decision_json, evaluated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                outcome.sensor_id,
                outcome.window_start_ns,
                outcome.status.value,
                outcome.reason,
                outcome.decision.model_dump_json() if outcome.decision else None,
                outcome.evaluated_at,
            ),
        )
        conn.commit()