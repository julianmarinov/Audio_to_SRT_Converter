"""Orchestrates a transcription run. No GUI dependency - errors are reported
through callbacks so this stays independently testable."""
from __future__ import annotations

import shutil
import traceback
from typing import Callable, Optional

from backends import Segment, select_backend
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

            update_status("Transcribing...")
            result = backend.transcribe(input_path, model_type, on_progress=on_progress)

            if self.cancelled:
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
