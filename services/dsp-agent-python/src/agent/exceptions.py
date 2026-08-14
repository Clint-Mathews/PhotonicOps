"""Custom exceptions for the LLM triage pipeline (src/agent)."""
from __future__ import annotations


class TriageError(Exception):
    """Base class for all triage-pipeline errors."""


class OllamaUnreachableError(TriageError):
    """Raised when the local Ollama instance at localhost:11434 cannot be reached."""


class OllamaTimeoutError(TriageError):
    """Raised when a call to Ollama exceeds the NFR-1.3 2.0s latency budget."""


class SchemaValidationExhaustedError(TriageError):
    """Raised when Instructor's retry budget is exhausted without a schema-valid response."""