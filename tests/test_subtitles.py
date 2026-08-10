import json
import os

from backends import Segment
from subtitles import (
    build_json,
    build_srt,
    build_txt,
    build_vtt,
    fmt_srt_time,
    fmt_vtt_time,
    with_extension,
    wrap_subtitle_text,
    write_text_file,
)


def test_fmt_srt_time_basic():
    assert fmt_srt_time(0) == "00:00:00,000"
    assert fmt_srt_time(65.25) == "00:01:05,250"
    assert fmt_srt_time(3661.001) == "01:01:01,001"


def test_fmt_vtt_time_uses_dot_separator():
    assert fmt_vtt_time(65.25) == "00:01:05.250"


def test_wrap_subtitle_text_short_text_unchanged():
    assert wrap_subtitle_text("short line") == "short line"


def test_wrap_subtitle_text_wraps_long_text():
    text = "This is a longer sentence that should exceed the default forty two character line width easily"
    wrapped = wrap_subtitle_text(text)
    lines = wrapped.split("\n")
    assert len(lines) > 1
    assert all(len(line) <= 42 for line in lines)
    assert " ".join(lines) == text  # no words dropped


def test_wrap_subtitle_text_empty():
    assert wrap_subtitle_text("   ") == ""


def test_build_srt_numbering_and_timestamps():
    segments = [
        Segment(start=0.0, end=1.5, text="Hello"),
        Segment(start=1.5, end=3.0, text="World"),
    ]
    srt = build_srt(segments)
    assert "1\n00:00:00,000 --> 00:00:01,500\nHello\n\n" in srt
    assert "2\n00:00:01,500 --> 00:00:03,000\nWorld\n\n" in srt


def test_build_vtt_has_header_and_dot_timestamps():
    segments = [Segment(start=0.0, end=1.0, text="Hi")]
    vtt = build_vtt(segments)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:01.000" in vtt


def test_build_txt_has_no_timestamps():
    segments = [Segment(start=0.0, end=1.0, text="Hello"), Segment(start=1.0, end=2.0, text="World")]
    txt = build_txt(segments)
    assert "-->" not in txt
    assert txt == "Hello\nWorld\n"


def test_build_json_structure():
    segments = [Segment(start=0.0, end=1.0, text="Hello")]
    payload = json.loads(build_json(segments, "en"))
    assert payload["language"] == "en"
    assert payload["segments"] == [{"start": 0.0, "end": 1.0, "text": "Hello"}]


def test_with_extension_replaces_suffix():
    assert with_extension("/a/b/output.srt", "vtt") == "/a/b/output.vtt"
    assert with_extension("/a/b/output", "json") == "/a/b/output.json"


def test_write_text_file_creates_parent_dirs(tmp_path):
    target = tmp_path / "nested" / "dir" / "out.txt"
    write_text_file("hello", str(target))
    assert target.read_text(encoding="utf-8") == "hello"
    assert os.path.isdir(str(tmp_path / "nested" / "dir"))
