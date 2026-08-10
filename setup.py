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


def _bundle_namespace_package(module_name: str, extra_native_dirs: tuple[str, ...] = ()) -> None:
    """PEP 420 namespace packages (no __init__.py) can't go through
    py2app's 'packages' option - its legacy imp-based
    collect_packagedirs can't find them at all. Bundle by walking the
    real directory and adding every subdirectory containing .py files as
    its own DATA_FILES entry, mirroring the source layout, plus any
    native .dylib/.metallib files a compiled extension needs at runtime
    (e.g. mlx/core.so's @rpath'd libmlx.dylib)."""
    spec = importlib.util.find_spec(module_name)
    if spec is None or not spec.submodule_search_locations:
        return
    pkg_dir = Path(list(spec.submodule_search_locations)[0])

    for native_subdir in extra_native_dirs:
        native_dir = pkg_dir / native_subdir
        native_files = [str(p) for p in native_dir.glob("*.dylib")] + [str(p) for p in native_dir.glob("*.metallib")]
        if native_files:
            DATA_FILES.append((f"lib/python{PY_VER}/lib-dynload/{module_name}/{native_subdir}", native_files))

    exclude_dirs = {"include", "share", "cmake", "__pycache__"}
    for dirpath, dirnames, filenames in os.walk(pkg_dir):
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        py_files = [str(Path(dirpath) / f) for f in filenames if f.endswith(".py") or f == "py.typed"]
        if py_files:
            rel = Path(dirpath).relative_to(pkg_dir)
            dest = f"lib/python{PY_VER}/{module_name}" if str(rel) == "." else f"lib/python{PY_VER}/{module_name}/{rel}"
            DATA_FILES.append((dest, py_files))


PACKAGES: list[str] = []
INCLUDES: list[str] = []

_site_packages = Path(sysconfig.get_paths()["purelib"])
for _entry in sorted(_site_packages.iterdir()):
    _name = _entry.name
    if _name.endswith((".dist-info", ".egg-info", ".pth")) or _name in _EXCLUDE_NAMES:
        continue
    if _entry.is_dir():
        if (_entry / "__init__.py").exists():
            PACKAGES.append(_name)
        elif any(_entry.glob("*.py")) or any(_entry.glob("**/*.so")):
            # mlx specifically ships a native lib/ dir its extension
            # dlopens via @rpath; other namespace packages found here
            # (e.g. tiktoken_ext, google) don't have that extra layer.
            _bundle_namespace_package(_name, extra_native_dirs=("lib",) if _name == "mlx" else ())
    elif _entry.suffix == ".py":
        INCLUDES.append(_entry.stem)
        # 'includes' alone isn't reliable for top-level single-file
        # modules that are only reachable (like typing_extensions,
        # transitively via torch) through another wholesale-bundled
        # package's untraced imports - copy it directly too.
        DATA_FILES.append((f"lib/python{PY_VER}", [str(_entry)]))

OPTIONS = {
    "argv_emulation": True,
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
