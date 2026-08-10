#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Must be set before any MPS op runs so unsupported ops silently fall back
# to CPU instead of crashing (relevant on Apple Silicon / MPS).
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")


def _prepend_bundled_ffmpeg_to_path() -> None:
    """When packaged as a .app via py2app, ffmpeg/ffprobe ship directly in
    Contents/Resources (not a "bin" subfolder - Homebrew's binaries
    reference their dylibs via @executable_path/../Frameworks, which only
    resolves to py2app's actual Contents/Frameworks/ from that exact
    location) so the app works without a Homebrew install. In a normal
    `python main.py` dev run, sys.frozen isn't set and this is a no-op -
    PATH is used as-is."""
    if not getattr(sys, "frozen", False):
        return
    bundled_resources = Path(sys.executable).resolve().parent.parent / "Resources"
    if bundled_resources.is_dir():
        os.environ["PATH"] = f"{bundled_resources}{os.pathsep}{os.environ.get('PATH', '')}"


_prepend_bundled_ffmpeg_to_path()

# ----------------------------------------------------------------------------
# Requirements:
#   pip install -r requirements.txt
#   ffmpeg must be on PATH (macOS: brew install ffmpeg | Windows: see ffmpeg.org)
#     - not needed when running the packaged .app, which bundles its own
#   tkinter (macOS: brew install python-tk, if not already bundled with Python)
#
# Runs on CUDA (NVIDIA GPU), MPS (Apple Silicon GPU), or CPU - whichever is
# available is selected automatically.
# ----------------------------------------------------------------------------

from gui import AudioToSRTConverter

if __name__ == "__main__":
    app = AudioToSRTConverter()
    app.mainloop()
