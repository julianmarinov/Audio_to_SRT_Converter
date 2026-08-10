"""Orchestrates transcription runs (single file or a batch/queue). No GUI
dependency - errors are reported through callbacks so this stays
independently testable."""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import tempfile
import traceback
from pathlib import Path
from typing import Callable, Optional

import chunking
import remote_input
from backends import LoadedModel, Segment, TranscriptionBackend, TranscriptionResult, select_backend
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


def _sanitize_filename(name: str) -> str:
    name = re.sub(r'[<>:"/\\|?*]', "_", name).strip()
    return name or "youtube_audio"


class TranscriptionService:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel_transcription(self) -> None:
        self.cancelled = True

    def transcribe(
        self,
        input_path: str,
        model_type: str,
        formats: set[str],
        update_status: StatusCallback,
        update_transcription_text: TextCallback,
        on_error: Optional[ErrorCallback] = None,
        chunk_minutes: float = chunking.DEFAULT_CHUNK_MINUTES,
        output_base_path: Optional[str] = None,
    ) -> None:
        """Transcribe a single file or URL. input_path may be a local path
        or a YouTube (or other yt-dlp supported) URL. output_base_path is
        auto-derived if not given: next to the source for local files, or
        into ~/Downloads named after the video's title for a URL."""
        self.cancelled = False
        model = self._load_model(model_type, update_status, on_error)
        if model is None:
            return
        self._process_file(
            model, input_path, model_type, formats,
            update_status, update_transcription_text, on_error, chunk_minutes, output_base_path,
        )

    def transcribe_batch(
        self,
        input_paths: list[str],
        model_type: str,
        formats: set[str],
        update_status: StatusCallback,
        update_transcription_text: TextCallback,
        on_error: Optional[ErrorCallback] = None,
        on_item_status: Optional[Callable[[str, str], None]] = None,  # (input_path, status)
        on_item_complete: Optional[Callable[[str], None]] = None,
        chunk_minutes: float = chunking.DEFAULT_CHUNK_MINUTES,
    ) -> None:
        """Transcribe a queue of files and/or URLs, writing each output
        next to its source file (or into ~/Downloads for a URL, named
        after the video's title). The model is loaded once and reused
        across all items. One item's failure doesn't stop the rest of
        the batch."""
        self.cancelled = False
        if not input_paths:
            return

        model = self._load_model(model_type, update_status, on_error)
        if model is None:
            return

        total = len(input_paths)
        for i, input_path in enumerate(input_paths, start=1):
            if self.cancelled:
                update_status("Batch cancelled.")
                return

            name = input_path if remote_input.is_url(input_path) else os.path.basename(input_path)
            update_status(f"Processing {i}/{total}: {name}")
            if on_item_status:
                item_status: StatusCallback = lambda msg, path=input_path: on_item_status(path, msg)
            else:
                item_status = lambda msg, i=i, name=name: update_status(f"[{i}/{total}] {name}: {msg}")

            self._process_file(
                model, input_path, model_type, formats,
                item_status, update_transcription_text, on_error, chunk_minutes,
            )
            if on_item_complete:
                on_item_complete(input_path)

        if not self.cancelled:
            update_status(f"Batch complete: {total} file(s) processed.")

    def _load_model(
        self, model_type: str, update_status: StatusCallback, on_error: Optional[ErrorCallback]
    ) -> Optional[LoadedModel]:
        try:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")

            backend: TranscriptionBackend = select_backend()
            update_status(f"Loading {backend.name} model on {backend.device_label()}...")

            def on_progress(percent: int, mb_done: float, mb_total: float) -> None:
                update_status(f"Downloading model... {percent}% ({mb_done:.0f}MB/{mb_total:.0f}MB)")

            try:
                return backend.load(model_type, on_progress=on_progress)
            except Exception as e:
                if _is_oom_error(e):
                    raise RuntimeError(
                        f"Ran out of memory loading the '{model_type}' model. "
                        "Try a smaller model size (e.g. 'medium' or 'small')."
                    ) from None
                raise
        except Exception as e:
            tb = traceback.format_exc()
            update_status("Error during transcription.")
            if on_error:
                on_error(str(e), tb)
            return None

    def _process_file(
        self,
        model: LoadedModel,
        input_path: str,
        model_type: str,
        formats: set[str],
        update_status: StatusCallback,
        update_transcription_text: TextCallback,
        on_error: Optional[ErrorCallback],
        chunk_minutes: float,
        output_base_path: Optional[str] = None,
    ) -> None:
        try:
            if not formats:
                raise ValueError("Select at least one output format.")

            with contextlib.ExitStack() as stack:
                actual_path = input_path
                resolved_output_base = output_base_path

                if remote_input.is_url(input_path):
                    update_status("Downloading audio from URL...")
                    tmp_dir = stack.enter_context(tempfile.TemporaryDirectory(prefix="audio_to_srt_yt_"))
                    actual_path, title = remote_input.download_audio(input_path, tmp_dir)
                    if resolved_output_base is None:
                        downloads_dir = Path.home() / "Downloads"
                        downloads_dir.mkdir(parents=True, exist_ok=True)
                        resolved_output_base = str(downloads_dir / _sanitize_filename(title))
                elif resolved_output_base is None:
                    resolved_output_base = os.path.splitext(input_path)[0]

                result = self._run_transcription(actual_path, model, model_type, update_status, chunk_minutes)
                if result is None:  # cancelled
                    update_status("Transcription cancelled.")
                    return

                update_status("Formatting subtitles...")
                for fmt in formats:
                    content = _FORMAT_BUILDERS[fmt](result.segments, result.language)
                    write_text_file(content, with_extension(resolved_output_base, fmt))

                full_text = "\n".join(seg.text for seg in result.segments)
                update_transcription_text(full_text)
                update_status("Subtitle file created successfully.")
        except Exception as e:
            tb = traceback.format_exc()
            update_status("Error during transcription.")
            if on_error:
                on_error(str(e), tb)

    def _run_transcription(
        self,
        input_path: str,
        model: LoadedModel,
        model_type: str,
        update_status: StatusCallback,
        chunk_minutes: float,
    ) -> Optional[TranscriptionResult]:
        duration = chunking.probe_duration_seconds(input_path)
        if not chunking.should_chunk(duration):
            update_status("Transcribing...")
            return self._transcribe_one(model, input_path, model_type)

        with tempfile.TemporaryDirectory(prefix="audio_to_srt_chunks_") as workdir:
            chunks = chunking.split_into_chunks(input_path, duration, workdir, chunk_minutes)
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
