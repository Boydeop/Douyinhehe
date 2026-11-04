# Douyinhehe Studio 3.0 · Development preview

## New workflow

1. Paste multiple licensed Douyin video URLs or use an explicit
   `https://www.douyin.com/user/...` profile URL with **Toàn kênh** mode.
2. Choose a bounded playlist limit, or explicitly confirm 0 (all obtainable
   items). A persistent `yt-dlp` archive prevents downloads already completed.
3. Open Studio, choose multiple local videos, scrub a representative frame,
   and **drag on the preview** to define manual blur or solid cover regions.
4. Click **Gợi ý vùng phụ đề Trung** for optional RapidOCR text boxes. When
   RapidOCR is not installed, the app suggests a generic lower-third only
   and clearly says it did **not** detect Chinese text.
5. Tune fit, color, CTA, trim, subtitles and narration. Apply to a batch
   or use CSV/JSON queue with `masks`, `trim_start`, `trim_end`.

The executable does not ship RapidOCR weights by default. For a development
setup, install the optional `rapidocr-onnxruntime` package and confirm that
its model redistribution terms and the real binary build are compatible.

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
