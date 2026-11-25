import { useEffect, useRef } from "react";

type WindowPayload = { sensor_id: string; raw: number[]; filtered: number[]; baseline_removed: number[]; has_anomaly: boolean };

const apiBase = (import.meta.env.VITE_DSP_HTTP as string | undefined) ?? "http://localhost:8000";

export function SignalChart() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const latest = useRef<WindowPayload | null>(null);
  const connected = useRef(false);

  useEffect(() => {
    const socketUrl = `${apiBase.replace(/^http/, "ws")}/ws/signal`;
    const socket = new WebSocket(socketUrl);
    socket.onopen = () => { connected.current = true; };
    socket.onmessage = (event) => {
      const payload = JSON.parse(event.data) as WindowPayload;
      latest.current = payload.sensor_id ? payload : null;
    };
    socket.onclose = () => { connected.current = false; };

    let frame = 0;
    const render = () => {
      draw(canvasRef.current, latest.current, connected.current);
      frame = requestAnimationFrame(render);
    };
    frame = requestAnimationFrame(render);
    return () => { socket.close(); cancelAnimationFrame(frame); };
  }, []);

  return <canvas ref={canvasRef} className="signal-canvas" aria-label="Live raw and filtered signal plot" />;
}

function draw(canvas: HTMLCanvasElement | null, payload: WindowPayload | null, connected: boolean) {
  if (!canvas) return;
  const ratio = globalThis.window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== width * ratio || canvas.height !== height * ratio) {
    canvas.width = width * ratio;
    canvas.height = height * ratio;
  }
  const context = canvas.getContext("2d");
  if (!context) return;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  context.fillStyle = "#081018";
  context.fillRect(0, 0, width, height);
  context.strokeStyle = "#18303c";
  context.lineWidth = 1;
  for (let y = 24; y < height; y += 34) { context.beginPath(); context.moveTo(0, y); context.lineTo(width, y); context.stroke(); }
  if (!payload) {
    context.fillStyle = "#6f8790";
    context.font = "12px ui-monospace, monospace";
    context.fillText(connected ? "WAITING FOR SENSOR WINDOW" : "CONNECTING TO DSP API", 22, height / 2);
    return;
  }
  plot(context, payload.raw, width, height, "#d8a85d");
  plot(context, payload.filtered, width, height, "#47d7b0");
  context.fillStyle = "#8aa1a8";
  context.font = "11px ui-monospace, monospace";
  context.fillText(payload.sensor_id, 18, 22);
  context.fillStyle = payload.has_anomaly ? "#f26c62" : "#47d7b0";
  context.fillText(payload.has_anomaly ? "ANOMALY" : "NOMINAL", width - 76, 22);
}

function plot(context: CanvasRenderingContext2D, values: number[], width: number, height: number, color: string) {
  if (values.length < 2) return;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 0.001);
  context.strokeStyle = color;
  context.lineWidth = 1.5;
  context.beginPath();
  values.forEach((value, index) => {
    const x = (index / (values.length - 1)) * width;
    const y = height - 22 - ((value - min) / range) * (height - 44);
    if (index === 0) context.moveTo(x, y); else context.lineTo(x, y);
  });
  context.stroke();
}
