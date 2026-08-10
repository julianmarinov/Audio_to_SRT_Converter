"""Tkinter GUI. Business logic lives in transcription_service.py."""
from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from backends import select_backend
from transcription_service import TranscriptionService


class AudioToSRTConverter(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Audio to SRT Converter")
        self.geometry("800x600")
        self.transcriber = TranscriptionService()
        self._build_ui()

    def _build_ui(self) -> None:
        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        # --- Audio file
        ttk.Label(frm, text="Audio File:").grid(row=0, column=0, sticky="e")
        self.audio_entry = ttk.Entry(frm, width=50)
        self.audio_entry.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Button(frm, text="Browse...", command=self._browse_audio).grid(row=0, column=2)

        # --- SRT output
        ttk.Label(frm, text="Save SRT As:").grid(row=1, column=0, sticky="e")
        self.srt_entry = ttk.Entry(frm, width=50)
        self.srt_entry.grid(row=1, column=1, sticky="ew", padx=5)
        ttk.Button(frm, text="Save As...", command=self._save_srt).grid(row=1, column=2)

        # --- Model selector
        ttk.Label(frm, text="Model:").grid(row=2, column=0, sticky="e")
        self.model_var = tk.StringVar(value="large")
        combo = ttk.Combobox(frm, textvariable=self.model_var,
                              values=["tiny", "base", "small", "medium", "large"],
                              state="readonly")
        combo.grid(row=2, column=1, sticky="w", padx=5)
        combo.current(4)

        # --- Buttons
        btn_frm = ttk.Frame(frm)
        btn_frm.grid(row=3, column=1, pady=10)
        self.go_btn = ttk.Button(btn_frm, text="Transcribe", command=self._on_transcribe)
        self.go_btn.pack(side="left", padx=5)
        ttk.Button(btn_frm, text="Cancel", command=self._on_cancel).pack(side="left")

        # --- Status + spinner
        self.status_lbl = ttk.Label(frm, text="Ready")
        self.status_lbl.grid(row=4, column=1, sticky="w")
        self.spinner = ttk.Progressbar(frm, mode="indeterminate")
        self.spinner.grid(row=5, column=1, sticky="ew", pady=5)

        ttk.Button(frm, text="Help", command=self._open_help_window).grid(row=6, column=1, pady=(10, 0), sticky="ew")

        # --- Transcribed text
        self.txt = scrolledtext.ScrolledText(self, height=15, state="disabled")
        self.txt.pack(fill="both", expand=True, padx=10, pady=10)

        # column config
        frm.columnconfigure(1, weight=1)

    def _open_help_window(self) -> None:
        help_window = tk.Toplevel(self)
        help_window.title("Help Information")
        help_window.geometry("650x260")

        backend = select_backend()
        device = backend.device_label()
        help_text = f"""
What this script does?
This script creates a complete .srt file (Transcription + timing) based on the provided audio file.

Which model to choose?
"Tiny" is the fastest model but least accurate, while "Large" is the slowest, but almost 100% accurate.
Using the large model requires a powerful machine and not too long an audio file.

Selected backend: {backend.name}
Detected compute device: {device}
{"(NVIDIA GPU acceleration)" if "cuda" in device else "(Apple Silicon GPU acceleration)" if "mps" in device else "(CPU only - this will be significantly slower, especially for larger models)"}

- Supported audio file formats: MP3, WAV, M4A
- Recommended maximum file size: 500MB
- Recommended maximum audio file duration: 2 hours
"""
        ttk.Label(help_window, text=help_text, justify=tk.LEFT).pack(padx=10, pady=10)

    def _browse_audio(self) -> None:
        p = filedialog.askopenfilename(
            title="Select Audio",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a"), ("All files", "*.*")]
        )
        if p:
            self.audio_entry.delete(0, tk.END)
            self.audio_entry.insert(0, p)

    def _save_srt(self) -> None:
        p = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("Subtitles", "*.srt")]
        )
        if p:
            self.srt_entry.delete(0, tk.END)
            self.srt_entry.insert(0, p)

    def _on_transcribe(self) -> None:
        audio = self.audio_entry.get().strip()
        srt = self.srt_entry.get().strip()
        model = self.model_var.get()
        if not audio or not srt:
            messagebox.showwarning("Missing files", "Please choose both an audio file and SRT save location.")
            return
        if not os.path.isfile(audio):
            messagebox.showerror("Not found", f"Audio file not found:\n{audio}")
            return

        # disable UI and start spinner
        self.go_btn.config(state="disabled")
        self.spinner.start(10)

        # thread-safe callbacks
        status_cb = lambda msg: self.after(0, self._update_status, msg)
        text_cb = lambda txt: self.after(0, self._update_text, txt)
        error_cb = lambda msg, tb: self.after(0, self._show_error, msg, tb)

        t = threading.Thread(
            target=self.transcriber.transcribe_audio_to_srt,
            args=(audio, srt, model, status_cb, text_cb, error_cb),
            daemon=True
        )
        t.start()

    def _on_cancel(self) -> None:
        self.transcriber.cancel_transcription()
        self.after(0, self._update_status, "Transcription cancelled.")

    def _update_status(self, msg: str) -> None:
        self.status_lbl.config(text=msg)
        # only stop spinner on final states:
        if msg.startswith("Subtitle file") or msg.startswith("Error") or msg.startswith("Transcription cancelled"):
            self.spinner.stop()
            self.go_btn.config(state="normal")

    def _update_text(self, txt: str) -> None:
        self.txt.config(state="normal")
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, txt)
        self.txt.config(state="disabled")

    def _show_error(self, msg: str, tb: str) -> None:
        messagebox.showerror("Transcription Error", f"{msg}\n\n{tb}")
