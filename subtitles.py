"""Pure subtitle-formatting logic - no GUI or backend dependencies, easy to
unit test."""
from __future__ import annotations

import datetime
import os

from backends import Segment


def fmt_srt_time(seconds: float) -> str:
    td = datetime.timedelta(seconds=seconds)
    total = int(td.total_seconds())
    hrs, rem = divmod(total, 3600)
    mins, secs = divmod(rem, 60)
    ms = td.microseconds // 1000
    return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


def build_srt(segments: list[Segment]) -> str:
    parts = []
    for i, seg in enumerate(segments, start=1):
        start = fmt_srt_time(seg.start)
        end = fmt_srt_time(seg.end)
        parts.append(f"{i}\n{start} --> {end}\n{seg.text}\n\n")
    return "".join(parts)


def write_text_file(content: str, path: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
