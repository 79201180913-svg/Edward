@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward Trading Platform v0.1
echo ========================================
echo.

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.14 virtual environment...
    py -3.14 -m venv .venv
    if errorlevel 1 (
        echo ERROR: Python 3.14 was not found.
        echo Install Python 3.14 and try again.
        pause
        exit /b 1
    )
)

echo Checking project installation...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :install_error

.venv\Scripts\python.exe -m pip install -e . --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
if errorlevel 1 goto :install_error

echo.
echo Starting Edward...
echo.
.venv\Scripts\python.exe -m edward.main
set EXIT_CODE=%ERRORLEVEL%

echo.
if not "%EXIT_CODE%"=="0" (
    echo Edward finished with error code %EXIT_CODE%.
) else (
    echo Edward finished successfully.
)
pause
exit /b %EXIT_CODE%

:install_error
echo.
echo ERROR: Failed to install project dependencies.
echo T-Invest SDK is installed from the official T-Bank package index.
pause
exit /b 1
