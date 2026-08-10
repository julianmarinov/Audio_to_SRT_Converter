"""Transcription backend abstraction.

Each backend wraps a different Whisper implementation behind a common
interface so the rest of the app doesn't need to know which one is in use.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Protocol

import torch


def get_device() -> torch.device:
    """Best available compute device: CUDA > Apple Silicon MPS > CPU."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_built() and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    segments: list[Segment]
    language: Optional[str] = None


class TranscriptionBackend(Protocol):
    name: str

    def transcribe(self, audio_path: str, model_size: str) -> TranscriptionResult:
        ...

    def device_label(self) -> str:
        ...


class OpenAIWhisperBackend:
    """Reference implementation (openai-whisper). Always available - the
    guaranteed fallback if no faster optional backend is installed."""

    name = "openai-whisper"

    def __init__(self) -> None:
        import whisper
        self._whisper = whisper

    def device_label(self) -> str:
        return get_device().type

    def transcribe(self, audio_path: str, model_size: str) -> TranscriptionResult:
        device = get_device()
        model = self._whisper.load_model(model_size, device=device)
        if device.type == "cuda":
            model = model.half()

        with torch.no_grad():
            # fp16 autocast is only reliable on CUDA; on MPS it produces
            # garbled/repeated output, and CPU doesn't support it at all.
            result = model.transcribe(audio_path, fp16=(device.type == "cuda"))

        segments = [
            Segment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
            for seg in result["segments"]
        ]
        return TranscriptionResult(segments=segments, language=result.get("language"))


def select_backend() -> TranscriptionBackend:
    """Pick the best available backend. Currently the only implementation;
    faster optional backends (mlx-whisper, faster-whisper) are added next."""
    return OpenAIWhisperBackend()
