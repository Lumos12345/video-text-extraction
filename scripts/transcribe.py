#!/usr/bin/env python3
"""Transcribe audio with word/sentence timestamps using faster-whisper.

Usage:
    python transcribe.py AUDIO [MODEL] [LANG]

Defaults: MODEL=medium, LANG=en.

For sung vocals:
  - Do NOT enable vad_filter (it drops quiet/reverbed lines).
  - Keep condition_on_previous_text=True and temperature fallback.

For mainland China, run with:
    HF_HUB_DISABLE_XET=1 HF_ENDPOINT=https://hf-mirror.com python transcribe.py ...
"""
import sys, json
from faster_whisper import WhisperModel

audio = sys.argv[1]
model_size = sys.argv[2] if len(sys.argv) > 2 else "medium"
lang = sys.argv[3] if len(sys.argv) > 3 else "en"

model = WhisperModel(model_size, device="cpu", compute_type="int8")

segments, info = model.transcribe(
    audio,
    language=lang,
    beam_size=5,
    temperature=[0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    condition_on_previous_text=True,
    no_speech_threshold=0.8,
    log_prob_threshold=-1.5,
    compression_ratio_threshold=2.8,
    word_timestamps=True,
    # NOTE: no vad_filter for music; see docstring.
    hallucination_silence_threshold=1.5,
)

print(f"# lang={info.language} prob={info.language_probability:.2f} dur={info.duration:.1f}s",
      file=sys.stderr)

out = []
for seg in segments:
    text = seg.text.strip()
    if not text:
        continue
    out.append({"start": round(seg.start, 2), "end": round(seg.end, 2), "text": text})
    print(f"[{seg.start:6.2f} - {seg.end:6.2f}] {text}")

with open("/tmp/lyrics_raw.json", "w") as f:
    json.dump(out, f, ensure_ascii=False, indent=2)
