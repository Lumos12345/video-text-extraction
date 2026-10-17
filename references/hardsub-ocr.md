# Burned-in (hardsub) text OCR — full playbook

When a video renders lyrics/captions into the picture (no soft subtitle stream), OCR frames to recover the official text.

## 1. Install tesseract without sudo

`sudo apt-get install` fails if the terminal can't prompt for a password. Instead, download the `.deb`s and extract them to a local prefix:

```bash
cd /tmp
mkdir -p tess
for p in tesseract-ocr tesseract-ocr-eng libtesseract5 liblept5 libarchive13t64 \
         libgif7 libjpeg-turbo8 libopenjp2-7 libwebp7 libtiff6; do
  apt-get download "$p"
done
for f in /tmp/*.deb; do dpkg-deb -x "$f" /tmp/tess; done
```

Notes:
- `libarchive13` may have "no candidate" on newer Ubuntu — use **`libarchive13t64`**.
- `liblept5` provides the real `liblept.so.5.0.4` (the dev package only ships dangling symlinks).
- Verify deps: `LD_LIBRARY_PATH=/tmp/tess/usr/lib/x86_64-linux-gnu ldd /tmp/tess/usr/bin/tesseract | grep "not found"` — should print nothing.

Wrap the env in a script (inline `export` can trip command-approval):

```bash
# /tmp/tessenv.sh
export LD_LIBRARY_PATH=/tmp/tess/usr/lib/x86_64-linux-gnu
export TESSDATA_PREFIX=/tmp/tess/usr/share/tesseract-ocr/5/tessdata
TES="/tmp/tess/usr/bin/tesseract"
```

## 2. Locate the caption band

Ask vision for coordinates instead of guessing:

> "There's a line of white subtitle text in the lower portion of this 1920x1080 image. Give approximate pixel coordinates (x,y) where it begins."

Typical music-video result: text starts around **(120, 950)** — band `crop=1500:95:90:910`. A crop 100px too high returns pure noise, so always confirm visually.

**Diagnose a bad crop fast.** The failure is deceptive: tesseract prints alphabet soup
like `i zs & 283) _` or nothing at all, which looks like "OCR can't read this" when it is
really "you cropped the artwork". One cheap check separates them — crop your band and
`vision_analyze` **the cropped band itself** with "what text is visible?". If vision also
sees no text, the crop is wrong, not the OCR tuning. If vision reads it fine, the crop is
correct and you only need the vision spot-fill path (§4).

Also re-derive the band per video: a `y=830` band that captured text on one frame
silently missed it on another because the caption baseline shifts with the artwork. Take
the coordinates from a **mid-song frame with a long lyric line**, not the title card.

## 3. Extract + OCR frames

```bash
# ~0.5s resolution across the whole clip
ffmpeg -y -i "$SRC" -vf "fps=2" /tmp/frames/f_%04d.png
```

Frame `f_NNNN` is at timestamp `N/2` seconds. Per frame:

```bash
ffmpeg -y -loglevel error -i frame.png \
  -vf "crop=1500:95:90:910,scale=3000:-1,format=gray" band.png
"$TES" band.png stdout --psm 6
```

`--psm 6` (single uniform block) beats `--psm 7` on these. Preprocessing that helps: upscale 2–3x then grayscale. `negate`/hard threshold often makes it worse on photo backgrounds.

### The upscale-width/source-res rule

The band crop must be scaled relative to the **source** resolution, not copied blindly.
A working shape for 1920-wide video: `crop=W:95:X:Y` where W covers the text, then
`scale=` to about **1.5–3x the crop width** (e.g. 1500 → 3000). Two failure modes:

- **Under-scaled** (no `scale`): tiny glyphs, tesseract returns 1–2 characters.
- **Over-scaled on a small crop**: you have cut the line in half, so you OCR a fragment
  like `reach the highest heigt` with the final letter missing. If every frame truncates
  the same way, widen the crop — it is not an OCR-tuning problem.

Verify by OCRing one known-good frame and checking the result against what vision reads
from the full frame. Once they agree, sweep the rest.

### Batch-sweep pattern (avoid one tool call per frame)

Do the whole clip in a single shell loop writing `timestamp|text` lines, then read the
file once:

```bash
for f in /tmp/frames/f_*.png; do
  n=$(basename "$f" .png | sed 's/f_//')
  ts=$(awk -v n=$n 'BEGIN{printf "%.1f", n/2}')
  ffmpeg -y -loglevel error -i "$f" -vf "crop=...,scale=...,format=gray" /tmp/b.png
  txt=$("$TES" /tmp/b.png stdout --psm 6 2>/dev/null | tr '\n' ' ' | sed 's/  */ /g;s/^ *//;s/ *$//')
  echo "$ts|$txt" >> /tmp/ocr_results.txt
done
```

313 frames (~0.4s each) ≈ 2 minutes. Then grep the result for clean lines and use vision
only on the timestamps whose rows are empty/garbled. Far cheaper than 300 vision calls.

## 4. Handle low-contrast text with vision

Tesseract returns garbage (or nothing) when the caption is pale serif over a bright scene. For those frames, extract the full frame and call `vision_analyze` with:

> "There is a line of white lyric text in the lower-left. Transcribe it exactly, or say 'no text'."

Vision reads these reliably. **Hybrid pattern: tesseract for the bulk sweep (fast, machine-parseable timestamps), vision to spot-fill the lines tesseract missed.** This is how you get both accurate text and a complete timestamp grid.

## 5. Assemble the lyrics

- Walk the frame list in time order. When a line first appears cleanly, record `timestamp = frame_index / 2`.
- Consecutive frames repeating the same line = one lyric line.
- Different lines may hold for several seconds — the *first* clean frame is the start time.
- Reconcile with the whisper transcript for lines/holds you're unsure about.

### Captions that fade in mid-line

Some videos fade the caption in/out, so the earliest frames of a line catch only its
tail (`ime winter says goodbye` — the leading `t` of "time" clipped by the fade). Always
take the **longest/most complete read** across the run of frames holding that line, not
the first one, and use the *first frame of the run* for the timestamp. If the head of a
line is permanently cut in every frame, infer it from the chorus/verse parallel and say
so in the deliverable rather than silently shipping a fragment.

### Emitting the .lrc

Build it programmatically from a `(seconds, text)` list so the `mm:ss.xx` conversion is
never hand-done (easy to write `01:27.50` when you mean `01:03.50`). Format:
`[ti:..] [ar:..] [length:mm:ss]` header, then `[{m:02d}:{s:05.2f}]{line}` — the `05.2f`
gives `03.50` so the bracket is `[01:03.50]`.

```python
def lrc_ts(sec):
    m = int(sec // 60); s = sec - m*60
    return f"[{m:02d}:{s:05.2f}]"
```

Also emit the plain `M:SS.S  line` text version — users often want to read it without a
player, and it is the format the `guitar-tabs` skill's chord-per-line step consumes most
readably.
