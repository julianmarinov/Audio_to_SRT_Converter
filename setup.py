"""py2app build script - produces an unsigned, double-clickable .app.

    python setup.py py2app

ffmpeg is copied into the bundle (Contents/Resources/bin/ffmpeg) so the
packaged app doesn't require a Homebrew install; main.py detects the
bundle and prepends that dir to PATH at startup.

Unsigned: macOS Gatekeeper will block the first launch. Right-click the
app -> Open -> Open, once, to approve it (see Documentation/).

Dependency bundling strategy: rather than relying on py2app's default
static import-graph tracing (which repeatedly missed real dependencies
here - huggingface_hub, httpx, mlx, and others all use lazy/dynamic
imports or ship compiled extensions with @rpath'd .dylibs, none of which
modulegraph's AST scanner can see), every actual site-packages
distribution is bundled wholesale, except a small blocklist of
build/dev-only tooling that must not ship in the app (pytest, setuptools,
py2app itself, etc). This trades some bundle size for not having to
discover missing transitive dependencies one runtime ImportError at a
time.
"""
import importlib.util
import os
import shutil
import sys
import sysconfig
from pathlib import Path

from setuptools import setup

# modulegraph's AST-based import scanner is a recursive-descent visitor
# that can exceed Python's default recursion limit on very large generated
# files (e.g. yt-dlp's extractor list is one file with ~2000 imports).
sys.setrecursionlimit(10000)

APP = ["main.py"]
PY_VER = f"{sys.version_info.major}.{sys.version_info.minor}"

_ffmpeg_path = shutil.which("ffmpeg")
_ffprobe_path = shutil.which("ffprobe")
if not _ffmpeg_path or not _ffprobe_path:
    raise SystemExit("ffmpeg/ffprobe not found on PATH - install it first (brew install ffmpeg) before packaging.")
# Homebrew's ffmpeg/ffprobe reference their dylibs via
# @executable_path/../Frameworks, which only resolves correctly if the
# binary sits directly in Contents/Resources/ (one level up lands in
# Contents/, then into Frameworks/ - matching where py2app actually puts
# copied dylibs). A "bin" subfolder breaks that resolution and the
# binaries fail to launch at all (dyld: Library not loaded).
DATA_FILES: list[tuple[str, list[str]]] = [("", [_ffmpeg_path, _ffprobe_path])]

# Build/dev-only tooling that must not ship in the app, plus a couple of
# stray non-package entries seen in this venv's site-packages root.
_EXCLUDE_NAMES = {
    "_distutils_hack", "_pytest", "altgraph", "build", "iniconfig",
    "macholib", "modulegraph", "more_itertools", "pip", "pluggy",
    "py2app", "pytest", "setuptools", "torchgen",
    "isympy.py", "py.py", ".DS_Store",
}

_site_packages = Path(sysconfig.get_paths()["purelib"])

# mlx and tiktoken_ext ship as PEP 420 namespace packages (no __init__.py).
# That breaks py2app in two separate ways: its legacy imp-based
# collect_packagedirs can't find them at all if listed in 'packages'
# (crashes with "No module named ..."), and even bundled by hand, py2app's
# automatic tracing places a compiled extension (mlx/core.so) via a
# mechanism that never establishes a real, filesystem-searchable __path__
# for the rest of the package - a sibling pure-Python file
# (mlx/_reprlib_fix.py, imported internally by core.so) failed with
# ModuleNotFoundError even sitting right next to core.so in the same
# directory. Giving them a real (empty) __init__.py turns them into
# ordinary packages as far as ALL of py2app's tooling is concerned, so
# they go through the exact same wholesale-copy path that already works
# correctly for regular packages like torch - no special-casing needed.
for _ns_pkg in ("mlx", "tiktoken_ext"):
    _ns_spec = importlib.util.find_spec(_ns_pkg)
    if _ns_spec is not None and _ns_spec.submodule_search_locations:
        (Path(list(_ns_spec.submodule_search_locations)[0]) / "__init__.py").touch(exist_ok=True)

PACKAGES: list[str] = []
INCLUDES: list[str] = []

for _entry in sorted(_site_packages.iterdir()):
    _name = _entry.name
    if _name.endswith((".dist-info", ".egg-info", ".pth")) or _name in _EXCLUDE_NAMES:
        continue
    if _entry.is_dir():
        if (_entry / "__init__.py").exists():
            PACKAGES.append(_name)
        # else: a genuine namespace package we haven't needed to handle
        # yet - if one shows up, it'll surface as a runtime ImportError
        # same as mlx/tiktoken_ext did, with a clear traceback pointing
        # at exactly which name is missing.
    elif _entry.suffix == ".py":
        INCLUDES.append(_entry.stem)
        # 'includes' alone isn't reliable for top-level single-file
        # modules that are only reachable (like typing_extensions,
        # transitively via torch) through another wholesale-bundled
        # package's untraced imports - copy it directly too.
        DATA_FILES.append((f"lib/python{PY_VER}", [str(_entry)]))

OPTIONS = {
    # argv_emulation makes py2app hook AppKit's Open Documents/Open URLs
    # event handling to emulate argv - which fights with Tkinter's own
    # Cocoa menu-bar setup at startup (Tk_SetWindowMenubar creating an
    # NSMenuItem hits an assertion failure -> uncaught NSException ->
    # abort). Not needed here anyway since the app doesn't accept argv
    # (files are added via its own queue UI, not Finder drag-to-icon).
    "argv_emulation": False,
    "packages": PACKAGES,
    "includes": [
        "backends", "subtitles", "chunking", "transcription_service",
        "gui", "model_download", "remote_input",
    ] + INCLUDES,
    "plist": {
        "CFBundleName": "Audio to SRT Converter",
        "CFBundleShortVersionString": "1.0.0",
        "NSHighResolutionCapable": True,
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
