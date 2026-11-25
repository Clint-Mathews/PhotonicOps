import { IncidentLog } from "./components/IncidentLog";
import { MetricsPanel } from "./components/MetricsPanel";
import { SignalChart } from "./components/SignalChart";

export default function App() {
  return (
    <main className="shell">
      <header className="masthead">
        <div>
          <p className="eyebrow">PHOTONICOPS / EDGE CONTROL ROOM</p>
          <h1>Signal intelligence, without the cloud.</h1>
        </div>
        <div className="status-pill"><span className="status-dot" /> LOCAL PIPELINE ONLINE</div>
      </header>
      <section className="hero-grid">
        <div className="panel signal-panel">
          <div className="panel-heading">
            <div><span className="section-kicker">LIVE TELEMETRY</span><h2>Raw vs filtered wavelength</h2></div>
            <span className="frame-rate">30 FPS VIEW</span>
          </div>
          <SignalChart />
        </div>
        <MetricsPanel />
      </section>
      <IncidentLog />
      <footer>Air-gapped observability stack · Prometheus :9090 · Grafana :3001 · DSP API :8000</footer>
    </main>
  );
}
