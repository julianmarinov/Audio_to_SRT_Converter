"""Pure subtitle-formatting logic - no GUI or backend dependencies, easy to
unit test."""
from __future__ import annotations

import datetime
import json
import os
import textwrap

from backends import Segment

# Standard subtitle readability convention (~42 chars/line).
DEFAULT_LINE_WIDTH = 42


def fmt_srt_time(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total = int(td.total_seconds())
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    ms = td.microseconds // 1000
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


def fmt_vtt_time(seconds: float) -> str:
    return fmt_srt_time(seconds).replace(",", ".")


def wrap_subtitle_text(text: str, max_chars: int = DEFAULT_LINE_WIDTH) -> str:
    text = text.strip()
    if not text:
        return text
    return "\n".join(textwrap.wrap(text, width=max_chars, break_long_words=False))


def build_srt(segments: list[Segment]) -> str:
    parts = []
    for i, seg in enumerate(segments, start=1):
        start = fmt_srt_time(seg.start)
        end = fmt_srt_time(seg.end)
        parts.append(f"{i}\n{start} --> {end}\n{wrap_subtitle_text(seg.text)}\n\n")
    return "".join(parts)


def build_vtt(segments: list[Segment]) -> str:
    parts = ["WEBVTT\n\n"]
    for i, seg in enumerate(segments, start=1):
        start = fmt_vtt_time(seg.start)
        end = fmt_vtt_time(seg.end)
        parts.append(f"{i}\n{start} --> {end}\n{wrap_subtitle_text(seg.text)}\n\n")
    return "".join(parts)


def build_txt(segments: list[Segment]) -> str:
    """Plain transcript, no timestamps."""
    return "\n".join(seg.text.strip() for seg in segments) + "\n"


def build_json(segments: list[Segment], language: str | None) -> str:
    payload = {
        "language": language,
        "segments": [
            {"start": seg.start, "end": seg.end, "text": seg.text.strip()}
            for seg in segments
        ],
    }
    return json.dumps(payload, indent=2, ensure_ascii=False)


def with_extension(path: str, ext: str) -> str:
    base, _ = os.path.splitext(path)
    return f"{base}.{ext}"


def write_text_file(content: str, path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
