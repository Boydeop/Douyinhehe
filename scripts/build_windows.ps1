$ErrorActionPreference = 'Stop'
python -m pip install --upgrade pip
python -m pip install -e '.[all]' pyinstaller
python -m PyInstaller --noconfirm --clean --onedir --windowed --name DouyinhehePro --collect-submodules yt_dlp --collect-submodules google.genai --collect-submodules pyttsx3 --collect-submodules faster_whisper --paths src launcher.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed' }
Write-Host 'Build complete: dist/DouyinhehePro/DouyinhehePro.exe'
