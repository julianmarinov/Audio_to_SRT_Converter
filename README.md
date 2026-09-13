# Local Transcription & Subtitle Creator

A free, private, local app for turning audio and video into subtitles — no
account, no upload, no subscription. Point it at a file, a folder, or a
YouTube link, and it writes out a subtitle file next to it.

Runs entirely on your own computer. Nothing you transcribe is ever sent anywhere,
except the one-time download when you give it a YouTube link (the fetched
video's audio, not your transcript, and not any of your own data).

## What it can do

- Transcribe audio (MP3, WAV, M4A) or video (MP4, MOV) files
- Paste in a YouTube link instead of a file — it downloads just the audio and
  transcribes that
- Do a whole batch at once: add several files, or an entire folder, to a
  queue and let it run unattended
- Export as `.srt` or `.vtt` (subtitle files with timestamps), `.txt` (plain
  transcript, no timestamps), and/or `.json` — pick any combination
- Handle long recordings (1-2+ hours) automatically, without needing a
  powerful machine
- Choose between five model sizes, trading speed for accuracy depending on
  what you need

## Download

Grab the latest build for your platform from the
[Releases page](https://github.com/julianmarinov/Local-Transcription-and-Subtitle-Creator/releases).

### macOS

**Requires an Apple Silicon Mac** (M1, M2, M3, or M4 — anything from late
2020 onward). It will not run on an Intel Mac.

1. Download the latest `.zip` from Releases
2. Double-click the downloaded `.zip` to unzip it
3. Drag **Local Transcription & Subtitle Creator.app** into your Applications
   folder (optional, but tidier)
4. **First launch only:** right-click (or Control-click) the app and choose
   **Open**, then click **Open** again in the dialog that appears

Step 4 is necessary because this app isn't signed with an Apple Developer
certificate (that costs $99/year, which isn't worth it for a free hobby
project) — macOS shows a warning for any unsigned app the first time you open
it. A plain double-click may refuse to open it or just show a generic
warning; right-click → Open is the way around that, and you only need to do
it once. If your Mac doesn't offer an "Open" option that way, check **System
Settings → Privacy & Security** — there's usually an "Open Anyway" button
there after the first blocked attempt.

### Windows

Requires an NVIDIA GPU (CUDA) for best performance, but also runs on CPU if
you don't have one — just slower.

1. Download the latest `.zip` from Releases
2. Unzip it anywhere
3. Double-click **Local Transcription & Subtitle Creator.exe** inside

Windows may show a "Windows protected your PC" SmartScreen warning the first
time, for the same reason as macOS's warning above (no paid code-signing
certificate). Click **More info**, then **Run anyway**.

## How to use it

1. **Add something to the queue** — click **Add Files...** for one or more
   audio/video files, **Add Folder...** to grab everything in a folder, or
   **Add YouTube URL...** to paste in a video link
2. **Pick a model size** — see the guide below
3. **Pick your output format(s)** — check `.srt`, `.vtt`, `.txt`, and/or
   `.json`; you can select more than one
4. Click **Transcribe Queue**

Files are processed one at a time, in order — queuing more files doesn't
speed things up, it just means less babysitting. Click **Cancel** to stop;
it takes effect after the current chunk or file finishes, not instantly
mid-sentence.

Output files are saved:
- **Local files:** right next to the original file, same name, new extension
- **YouTube links:** in your **Downloads** folder, named after the video's
  title

### Which model size should I pick?

| Model | Speed | Accuracy |
|---|---|---|
| `tiny` | Fastest | Least accurate |
| `base` | Fast | Basic |
| `small` | Balanced | Good |
| `medium` | Slower | Very good |
| `large` | Slowest | Best |

For a quick draft or a short clip, `small` is a good default. For anything
you'll actually publish or rely on, use `large` if you don't mind the wait.

### The first time you use a given model size

The app downloads that model from the internet the first time you use it (a
few hundred MB to a few GB, depending on size). After that, it's cached on
your computer and every future transcription with that model works completely
offline. You'll see a "Downloading model..." progress message during that
first run.

## Things worth knowing

- **Whisper (the AI model this app uses) can occasionally get things
  slightly wrong or, rarely, repeat a phrase oddly.** If a transcript looks
  off in one spot, just running it again usually fixes it.
- **A YouTube download can occasionally fail** with an error mentioning
  "403 Forbidden." This is YouTube's side, not the app being broken —
  waiting a moment and retrying almost always works.
- **Disk space:** downloaded models are cached in a `.cache` folder in your
  user/home directory and can add up to a few GB if you use several model
  sizes. Safe to delete if you need the space back — they just re-download
  next time.

## FAQ

**Does it work with languages other than English?**
Yes — Whisper (the AI model behind this app) automatically detects the
spoken language and transcribes dozens of languages, not just English.

**Does it translate?**
No. It transcribes in whatever language is actually spoken — it doesn't
translate into English or any other language.

**Which output format should I use?**
`.srt` is the standard choice for adding subtitles in a video editor or
media player. `.vtt` is the web equivalent (used by HTML5 video). `.txt`
is just the words, no timestamps — good for reading, searching, or feeding
into something else. `.json` includes timestamps in a structured format,
useful if you're a developer building on top of the output.

**Why is the download so large (~400MB)?**
It bundles a full Python environment, the AI libraries, and ffmpeg, so it
runs standalone with nothing separate to install. The AI models themselves
are downloaded separately, on first use (see above).

**Does it need an internet connection?**
Only for two things: downloading a model the first time you use that size,
and fetching a video's audio when you give it a YouTube link. Everything
else — the actual transcription — runs offline.

## Running from source / contributing

This repo also contains the full Python source, if you want to modify it or
build it yourself. See
[`Documentation/How to install dependencies.txt`](Documentation/How%20to%20install%20dependencies.txt)
for setup steps on macOS and Windows. Nothing in the code is Mac/Windows-
specific, so it should also run on Linux from source, but that hasn't
actually been tested.

## License

[MIT](LICENSE) — free to use, modify, and share.
