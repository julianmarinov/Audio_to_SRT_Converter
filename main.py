#!/usr/bin/env python3
import os

# Must be set before any MPS op runs so unsupported ops silently fall back
# to CPU instead of crashing (relevant on Apple Silicon / MPS).
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import datetime
import shutil
import threading

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

# openai-whisper (pip install openai-whisper) - import name is "whisper"
import whisper
import torch

# ----------------------------------------------------------------------------
# Requirements:
#   pip install -r requirements.txt
#   ffmpeg must be on PATH (macOS: brew install ffmpeg | Windows: see ffmpeg.org)
#   tkinter (macOS: brew install python-tk, if not already bundled with Python)
#
# Runs on CUDA (NVIDIA GPU), MPS (Apple Silicon GPU), or CPU - whichever is
# available is selected automatically.
# ----------------------------------------------------------------------------


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_built() and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


class TranscriptionService:
    def __init__(self):
        self.cancelled = False

    def cancel_transcription(self):
        self.cancelled = True

    def transcribe_audio_to_srt(
        self,
        audio_file_path: str,
        srt_file_path: str,
        model_type: str,
        update_status,                # must be thread-safe (i.e. schedule back to mainloop)
        update_transcription_text,    # same
    ):
        self.cancelled = False
        try:
            if not shutil.which("ffmpeg"):
                raise RuntimeError("ffmpeg not found in PATH. Please install ffmpeg.")

            device = get_device()
            update_status(f"Loading model on {device.type}...")
            model = whisper.load_model(model_type, device=device)
            if device.type == "cuda":
                model = model.half()

            update_status("Transcribing...")
            with torch.no_grad():
                # fp16 autocast is only reliable on CUDA; on MPS it produces
                # garbled/repeated output, and CPU doesn't support it at all.
                result = model.transcribe(audio_file_path, fp16=(device.type == "cuda"))

            if self.cancelled:
                update_status("Transcription cancelled.")
                return

            update_status("Formatting subtitles...")
            subtitles = self._build_srt_segments(result["segments"])
            self._write_srt_file(subtitles, srt_file_path)

            full_text = "\n".join(seg["text"] for seg in result["segments"])
            update_transcription_text(full_text)

            update_status("Subtitle file created successfully.")
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            update_status("Error during transcription.")
            messagebox.showerror("Transcription Error", f"{e}\n\n{tb}")

    def _build_srt_segments(self, segments):
        out = []
        for i, seg in enumerate(segments, start=1):
            start = self._fmt_time(seg["start"])
            end = self._fmt_time(seg["end"])
            text = seg["text"].strip()
            out.append(f"{i}\n{start} --> {end}\n{text}\n\n")
        return out

    @staticmethod
    def _write_srt_file(subtitles, path):
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.writelines(subtitles)

    @staticmethod
    def _fmt_time(seconds: float) -> str:
        td = datetime.timedelta(seconds=seconds)
        total = int(td.total_seconds())
        hrs, rem = divmod(total, 3600)
        mins, secs = divmod(rem, 60)
        ms = td.microseconds // 1000
        return f"{hrs:02}:{mins:02}:{secs:02},{ms:03}"


class AudioToSRTConverter(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Audio to SRT Converter")
        self.geometry("800x600")
        self.transcriber = TranscriptionService()
        self._build_ui()

    def _build_ui(self):
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

    def _open_help_window(self):
        help_window = tk.Toplevel(self)
        help_window.title("Help Information")
        help_window.geometry("650x260")

        device = get_device()
        help_text = f"""
What this script does?
This script creates a complete .srt file (Transcription + timing) based on the provided audio file.

Which model to choose?
"Tiny" is the fastest model but least accurate, while "Large" is the slowest, but almost 100% accurate.
Using the large model requires a powerful machine and not too long an audio file.

Detected compute device: {device.type}
{"(NVIDIA GPU acceleration)" if device.type == "cuda" else "(Apple Silicon GPU acceleration)" if device.type == "mps" else "(CPU only - this will be significantly slower, especially for larger models)"}

- Supported audio file formats: MP3, WAV, M4A
- Recommended maximum file size: 500MB
- Recommended maximum audio file duration: 2 hours
"""
        ttk.Label(help_window, text=help_text, justify=tk.LEFT).pack(padx=10, pady=10)

    def _browse_audio(self):
        p = filedialog.askopenfilename(
            title="Select Audio",
            filetypes=[("Audio", "*.mp3 *.wav *.m4a"), ("All files", "*.*")]
        )
        if p:
            self.audio_entry.delete(0, tk.END)
            self.audio_entry.insert(0, p)

    def _save_srt(self):
        p = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("Subtitles", "*.srt")]
        )
        if p:
            self.srt_entry.delete(0, tk.END)
            self.srt_entry.insert(0, p)

    def _on_transcribe(self):
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

        t = threading.Thread(
            target=self.transcriber.transcribe_audio_to_srt,
            args=(audio, srt, model, status_cb, text_cb),
            daemon=True
        )
        t.start()

    def _on_cancel(self):
        self.transcriber.cancel_transcription()
        self.after(0, self._update_status, "Transcription cancelled.")

    def _update_status(self, msg: str):
        self.status_lbl.config(text=msg)
        # only stop spinner on final states:
        if msg.startswith("Subtitle file") or msg.startswith("Error") or msg.startswith("Transcription cancelled"):
            self.spinner.stop()
            self.go_btn.config(state="normal")

    def _update_text(self, txt: str):
        self.txt.config(state="normal")
        self.txt.delete("1.0", tk.END)
        self.txt.insert(tk.END, txt)
        self.txt.config(state="disabled")


if __name__ == "__main__":
    app = AudioToSRTConverter()
    app.mainloop()
