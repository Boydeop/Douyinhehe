# Douyinhehe Studio 3.0 · Development preview

## New workflow

1. Paste multiple licensed Douyin video URLs or use an explicit
   `https://www.douyin.com/user/...` profile URL with **Toàn kênh** mode.
2. Choose a bounded playlist limit, or explicitly confirm 0 (all obtainable
   items). A persistent `yt-dlp` archive prevents downloads already completed.
3. Open Studio, choose multiple local videos, scrub a representative frame,
   and **drag on the preview** to define manual blur or solid cover regions.
4. Click **Nhận diện chữ Trung bằng OCR offline** for detected Chinese text boxes.
   RapidOCR, ONNX Runtime and the three Chinese OCR models are bundled in Windows
   v3.1. Missing model assets fail the build/self-test instead of silently guessing.
5. Tune fit, color, CTA, trim, subtitles and narration. Apply to a batch
   or use CSV/JSON queue with `masks`, `trim_start`, `trim_end`.

The Windows executable now bundles the maintained `rapidocr` package and ONNX
Runtime CPU models. The editor analyzes a representative frame, so moving
captions need manual verification or additional user-selected regions.
See [OCR_OFFLINE.md](OCR_OFFLINE.md) for smoke-test instructions and caveats.

## Private data

The new UI never asks for or stores creator names, license evidence files,
contract references or expiration dates. Rights confirmation is still
required for download/render. Old SQLite databases may still contain those
fields from v2.1, so Settings includes an **explicit purge** of legacy
metadata. Old exported provenance JSON files are not deleted automatically.
Back up a database before the irreversible operation if desired.

Source URLs may still be included in output metadata or a sidecar for
attribution as required by the content license; the operator is responsible
for source credits in the published description when required.

## Upstream skills

- [ffmpeg-skill](https://github.com/kajisho5/ffmpeg-skill), MIT:
  transform planning, overlays and export verification.
- [video-editing-skill](https://github.com/kajisho5/video-editing-skill), MIT:
  operation validation and reproducible exports.
- [subtitle-skill](https://github.com/kajisho5/subtitle-skill), MIT:
  timeline consistency and burn-in QA.
- [morluto/rea](https://github.com/morluto/rea), MIT:
  reverse engineering and inspecting **compiled PyInstaller executables**.
  Not an FFmpeg editor or a video enhancement engine. This preview does not
  bundle the REA runtime or claim an REA binary audit.

This project does not help evade copyright matching or originality rules.
Crop, color and masking do not remove obligations to original rightsholders.
