# HADJ AIR TOUCH - PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  HADJ AIR TOUCH - Setup & Launch" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

function Test-Deps {
    python -c "import PySide6, cv2, mediapipe, numpy" 2>$null
    return ($LASTEXITCODE -eq 0)
}

function Ensure-Venv {
    if (Test-Path ".venv\Scripts\Activate.ps1") { return }
    Write-Host "[1/2] Creating virtual environment..."
    python -m venv .venv 2>$null
    if (($LASTEXITCODE -ne 0) -and (Test-Path ".venv")) {
        # ensurepip is blocked (Application Control / restricted policy).
        Write-Host "      pip blocked; creating a pip-less venv..." -ForegroundColor Yellow
        Remove-Item -Recurse -Force ".venv"
        python -m venv --without-pip .venv 2>$null
    }
}

# If the active Python already has everything, use it directly.
if (Test-Deps) {
    Write-Host "[1/2] Dependencies found in the active Python environment." -ForegroundColor Green
} else {
    Ensure-Venv
    if (Test-Path ".venv\Scripts\Activate.ps1") {
        . .\.venv\Scripts\Activate.ps1
    }
    if (-not (Test-Deps)) {
        Write-Host "Some dependencies are missing. Install with:" -ForegroundColor Yellow
        Write-Host "  python -m pip install -r requirements.txt" -ForegroundColor Yellow
        Write-Host "Offline / restricted PC? See README: 'Offline / restricted networks'." -ForegroundColor Yellow
    }
}

# Launch
Write-Host "[2/2] Launching HADJ AIR TOUCH..."
python main.py @args