# Local Transcription & Subtitle Creator

A free, private, local app for turning audio and video into subtitles — no
account, no upload, no subscription. Point it at a file, a folder, or a
YouTube link, and it writes out a subtitle file next to it.

Runs entirely on your Mac. Nothing you transcribe is ever sent anywhere,
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

**Requires an Apple Silicon Mac** (M1, M2, M3, or M4 — anything from late
2020 onward). It will not run on an Intel Mac.

1. Go to the [Releases page](https://github.com/julianmarinov/local-transcription-subtitle-creator/releases)
   and download the latest `.zip`
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

## How to use it

1. **Add something to the queue** — click **Add Files...** for one or more
   audio/video files, **Add Folder...** to grab everything in a folder, or
   **Add YouTube URL...** to paste in a video link
2. **Pick a model size** — see the guide below
3. **Pick your output format(s)** — check `.srt`, `.vtt`, `.txt`, and/or
   `.json`; you can select more than one
4. Click **Transcribe Queue**

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
your Mac and every future transcription with that model works completely
offline. You'll see a "Downloading model..." progress message during that
first run.

## Things worth knowing

- **Whisper (the AI model this app uses) can occasionally get things
  slightly wrong or, rarely, repeat a phrase oddly.** If a transcript looks
  off in one spot, just running it again usually fixes it.
- **A YouTube download can occasionally fail** with an error mentioning
  "403 Forbidden." This is YouTube's side, not the app being broken —
  waiting a moment and retrying almost always works.
- **Disk space:** downloaded models are cached in a hidden folder in your
  home directory (`~/.cache`) and can add up to a few GB if you use several
  model sizes. Safe to delete if you need the space back — they just
  re-download next time.

## Running from source / contributing

This repo also contains the full Python source, if you want to modify it,
run it on Windows or Linux, or build it yourself. See
[`Documentation/How to install dependencies.txt`](Documentation/How%20to%20install%20dependencies.txt)
for setup steps on both macOS and Windows.

## License

[MIT](LICENSE) — free to use, modify, and share.
