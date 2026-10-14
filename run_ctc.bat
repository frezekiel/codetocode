@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe -c "import PIL, pymupdf" >nul 2>nul
if errorlevel 1 (
    echo Scananzeige wird eingerichtet...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 goto :failed
)
.venv\Scripts\python.exe src\app.py
if errorlevel 1 goto :failed
exit /b 0
:failed
echo CtC konnte nicht gestartet werden. Fehlerdetails stehen oben.
pause
exit /b 1
