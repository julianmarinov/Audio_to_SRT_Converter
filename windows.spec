# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Windows builds.

    pyinstaller windows.spec

ffmpeg.exe and ffprobe.exe must sit next to this spec file before running
(the CI workflow downloads them there) - main.py's bundled-ffmpeg PATH
logic expects them alongside the built .exe.

Several third-party packages need explicit collect_all treatment here
because their imports aren't fully visible to PyInstaller's static
analysis - the same category of problem (lazy imports, namespace/plugin
packages) that required manual bundling on the macOS py2app build, which
took many iterations against real ImportErrors to get right:
  - huggingface_hub: most of its public API is loaded via a lazy
    __getattr__, invisible to static import tracing.
  - tiktoken_ext: a namespace package that tiktoken's registry imports by
    name at runtime, not via a static import.
  - yt_dlp: its ~2000 site extractors are registered dynamically.
This has NOT been verified against a real Windows build (no Windows
environment was available while writing this) - if the GitHub Actions
build fails, the error will point at whatever this list missed.
"""
import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

_COLLECT_ALL = [
    "huggingface_hub", "tiktoken", "tiktoken_ext", "yt_dlp",
    "whisper", "faster_whisper", "ctranslate2",
]

datas = []
binaries = []
hiddenimports = []
for _pkg in _COLLECT_ALL:
    _d, _b, _h = collect_all(_pkg)
    datas += _d
    binaries += _b
    hiddenimports += _h

_here = Path(os.path.dirname(os.path.abspath(SPEC)))
for _exe_name in ("ffmpeg.exe", "ffprobe.exe"):
    _exe_path = _here / _exe_name
    if _exe_path.exists():
        binaries.append((str(_exe_path), "."))

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Local Transcription & Subtitle Creator",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Local Transcription & Subtitle Creator",
)
