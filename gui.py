"""Tkinter GUI. Business logic lives in transcription_service.py."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, simpledialog, ttk

import chunking
import remote_input
from backends import select_backend
from transcription_service import AUDIO_VIDEO_EXTENSIONS, TranscriptionService

_AUDIO_VIDEO_SUFFIXES = {ext.replace("*", "") for ext in AUDIO_VIDEO_EXTENSIONS}


class AudioToSRTConverter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio to SRT Converter")
        self.geometry("820x680")
        self.transcriber = TranscriptionService()
        self._queue_rows: dict[str, str] = {}  # input_path -> Treeview item id
        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Model selector
        ttk.Label(frm, text="Model:").grid(row=0, column=0, sticky="e")
        self.model_var = tk.StringVar(value="large")
        model_combo = ttk.Combobox(frm, textvariable=self.model_var,
                                    values=["tiny", "base", "small", "medium", "large"],
                                    state="readonly", width=12)
        model_combo.grid(row=0, column=1, sticky="w", padx=5)
        model_combo.current(4)

        # --- Output formats
        ttk.Label(frm, text="Formats:").grid(row=0, column=2, sticky="e")
        fmt_frm = ttk.Frame(frm)
        fmt_frm.grid(row=0, column=3, sticky="w")
        self.format_vars = {
            "srt": tk.BooleanVar(value=True),
            "vtt": tk.BooleanVar(value=False),
            "txt": tk.BooleanVar(value=False),
            "json": tk.BooleanVar(value=False),
        }
        for fmt, var in self.format_vars.items():
            ttk.Checkbutton(fmt_frm, text=f".{fmt}", variable=var).pack(side="left", padx=(0, 8))

        # --- Chunk length (for auto-splitting long files)
        ttk.Label(frm, text="Chunk size (min):").grid(row=1, column=0, sticky="e", pady=(5, 0))
        self.chunk_minutes_var = tk.IntVar(value=int(chunking.DEFAULT_CHUNK_MINUTES))
        ttk.Spinbox(frm, from_=5, to=60, textvariable=self.chunk_minutes_var, width=5).grid(
            row=1, column=1, sticky="w", padx=5, pady=(5, 0))

        # --- Queue
        queue_frm = ttk.Frame(frm)
        queue_frm.grid(row=2, column=0, columnspan=4, sticky="nsew", pady=(10, 0))
        frm.rowconfigure(2, weight=1)
        for c in range(4):
            frm.columnconfigure(c, weight=1)

        self.queue_tree = ttk.Treeview(queue_frm, columns=("status",), show="tree headings", height=8)
        self.queue_tree.heading("#0", text="File")
        self.queue_tree.heading("status", text="Status")
        self.queue_tree.column("#0", width=420)
        self.queue_tree.column("status", width=260)
        scrollbar = ttk.Scrollbar(queue_frm, orient="vertical", command=self.queue_tree.yview)
        self.queue_tree.configure(yscrollcommand=scrollbar.set)
        self.queue_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        queue_btn_frm = ttk.Frame(frm)
        queue_btn_frm.grid(row=3, column=0, columnspan=4, sticky="ew", pady=5)
        ttk.Button(queue_btn_frm, text="Add Files...", command=self._add_files).pack(side="left", padx=(0, 5))
        ttk.Button(queue_btn_frm, text="Add Folder...", command=self._add_folder).pack(side="left", padx=(0, 5))
        ttk.Button(queue_btn_frm, text="Add YouTube URL...", command=self._add_url).pack(side="left", padx=(0, 5))
        ttk.Button(queue_btn_frm, text="Remove Selected", command=self._remove_selected).pack(side="left", padx=(0, 5))
        ttk.Button(queue_btn_frm, text="Clear Queue", command=self._clear_queue).pack(side="left")

        # --- Buttons
        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=4, column=0, columnspan=4, pady=10)
        self.go_btn = ttk.Button(btn_frm, text="Transcribe Queue", command=self._on_transcribe)
        self.go_btn.pack(side="left", padx=5)
        ttk.Button(btn_frm, text="Cancel", command=self._on_cancel).pack(side="left")

        # --- Status + spinner
        self.status_lbl = ttk.Label(frm, text="Ready")
        self.status_lbl.grid(row=5, column=0, columnspan=4, sticky="w")
        self.spinner = ttk.Progressbar(frm, mode="indeterminate")
        self.spinner.grid(row=6, column=0, columnspan=4, sticky="ew", pady=5)

        ttk.Button(frm, text="Help", command=self._open_help_window).grid(
            row=7, column=0, columnspan=4, pady=(5, 0), sticky="ew")

        # --- Transcribed text (last completed file)
        self.txt = scrolledtext.ScrolledText(self, height=12, state="disabled")
        self.txt.pack(fill="both", expand=True, padx=10, pady=10)

    def _open_help_window(self) -> None:
        help_window = tk.Toplevel(self)
        help_window.title("Help Information")
        help_window.geometry("650x280")

        try:
            backend = select_backend()
            device = backend.device_label()
        except Exception as e:
            # Show the failure instead of leaving the window blank -
            # backend selection can fail (e.g. a broken optional install).
            ttk.Label(
                help_window,
                text=f"Could not determine the active backend:\n\n{e}",
                justify=tk.LEFT, foreground="red",
            ).pack(padx=10, pady=10)
            return

        help_text = f"""
