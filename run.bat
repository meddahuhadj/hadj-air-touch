@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo   HADJ AIR TOUCH - Setup ^& Launch
echo ============================================
echo.

rem If the active Python already has the dependencies, use it directly.
python -c "import PySide6, cv2, mediapipe, numpy" >nul 2>nul
if %ERRORLEVEL%==0 goto launch

if not exist ".venv\Scripts\activate.bat" (
    echo [1/2] Creating virtual environment...
    python -m venv .venv >nul 2>nul
    if not exist ".venv\Scripts\activate.bat" (
        rem ensurepip is blocked (Application Control / restricted policy):
        rem fall back to a pip-less virtual environment.
        echo       pip blocked; creating a pip-less venv...
        rmdir /s /q ".venv" >nul 2>nul
        python -m venv --without-pip .venv >nul 2>nul
    )
)
if exist ".venv\Scripts\activate.bat" call ".venv\Scripts\activate.bat"

python -c "import PySide6, cv2, mediapipe, numpy" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo.
    echo Some dependencies are missing. Install with:
    echo   python -m pip install -r requirements.txt
    echo Offline / restricted PC? See README: "Offline / restricted networks".
    echo.
)

:launch
echo [2/2] Launching HADJ AIR TOUCH...
python main.py %*
pause
endlocal