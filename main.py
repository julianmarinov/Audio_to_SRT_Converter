#!/usr/bin/env python3
import os

# Must be set before any MPS op runs so unsupported ops silently fall back
# to CPU instead of crashing (relevant on Apple Silicon / MPS).
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

# ----------------------------------------------------------------------------
# Requirements:
#   pip install -r requirements.txt
#   ffmpeg must be on PATH (macOS: brew install ffmpeg | Windows: see ffmpeg.org)
#   tkinter (macOS: brew install python-tk, if not already bundled with Python)
#
# Runs on CUDA (NVIDIA GPU), MPS (Apple Silicon GPU), or CPU - whichever is
# available is selected automatically.
# ----------------------------------------------------------------------------

from gui import AudioToSRTConverter

if __name__ == "__main__":
    app = AudioToSRTConverter()
    app.mainloop()
