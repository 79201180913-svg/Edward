@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward - Test Runner
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.14 virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python 3.14 was not found.
        pause
        exit /b 1
    )
)

echo Installing project and dependencies...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e . --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
if errorlevel 1 (
    echo ERROR: Failed to install project dependencies.
    pause
    exit /b 1
)

.venv\Scripts\python.exe -m pip install pytest
if errorlevel 1 (
    echo ERROR: Failed to install pytest.
    pause
    exit /b 1
)

echo.
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
