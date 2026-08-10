"""Orchestrates a transcription run. No GUI dependency - errors are reported
through callbacks so this stays independently testable."""
from __future__ import annotations

import shutil
import traceback
from typing import Callable, Optional

from backends import select_backend
from subtitles import build_srt, write_text_file

StatusCallback = Callable[[str], None]
TextCallback = Callable[[str], None]
ErrorCallback = Callable[[str, str], None]  # (message, full_traceback)


class TranscriptionService:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel_transcription(self) -> None:
        self.cancelled = True

    def transcribe_audio_to_srt(
        self,
        audio_file_path: str,
        srt_file_path: str,
        model_type: str,
        update_status: StatusCallback,
        update_transcription_text: TextCallback,
        on_error: Optional[ErrorCallback] = None,
    ) -> None:
        self.cancelled = False
        try:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")

            backend = select_backend()
            update_status(f"Loading model on {backend.device_label()}...")
            update_status("Transcribing...")
            result = backend.transcribe(audio_file_path, model_type)

            if self.cancelled:
                update_status("Transcription cancelled.")
                return

            update_status("Formatting subtitles...")
            srt_content = build_srt(result.segments)
            write_text_file(srt_content, srt_file_path)

            full_text = "\n".join(seg.text for seg in result.segments)
            update_transcription_text(full_text)
            update_status("Subtitle file created successfully.")
        except Exception as e:
            tb = traceback.format_exc()
            update_status("Error during transcription.")
            if on_error:
                on_error(str(e), tb)
