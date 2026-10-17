# Whisper setup & mainland-China HF mirror

## Install faster-whisper (CPU, int8)

```bash
uv venv /tmp/wvenv
/tmp/wvenv/bin/python -m pip install faster-whisper
```

`uv venv` bootstraps pip into a bare venv only after `ensurepip`; if
`/tmp/wvenv/bin/pip` is missing, call the module form directly:
`/tmp/wvenv/bin/python -m pip install ...`.

The install downloads ctranslate2, onnxruntime, tokenizers, huggingface-hub,
numpy — a few hundred MB. Run it as a tracked background process
(`terminal(background=True, notify_on_complete=True)`) rather than a foreground
call that times out.

## Model download hangs? Use the HF mirror

Symptom: the process sits at ~5 MB RSS for minutes with 1 thread and no output —
it's blocked reaching `huggingface.co` (normal in mainland China).

Fix — set BOTH env vars:

```bash
HF_HUB_DISABLE_XET=1 HF_ENDPOINT=https://hf-mirror.com \
  /tmp/wvenv/bin/python transcribe.py /tmp/song.wav medium
```

- `HF_ENDPOINT=https://hf-mirror.com` routes downloads through the mirror.
- `HF_HUB_DISABLE_XET=1` is REQUIRED: the default `hf-xet` transfer backend
  errors with `401 Unauthorized` against `cas-server.xethub.hf.co` when using
  the mirror. Disabling it forces classic HTTP download, which works.

If you still see no `~/.cache/huggingface` growth after ~30s, the download is
stalled — re-run with the env vars above.

## Spotting a healthy vs stalled load

- Loading/downloading: low RSS (~5 MB), 1 thread, `State: S`.
  For a Python script, the real worker is the child PID (check
  `ps --ppid <pid>`); the parent just waits.
- Actually transcribing: RSS ~1–1.5 GB (medium model), high cumulative CPU
  jiffies in `/proc/<pid>/stat` field 14+15.

## Model choice

- `medium` — good accuracy, fast enough on CPU (a 156s song ≈ 2 min).
- `large-v3` — better, notably slower on CPU.
- `tiny`/`base` — only for quick drafts; poor on sung vocals.
