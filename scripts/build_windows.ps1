$ErrorActionPreference = 'Stop'
python -m pip install --upgrade pip
python -m pip install -e '.[all]' pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --windowed --name DouyinhehePro --collect-submodules yt_dlp --collect-submodules google.genai --collect-submodules pyttsx3 --collect-submodules faster_whisper --collect-all rapidocr --collect-all onnxruntime --collect-all cv2 --hidden-import PySide6.QtMultimedia --hidden-import PySide6.QtMultimediaWidgets --paths src launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host 'Build complete: dist/DouyinhehePro/DouyinhehePro.exe'
