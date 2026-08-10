"""Resolves a YouTube (or other yt-dlp supported) URL to a local audio
file, so the rest of the app can treat it exactly like any local file."""
from __future__ import annotations

import glob
import os


def is_url(source: str) -> bool:
    return source.strip().lower().startswith(("http://", "https://"))


def download_audio(url: str, output_dir: str) -> tuple[str, str]:
    """Downloads and extracts audio to output_dir. Returns (local_path, title)."""
    import yt_dlp

    outtmpl = os.path.join(output_dir, "audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "wav"}],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)

    matches = glob.glob(os.path.join(output_dir, "audio.*"))
    if not matches:
        raise RuntimeError(f"Failed to download audio from {url}")
    return matches[0], info.get("title", "youtube_audio")
