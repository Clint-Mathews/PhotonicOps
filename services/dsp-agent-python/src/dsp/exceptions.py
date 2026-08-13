"""Custom exceptions for the DSP pipeline (src/dsp)."""
from __future__ import annotations

class DSPError(Exception):
    """Base class for all DSP-pipeline errors."""

class EmptyFrameBatchError(DSPError):
    """Raised when a FrameBatch/array has zero samples to process."""

class MismatchedFrameLengthError(DSPError):
    """Raised when wavelength and timestamp arrays for a batch disagree in length."""

class InvalidFilterParametersError(DSPError):
    """Raised when Kalman filter variances or window sizes are non-physical (<= 0)."""

