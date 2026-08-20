@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward Trading Platform v0.1
echo ========================================

echo.
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Create it with:
    echo     python -m venv .venv
    echo     .venv\Scripts\python.exe -m pip install -e .
    pause
    exit /b 1
)

echo Checking project installation...
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install project dependencies.
    pause
    exit /b 1
)

echo.
echo Starting Edward...
echo.
.venv\Scripts\python.exe -m edward
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" (
    echo Edward finished with error code %EXIT_CODE%.
) else (
    echo Edward finished successfully.
)
pause
exit /b %EXIT_CODE%
