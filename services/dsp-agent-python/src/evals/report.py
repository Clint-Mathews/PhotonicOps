"""Post-processes promptfoo's results.json into the Phase 4A gate metrics:
remediation accuracy, false-positive rate, and p50/p95 latency. Also appends
failing cases to a cumulative failure log, per Roadmap Task 4.1 ("keep a
record of prompts that didn't work; the failure log is a valuable as the pass rate")."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

RESULTS_PATH = Path("results.json")
FAILURE_LOG_PATH = Path("src/evals/failure_log.jsonl")
ACCURACY_GATE = 0.95

def _percentile(sorted_values: List[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct
    lo, hi = int(k), min(int(k) + 1, len(sorted_values)-1)
    if lo == hi:
        return sorted_values[lo]
    return sorted_values[lo] + (sorted_values[hi] - lo) * (sorted_values[hi] - sorted_values[lo])

def main() -> int:
    data = json.loads(RESULTS_PATH.read_text())
    results = data["results"]["results"]

    latencies: List[float] = []
    correct = 0
    false_positives = 0 # expected REQUIRES_MANUAL_REVIEW but agent AUTO_EXECUTED
    total = len(results)
    failures: List[dict] = []

    for r in results:
        case_vars = r["testCase"]["vars"]
        output = r.get("response", {}).get("output") or {}
        latency = r.get("response", {}).get("latencyMs")
        if latency is not None:
            latencies.append(latency)
        expected_status = case_vars.get("expected_status")
        actual_status = output.get("status")
        passed = bool(r.get("success"))

        if passed:
            correct += 1
        else:
            failures.append({
                "sensor_id": case_vars.get("sensor_id"),
                "class": case_vars.get("class"),
                "expected_status": expected_status,
                "actual_status": actual_status,
                "expected_failure_category": case_vars.get("expected_failure_category"),
                "actual_failure_category": output.get("failure_category"),
                "notes": case_vars.get("notes"),
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            })
        
        if expected_status == "REQUIRES_MANUAL_REVIEW" and actual_status == "AUTO_EXECUTED":
            false_positives += 1

    accuracy = correct / total if total > 0 else 0.0
    fpr = false_positives / total if total > 0 else 0.0
    latencies.sort()
    p50 = _percentile(latencies, 0.50)
    p95 = _percentile(latencies, 0.95)

    print(f"remediation accuracy: {accuracy:.1%} ({correct}/{total})")
    print(f"false-positive rate (unsafe auto-execute): {fpr:.1%} ({false_positives}/{total})")    
    print(f"latency p50: {p50:.1f} ms, p95: {p95:.1f} ms")

    if failures:
        FAILURE_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FAILURE_LOG_PATH.open('a', encoding="utf-8") as f:
            for entry in failures:
                f.write(json.dumps(entry) + '\n')
        print(f"appended {len(failures)} failing case(s) to {FAILURE_LOG_PATH}")
    
    if accuracy < ACCURACY_GATE:
        print(f"GATE FAILED: {accuracy:.1%} < required {ACCURACY_GATE:.0%}", file=sys.stderr)
        return 1
    
    print("GATE PASSED")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
    


