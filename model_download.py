"""Backend-agnostic model-download progress.

None of the three backends expose a uniform, version-stable hook into their
internal downloaders (urllib+tqdm, HuggingFace Hub, ...), so instead of
hooking each one individually this watches the known model-cache
directories for byte growth while a model load is in flight and reports an
approximate percentage. Already-cached models produce no growth, so no
progress events fire for them.
"""
from __future__ import annotations

import os
import threading
import time
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Callable[[int, float, float], None]  # (percent, mb_done, mb_total)

# Rough sizes in MB for the fp16 model weights, used only to compute an
# approximate percentage - doesn't need to be exact.
_APPROX_SIZE_MB = {
    "tiny": 75,
    "base": 145,
    "small": 484,
    "medium": 1500,
    "large": 3100,
}

_WATCH_DIRS = [
    Path.home() / ".cache" / "whisper",
    Path.home() / ".cache" / "huggingface" / "hub",
]

# Below this, what we're seeing is small metadata/lock files HF Hub
# touches on every load (even cache hits), not an actual model download.
_NOISE_FLOOR_BYTES = 1024 * 1024


def _bytes_written_since(dirs: list[Path], since_ts: float) -> int:
    total = 0
    for base in dirs:
        if not base.exists():
            continue
        for root, _, files in os.walk(base):
            for name in files:
                path = Path(root) / name
                try:
                    st = path.stat()
                except OSError:
                    continue
                if st.st_mtime >= since_ts:
                    total += st.st_size
    return total


class DownloadProgressWatcher:
    """Context manager: polls the model-cache dirs for growth on a
    background thread and calls on_progress(percent, mb_done, mb_total)
    while inside the `with` block."""

    def __init__(self, model_size: str, on_progress: Optional[ProgressCallback], poll_interval: float = 0.5) -> None:
        base_size = _APPROX_SIZE_MB.get(model_size.split("-")[0].replace(".en", ""), 1000)
        self._expected_bytes = base_size * 1024 * 1024
        self._on_progress = on_progress
        self._poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        # small lookback window so files that started writing just before
        # the watcher started are still counted
        self._since_ts = time.time() - 5

    def __enter__(self) -> "DownloadProgressWatcher":
        if self._on_progress is not None:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        return self

    def __exit__(self, *exc_info) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1)

    def _run(self) -> None:
        assert self._on_progress is not None
        while not self._stop.is_set():
            downloaded = _bytes_written_since(_WATCH_DIRS, self._since_ts)
            if downloaded > _NOISE_FLOOR_BYTES:
                percent = min(100, int(downloaded / self._expected_bytes * 100))
                self._on_progress(percent, downloaded / (1024 * 1024), self._expected_bytes / (1024 * 1024))
            self._stop.wait(self._poll_interval)
