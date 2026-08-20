@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward - Test Runner
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

echo Running tests...
echo.
.venv\Scripts\python.exe -m pytest -q
set EXIT_CODE=%ERRORLEVEL%

echo.
if "%EXIT_CODE%"=="0" (
    echo ========================================
    echo ALL TESTS PASSED
    echo ========================================
) else (
    echo ========================================
    echo TESTS FAILED - code %EXIT_CODE%
    echo ========================================
)

pause
exit /b %EXIT_CODE%
