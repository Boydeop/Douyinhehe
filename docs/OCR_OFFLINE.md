# Offline Chinese OCR: Windows portable requirements

## Runtime

The 3.1.0 portable ZIP embeds `rapidocr` (maintained 3.x package), `onnxruntime`
CPU, and model weights in `rapidocr/models/*.onnx` under the PyInstaller bundle.
The OCR code uses local PIL image input, never remote URLs or `result.vis()`
(which may try to download fonts). No API key or internet connection is needed.

## Development

```powershell
py -3.12 -m pip install -e ".[all,dev]"
python -m douyinhehe --ocr-self-test
```

## Build validation

The Windows Action fails unless at least three model files are present inside
the onedir output and the frozen EXE completes a real recognition inference
from a generated Chinese test image. `--doctor` reports OCR readiness.
Run `DouyinhehePro.exe --ocr-self-test` after unpacking to diagnose local issues.

## Reliability and privacy

- OCR text is processed locally. No image/video is sent to Gemini by this step.
- A detected rectangle is only a proposal on one frame. It may include on-screen
  Chinese titles instead of just subtitles, and subtitles that move or appear
  later can be missed. Review the full edited video and add manual regions.
- OCR does not remove watermark/copyright obligations. Use only content you
  have permission to edit and republish.
- Offline models: RapidOCR and its derived PaddleOCR model weights use Apache-2.0;
  ONNX Runtime CPU uses MIT. See `docs/THIRD_PARTY.md`.
