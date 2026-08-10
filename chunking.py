"""Splits long audio/video files into fixed-length pieces so very long
recordings (1-2hrs) transcribe with a bounded per-chunk decode buffer and
give incremental progress, then stitches the per-chunk results back into
one continuous timeline by offsetting timestamps.

No cross-chunk overlap/dedup - a word split exactly on a chunk boundary is
a rare, minor cosmetic issue, not worth the added complexity here.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from backends import Segment, TranscriptionResult

DEFAULT_THRESHOLD_MINUTES = 20.0
DEFAULT_CHUNK_MINUTES = 15.0


def probe_duration_seconds(path: str) -> float:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
        capture_output=True, text=True, check=True,
    )
    data = json.loads(proc.stdout)
    return float(data["format"]["duration"])


def should_chunk(duration_seconds: float, threshold_minutes: float = DEFAULT_THRESHOLD_MINUTES) -> bool:
    return duration_seconds > threshold_minutes * 60


@dataclass
class Chunk:
    path: str
    start_offset: float


def split_into_chunks(
    input_path: str,
    duration_seconds: float,
    workdir: str,
    chunk_minutes: float = DEFAULT_CHUNK_MINUTES,
) -> list[Chunk]:
    chunk_seconds = chunk_minutes * 60
    chunks: list[Chunk] = []
    start = 0.0
    index = 0
    while start < duration_seconds:
        length = min(chunk_seconds, duration_seconds - start)
        out_path = str(Path(workdir) / f"chunk_{index:03}.wav")
        subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(start), "-t", str(length), "-i", input_path,
                "-ac", "1", "-ar", "16000", out_path,
            ],
            capture_output=True, text=True, check=True,
        )
        chunks.append(Chunk(path=out_path, start_offset=start))
        start += chunk_seconds
        index += 1
    return chunks


def merge_results(chunk_results: list[tuple[Chunk, TranscriptionResult]]) -> TranscriptionResult:
    segments: list[Segment] = []
    language: Optional[str] = None
    for chunk, result in chunk_results:
        if language is None:
            language = result.language
        for seg in result.segments:
            segments.append(Segment(
                start=seg.start + chunk.start_offset,
                end=seg.end + chunk.start_offset,
                text=seg.text,
            ))
    return TranscriptionResult(segments=segments, language=language)
