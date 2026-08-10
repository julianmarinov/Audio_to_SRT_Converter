"""Transcription backend abstraction.

Each backend wraps a different Whisper implementation behind a common
interface so the rest of the app doesn't need to know which one is in use.
select_backend() auto-picks the fastest one actually installed:

  1. mlx-whisper   - Apple Silicon only, native Metal GPU. Fastest on Mac.
  2. faster-whisper - CTranslate2. No MPS support (CPU-only on Mac), but
                       faster than openai-whisper on CUDA and CPU.
  3. openai-whisper - reference implementation, always available (required
                       dependency) - the guaranteed fallback.

Loading and transcribing are separate steps (backend.load() -> a
LoadedModel with its own .transcribe()) so a caller processing multiple
chunks of one file only pays the model-load cost once.
"""
from __future__ import annotations

import importlib.util
import platform
from dataclasses import dataclass
from typing import Optional, Protocol

import torch

from model_download import DownloadProgressWatcher, ProgressCallback


def get_device() -> torch.device:
    """Best available compute device: CUDA > Apple Silicon MPS > CPU."""
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_built() and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _is_apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def _importable(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    segments: list[Segment]
    language: Optional[str] = None


class LoadedModel(Protocol):
    def transcribe(self, audio_path: str) -> TranscriptionResult:
        ...


class TranscriptionBackend(Protocol):
    name: str

    def load(self, model_size: str, on_progress: Optional[ProgressCallback] = None) -> LoadedModel:
        ...

    def device_label(self) -> str:
        ...


class _OpenAIWhisperLoadedModel:
    def __init__(self, model, device: torch.device) -> None:
        self._model = model
        self._device = device

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        with torch.no_grad():
            # fp16 autocast is only reliable on CUDA; on MPS it produces
            # garbled/repeated output, and CPU doesn't support it at all.
            result = self._model.transcribe(audio_path, fp16=(self._device.type == "cuda"))
        segments = [
            Segment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
            for seg in result["segments"]
        ]
        return TranscriptionResult(segments=segments, language=result.get("language"))


class OpenAIWhisperBackend:
    """Reference implementation (openai-whisper). Always available - the
    guaranteed fallback if no faster optional backend is installed."""

    name = "openai-whisper"

    def __init__(self) -> None:
        import whisper
        self._whisper = whisper

    def device_label(self) -> str:
        return get_device().type

    def load(self, model_size: str, on_progress: Optional[ProgressCallback] = None) -> _OpenAIWhisperLoadedModel:
        device = get_device()
        with DownloadProgressWatcher(model_size, on_progress):
            model = self._whisper.load_model(model_size, device=device)
        if device.type == "cuda":
            model = model.half()
        return _OpenAIWhisperLoadedModel(model, device)


class _FasterWhisperLoadedModel:
    def __init__(self, model) -> None:
        self._model = model

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        segments_gen, info = self._model.transcribe(audio_path)
        segments = [
            Segment(start=seg.start, end=seg.end, text=seg.text.strip())
            for seg in segments_gen
        ]
        return TranscriptionResult(segments=segments, language=info.language)


class FasterWhisperBackend:
    """CTranslate2-based backend. No MPS support - CUDA or CPU only."""

    name = "faster-whisper"

    def __init__(self) -> None:
        from faster_whisper import WhisperModel
        self._WhisperModel = WhisperModel
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._compute_type = "float16" if self._device == "cuda" else "int8"

    def device_label(self) -> str:
        return self._device

    def load(self, model_size: str, on_progress: Optional[ProgressCallback] = None) -> _FasterWhisperLoadedModel:
        with DownloadProgressWatcher(model_size, on_progress):
            model = self._WhisperModel(model_size, device=self._device, compute_type=self._compute_type)
        return _FasterWhisperLoadedModel(model)


class _MLXWhisperLoadedModel:
    """mlx_whisper.transcribe() loads (and downloads, if needed) the model
    internally on every call - there's no separate load step to hook. The
    download watcher is therefore attached only to the first transcribe()
    call; later calls (e.g. subsequent chunks) reuse the already-downloaded
    local cache so there's nothing left to watch."""

    def __init__(self, mlx_whisper_module, repo: str, model_size: str, on_progress: Optional[ProgressCallback]) -> None:
        self._mlx_whisper = mlx_whisper_module
        self._repo = repo
        self._model_size = model_size
        self._pending_progress = on_progress

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        progress = self._pending_progress
        self._pending_progress = None
        with DownloadProgressWatcher(self._model_size, progress):
            result = self._mlx_whisper.transcribe(audio_path, path_or_hf_repo=self._repo)
        segments = [
            Segment(start=seg["start"], end=seg["end"], text=seg["text"].strip())
            for seg in result["segments"]
        ]
        return TranscriptionResult(segments=segments, language=result.get("language"))


class MLXWhisperBackend:
    """Apple's MLX framework - native Metal GPU execution. The fastest
    option on Apple Silicon."""

    name = "mlx-whisper"

    _MODEL_REPOS = {
        "tiny": "mlx-community/whisper-tiny-mlx",
        "base": "mlx-community/whisper-base-mlx",
        "small": "mlx-community/whisper-small-mlx",
        "medium": "mlx-community/whisper-medium-mlx",
        "large": "mlx-community/whisper-large-v3-mlx",
    }

    def __init__(self) -> None:
        import mlx_whisper
        self._mlx_whisper = mlx_whisper

    def device_label(self) -> str:
        return "mps (mlx)"

    def load(self, model_size: str, on_progress: Optional[ProgressCallback] = None) -> _MLXWhisperLoadedModel:
        repo = self._MODEL_REPOS.get(model_size, self._MODEL_REPOS["small"])
        return _MLXWhisperLoadedModel(self._mlx_whisper, repo, model_size, on_progress)


def select_backend() -> TranscriptionBackend:
    if _is_apple_silicon() and _importable("mlx_whisper"):
        return MLXWhisperBackend()
    if _importable("faster_whisper"):
        return FasterWhisperBackend()
    return OpenAIWhisperBackend()
