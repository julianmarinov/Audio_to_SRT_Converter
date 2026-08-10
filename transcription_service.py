"""Orchestrates a transcription run. No GUI dependency - errors are reported
through callbacks so this stays independently testable."""
from __future__ import annotations

import shutil
import tempfile
import traceback
from typing import Callable, Optional

import chunking
from backends import LoadedModel, Segment, TranscriptionResult, select_backend
from subtitles import build_json, build_srt, build_txt, build_vtt, with_extension, write_text_file

StatusCallback = Callable[[str], None]
TextCallback = Callable[[str], None]
ErrorCallback = Callable[[str, str], None]  # (message, full_traceback)

_FORMAT_BUILDERS: dict[str, Callable[[list[Segment], Optional[str]], str]] = {
    "srt": lambda segments, language: build_srt(segments),
    "vtt": lambda segments, language: build_vtt(segments),
    "txt": lambda segments, language: build_txt(segments),
    "json": build_json,
}

AUDIO_VIDEO_EXTENSIONS = ("*.mp3", "*.wav", "*.m4a", "*.mp4", "*.mov")


def _is_oom_error(exc: Exception) -> bool:
    if exc.__class__.__name__ in ("OutOfMemoryError", "MemoryError"):
        return True
    text = str(exc).lower()
    return "out of memory" in text or " oom" in text


class TranscriptionService:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel_transcription(self) -> None:
        self.cancelled = True

    def transcribe(
        self,
        input_path: str,
        output_base_path: str,
        model_type: str,
        formats: set[str],
        update_status: StatusCallback,
        update_transcription_text: TextCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.cancelled = False
        try:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")
            if not formats:
                raise ValueError("Select at least one output format.")

            backend = select_backend()
            update_status(f"Loading {backend.name} model on {backend.device_label()}...")

            def on_progress(percent: int, mb_done: float, mb_total: float) -> None:
                update_status(f"Downloading model... {percent}% ({mb_done:.0f}MB/{mb_total:.0f}MB)")

            try:
                model = backend.load(model_type, on_progress=on_progress)
            except Exception as e:
                if _is_oom_error(e):
                    raise RuntimeError(
                        f"Ran out of memory loading the '{model_type}' model. "
                        "Try a smaller model size (e.g. 'medium' or 'small')."
                    ) from None
                raise

            result = self._run_transcription(input_path, model, model_type, update_status)
            if result is None:  # cancelled
                update_status("Transcription cancelled.")
                return

            update_status("Formatting subtitles...")
            for fmt in formats:
                content = _FORMAT_BUILDERS[fmt](result.segments, result.language)
                write_text_file(content, with_extension(output_base_path, fmt))

            full_text = "\n".join(seg.text for seg in result.segments)
            update_transcription_text(full_text)
            update_status("Subtitle file created successfully.")
        except Exception as e:
            tb = traceback.format_exc()
            update_status("Error during transcription.")
            if on_error:
                on_error(str(e), tb)

    def _run_transcription(
        self, input_path: str, model: LoadedModel, model_type: str, update_status: StatusCallback
    ) -> Optional[TranscriptionResult]:
        duration = chunking.probe_duration_seconds(input_path)
        if not chunking.should_chunk(duration):
            update_status("Transcribing...")
            return self._transcribe_one(model, input_path, model_type)

        with tempfile.TemporaryDirectory(prefix="audio_to_srt_chunks_") as workdir:
            chunks = chunking.split_into_chunks(input_path, duration, workdir)
            chunk_results = []
            for i, chunk in enumerate(chunks, start=1):
                if self.cancelled:
                    return None
                update_status(f"Transcribing chunk {i}/{len(chunks)}...")
                result = self._transcribe_one(model, chunk.path, model_type)
                chunk_results.append((chunk, result))
            return chunking.merge_results(chunk_results)

    @staticmethod
    def _transcribe_one(model: LoadedModel, audio_path: str, model_type: str) -> TranscriptionResult:
        try:
            return model.transcribe(audio_path)
        except Exception as e:
            if _is_oom_error(e):
                raise RuntimeError(
                    f"Ran out of memory while transcribing with the '{model_type}' model. "
                    "Try a smaller model size (e.g. 'medium' or 'small')."
                ) from None
            raise
