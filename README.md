# video-text-extraction

A skill for extracting **timed lyrics / subtitles** from a local media file — the case
where a downloaded video has no soft subtitle track but has the text **burned into the
picture**, and the case where you only have audio.

## What it solves

You hand it a `.mp4` / `.m4s` / `.mkv` / `.m4a` / `.mp3` and ask for the lyrics with
timestamps. It returns an `.lrc` (or plain `M:SS  text`).

Three paths, in priority order:

| Source | Method | Quality |
|--------|--------|---------|
| Soft subtitle stream | `ffmpeg -map 0:s:0 out.srt` | perfect |
| Burned-in (hardsub) text | dense frame OCR + vision spot-fill | near-perfect wording |
| Audio only | `faster-whisper` (no VAD for singing) | good timing, mishears sung words |

The trick that matters: when both on-screen text and audio exist, **use OCR for the words
and whisper for the timing**. Whisper mishears lyrics badly ("petals" → "pedophiles"), but
the burned-in text is the official spelling.

## Notable gotchas documented

- Bilibili `.m4s` files are **video-only** — audio lives in a companion file.
- The **title card is not the caption band** — deriving crop coordinates from frame 0
  misses every lyric.
- **Tesseract's shared-library deps fail one at a time** (`liblept.so.5`, then
  `libarchive.so.13`, then `libgif.so.7`…). Install the whole set up front; note that
  `libarchive13` has no candidate on newer Ubuntu (`libarchive13t64`) and that `liblept5`
  is the package with the real `.so`.
- **A garbled OCR read is usually a crop bug, not an OCR bug.** Crop the band and ask a
  vision model what text is in *it* before tuning `--psm`.
- **Do not use VAD for singing** — it drops quiet vocal lines and can reduce a 3-minute
  song to a handful of segments.
- **HuggingFace is blocked in mainland China** — use `HF_ENDPOINT=https://hf-mirror.com`
  **and** `HF_HUB_DISABLE_XET=1` (the xet backend 401s against the mirror).
- Captions fade in mid-line, so the first frame of a run often catches only a tail
  (`ime winter says goodbye`) — take the most complete read, timestamp from the first frame.

## Layout

```
SKILL.md                      main skill: decision tree, whisper tuning, OCR sweep
references/hardsub-ocr.md     full hardsub playbook: deb install, crop, batch sweep, .lrc
references/whisper-setup.md   faster-whisper install + the China mirror fix
scripts/transcribe.py         whisper wrapper tuned for singing
```

## Chains with `guitar-tabs`

The `.lrc` this produces is exactly the input the [guitar-tabs](https://github.com/Lumos12345/guitar-tabs)
skill wants for its LRC-synced chord chart:

```
video-text-extraction  →  timed lyrics (.lrc)  →  guitar-tabs  →  弹唱谱
```

## License

MIT