What this script does?
Add one or more audio/video files (or a whole folder, or a YouTube URL) to the queue,
pick a model and output format(s), and click "Transcribe Queue". Each file's subtitles
are written next to the source file; a YouTube URL's audio is downloaded locally first
(one-time network fetch) and its subtitles are saved to ~/Downloads, named after the
video's title - transcription itself always runs entirely on-device.

Which model to choose?
"Tiny" is the fastest model but least accurate, while "Large" is the slowest, but almost 100% accurate.

Selected backend: {backend.name}
Detected compute device: {device}
{"(NVIDIA GPU acceleration)" if "cuda" in device else "(Apple Silicon GPU acceleration)" if "mps" in device else "(CPU only - this will be significantly slower, especially for larger models)"}

Long files (over 20 minutes) are automatically split into chunks (size configurable above)
so memory usage stays bounded and progress updates incrementally.

- Supported input formats: MP3, WAV, M4A (audio), MP4, MOV (video - audio track is extracted automatically)
- Recommended maximum file size: 500MB per file
"""
        ttk.Label(help_window, text=help_text, justify=tk.LEFT).pack(padx=10, pady=10)

    def _add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="Select Audio or Video Files",
            filetypes=[("Audio/Video", " ".join(AUDIO_VIDEO_EXTENSIONS)), ("All files", "*.*")]
        )
        for p in paths:
            self._add_to_queue(p)

    def _add_folder(self) -> None:
        folder = filedialog.askdirectory(title="Select Folder")
        if not folder:
            return
        for path in sorted(Path(folder).rglob("*")):
            if path.is_file() and path.suffix.lower() in _AUDIO_VIDEO_SUFFIXES:
                self._add_to_queue(str(path))

    def _add_url(self) -> None:
        url = simpledialog.askstring("Add YouTube URL", "Enter a video URL:", parent=self)
        if not url:
            return
        url = url.strip()
        if not remote_input.is_url(url):
            messagebox.showerror("Invalid URL", "That doesn't look like a valid http(s) URL.")
            return
        self._add_to_queue(url)

    def _add_to_queue(self, path: str) -> None:
        if path in self._queue_rows:
            return
        display = path if remote_input.is_url(path) else os.path.basename(path)
        iid = self.queue_tree.insert("", "end", text=display, values=("Queued",))
        self._queue_rows[path] = iid

    def _remove_selected(self) -> None:
        for iid in self.queue_tree.selection():
            path = next((p for p, row_iid in self._queue_rows.items() if row_iid == iid), None)
            if path:
                del self._queue_rows[path]
            self.queue_tree.delete(iid)

    def _clear_queue(self) -> None:
        self.queue_tree.delete(*self.queue_tree.get_children())
        self._queue_rows.clear()

    def _on_transcribe(self) -> None:
        input_paths = list(self._queue_rows.keys())
        if not input_paths:
            messagebox.showwarning("Empty queue", "Add at least one audio or video file to the queue.")
            return

        formats = {fmt for fmt, var in self.format_vars.items() if var.get()}
        if not formats:
            messagebox.showwarning("No format selected", "Please select at least one output format.")
            return

        model = self.model_var.get()
        chunk_minutes = self.chunk_minutes_var.get()

        for path in input_paths:
            self._set_row_status(path, "Queued")

        self.go_btn.config(state="disabled")
        self.spinner.start(10)

        status_cb = lambda msg: self.after(0, self._update_status, msg)
        text_cb = lambda txt: self.after(0, self._update_text, txt)
        error_cb = lambda msg, tb: self.after(0, self._show_error, msg, tb)
        item_status_cb = lambda path, msg: self.after(0, self._set_row_status, path, msg)
        item_complete_cb = lambda path: self.after(0, self._set_row_status, path, "Done")

        t = threading.Thread(
            target=self.transcriber.transcribe_batch,
            args=(input_paths, model, formats, status_cb, text_cb, error_cb, item_status_cb, item_complete_cb, chunk_minutes),
            daemon=True
        )
        t.start()

    def _set_row_status(self, path: str, status: str) -> None:
        iid = self._queue_rows.get(path)
        if iid and self.queue_tree.exists(iid):
            self.queue_tree.set(iid, "status", status)

    def _on_cancel(self) -> None:
        self.transcriber.cancel_transcription()
        self.after(0, self._update_status, "Cancelling...")

    def _update_status(self, msg: str) -> None:
        self.status_lbl.config(text=msg)
        if msg.startswith("Batch complete") or msg.startswith("Batch cancelled") or msg.startswith("Error"):
            self.spinner.stop()
            self.go_btn.config(state="normal")

    def _update_text(self, txt: str) -> None:
        self.txt.config(state="normal")
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, txt)
        self.txt.config(state="disabled")

    def _show_error(self, msg: str, tb: str) -> None:
        messagebox.showerror("Transcription Error", f"{msg}\n\n{tb}")
