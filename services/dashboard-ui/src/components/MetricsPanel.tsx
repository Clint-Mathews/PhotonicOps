export function MetricsPanel() {
  return <aside className="panel metrics-panel">
    <span className="section-kicker">SYSTEM MAP</span>
    <h2>Local runtime</h2>
    <div className="metric-row"><span>Ingestion</span><strong>10 kHz</strong></div>
    <div className="metric-row"><span>DSP transport</span><strong>UDS / local</strong></div>
    <div className="metric-row"><span>Inference</span><strong>Ollama only</strong></div>
    <div className="metric-row"><span>Retention</span><strong>JSONL audit</strong></div>
    <a href="http://localhost:3001" target="_blank" rel="noreferrer" className="grafana-link">OPEN GRAFANA <span>{"->"}</span></a>
  </aside>;
}
