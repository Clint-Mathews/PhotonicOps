from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from src.agent import incident_feed
from src.agent.schema import TriageOutcome, TriageStatus
from src.httpapi.server import LatestWindowStore, create_app


def test_incident_list_and_ack_are_append_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(incident_feed, "INCIDENT_LOG_PATH", tmp_path / "incidents.jsonl")
    monkeypatch.setattr(incident_feed, "ACK_LOG_PATH", tmp_path / "acks.jsonl")
    outcome = TriageOutcome(
        status=TriageStatus.REQUIRES_MANUAL_REVIEW,
        decision=None,
        reason="ollama unreachable",
        sensor_id="ring-01",
        window_start_ns=123,
        evaluated_at=datetime.now(timezone.utc),
    )
    incident_feed.record_outcome(outcome)
    client = TestClient(create_app(LatestWindowStore()))

    response = client.get("/incidents")
    assert response.status_code == 200
    assert response.json()[0]["id"] == outcome.id

    assert client.post(f"/incidents/{outcome.id}/ack").json()["ok"] is True
    assert client.get("/incidents").json() == []
    assert (tmp_path / "incidents.jsonl").read_text().count("\n") == 1
    assert (tmp_path / "acks.jsonl").read_text().count("\n") == 1


def test_signal_websocket_returns_latest_windows() -> None:
    client = TestClient(create_app(LatestWindowStore()))
    with client.websocket_connect("/ws/signal") as websocket:
        assert websocket.receive_json()["sensor_id"] == ""
