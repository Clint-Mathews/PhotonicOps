import { useEffect, useState } from "react";

type Incident = { id: string; sensor_id: string; reason: string; status: string; evaluated_at: string; decision?: { confidence_score: number } };
const apiBase = (import.meta.env.VITE_DSP_HTTP as string | undefined) ?? "http://localhost:8000";

export function IncidentLog() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const refresh = () => fetch(`${apiBase}/incidents`).then((response) => response.json()).then(setIncidents).catch(() => undefined);
  useEffect(() => { refresh(); const timer = window.setInterval(refresh, 2000); return () => window.clearInterval(timer); }, []);
  const acknowledge = (id: string) => fetch(`${apiBase}/incidents/${id}/ack`, { method: "POST" }).then(refresh);

  return (
    <section className="panel incidents-panel">
      <div className="panel-heading"><div><span className="section-kicker">OPERATOR QUEUE</span><h2>Manual review incidents</h2></div><span className="queue-count">{incidents.length.toString().padStart(2, "0")} OPEN</span></div>
      {incidents.length === 0 ? <div className="empty-state">No pending incidents. Fail-safe decisions will appear here when the local model is unreachable or uncertain.</div> :
        <div className="incident-list">{incidents.map((incident) => <article className="incident" key={incident.id}>
          <div className="incident-marker" /><div className="incident-main"><strong>{incident.sensor_id}</strong><span>{incident.reason}</span><small>{new Date(incident.evaluated_at).toLocaleString()}</small></div>
          <div className="confidence"><span>{incident.status}</span><br />{incident.decision ? `${Math.round(incident.decision.confidence_score * 100)}% confidence` : "NO MODEL RESPONSE"}</div>
          <button onClick={() => acknowledge(incident.id)}>ACKNOWLEDGE</button>
        </article>)}</div>}
    </section>
  );
}
