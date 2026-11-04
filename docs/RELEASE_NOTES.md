# Douyinhehe Studio v3.1.0 - OCR bundled / audited release candidate

This update focuses on shipping Chinese text OCR **inside** the Windows portable
EXE distribution. It adds maintainable RapidOCR and ONNX Runtime CPU, bundled
ONNX model weights, build-time artifact checking, and a real frozen OCR inference
smoke test. No remote OCR service, API key, or model download is required.

Changes:
- Direct OCR result contract via `RapidOCR(...).boxes/txts/scores`.
- Cached engine shared between preview and batch workers.
- Fail clearly if model assets are missing, instead of applying an unrelated
  lower-third region to every video.
- Manual masks remain intact in automatic batch mode.
- OCR status button and `--ocr-self-test` command.
- Test cases for OCR boxes, no-detection, confidence threshold and failure paths.

Limitations: OCR works from sampled frames and does not track changing text
throughout an entire video. Always inspect the result. Distribution of FFmpeg,
Qt and ONNX OCR components has separate license obligations. See THIRD_PARTY.md.
This release does not unlock accounts, bypass platform restrictions, guarantee
reach, or make transforms exempt from copyright.
