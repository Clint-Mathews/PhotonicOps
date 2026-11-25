#!/usr/bin/env python3
"""Reject privacy and transport regressions in source and CI configuration."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCANNED_SUFFIXES = {".py", ".go", ".yml", ".yaml"}
REQUIRED_CONSTRAINTS = (
    ROOT / ".agents/AGENTS.md",
    ROOT / ".claude/skills/go-architect/SKILL.md",
)


def scan_paths(paths: list[Path]) -> list[str]:
    findings: list[str] = []
    cloud_hosts = ("api." + "openai.com", "api." + "anthropic.com", "generativelanguage.googleapis.com")
    hosted_telemetry = ("api." + "smith", "api." + "langfuse.com", "datadoghq.com")
    for path in paths:
        if (
            path.resolve() == Path(__file__).resolve()
            or path.suffix not in SCANNED_SUFFIXES
            or ".git" in path.parts
            or ".venv" in path.parts
            or "node_modules" in path.parts
            or path.name.startswith("test_")
        ):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), 1):
            if any(host in line for host in cloud_hosts):
                findings.append(f"{path}:{line_number}: cloud LLM endpoint")
            if any(host in line.lower() for host in hosted_telemetry):
                findings.append(f"{path}:{line_number}: hosted telemetry endpoint")
            if "anthropic" in line.lower():
                findings.append(f"{path}:{line_number}: Anthropic client or reference")
            if "from openai import" in line or "openai.OpenAI(" in line:
                if "localhost:11434" not in text and "ollama:11434" not in text:
                    findings.append(f"{path}:{line_number}: OpenAI client without local Ollama base URL")
            if "insecure.NewCredentials()" in line:
                allowed = path.as_posix().endswith("services/ingestion-go/internal/dsp/forwarder.go")
                if not allowed:
                    findings.append(f"{path}:{line_number}: insecure TCP gRPC credentials")
    return findings


def main() -> int:
    missing = [str(path) for path in REQUIRED_CONSTRAINTS if not path.is_file()]
    if missing:
        print("missing required constraint files:", *missing, sep="\n", file=sys.stderr)
        return 1
    paths = [path for path in ROOT.rglob("*") if path.is_file()]
    findings = scan_paths(paths)
    if findings:
        print("privacy and transport policy violations:", *findings, sep="\n", file=sys.stderr)
        return 1
    print("No cloud LLM, hosted telemetry, or disallowed TCP credentials found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
