from pathlib import Path

from check_no_cloud_llm import scan_paths


def test_local_ollama_client_is_allowed(tmp_path: Path) -> None:
    path = tmp_path / "triage.py"
    path.write_text('from openai import OpenAI\nBASE = "http://localhost:11434/v1"\n')
    assert scan_paths([path]) == []


def test_cloud_endpoint_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.py"
    path.write_text('client = OpenAI(base_url="https://api.openai.com/v1")\n')
    assert scan_paths([path])


def test_tcp_insecure_credentials_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "server.go"
    path.write_text('grpc.WithTransportCredentials(insecure.NewCredentials' + '())\n')
    assert scan_paths([path])
