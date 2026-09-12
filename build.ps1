# Build Script for HADJ AIR TOUCH
# Requires: pyinstaller (pip install pyinstaller)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "Building HADJ AIR TOUCH executable..." -ForegroundColor Cyan

# Ensure PyInstaller is installed
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing PyInstaller..."
    python -m pip install pyinstaller
}

# Build
pyinstaller `
    --name "HADJ Air Touch Portable" `
    --onedir `
    --add-data "app;app" `
    --collect-all "mediapipe" `
    --collect-all "PySide6" `
    --collect-all "cv2" `
    --hidden-import "numpy" `
    main.py

Write-Host "Build complete. Output in dist/" -ForegroundColor Green