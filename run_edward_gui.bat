@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward Trading Platform v0.1 - GUI
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

if not exist ".venv-tinvest\Scripts\python.exe" (
    echo Creating T-Invest Python 3.12 virtual environment...
    py -3.12 -m venv .venv-tinvest
    if errorlevel 1 (
        echo ERROR: Python 3.12 was not found.
        pause
        exit /b 1
    )
)

echo Installing Edward...
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :install_error

echo.
echo Checking T-Invest adapter...
.venv-tinvest\Scripts\python.exe -m pip install -r runtime\requirements.txt --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
if errorlevel 1 goto :tinvest_error

.venv\Scripts\python.exe -m edward.ui.gui_launcher
set EXIT_CODE=%ERRORLEVEL%
if not "%EXIT_CODE%"=="0" (
    echo Edward GUI finished with error code %EXIT_CODE%.
)
exit /b %EXIT_CODE%

:install_error
echo ERROR: Failed to install Edward dependencies.
pause
exit /b 1

:tinvest_error
echo ERROR: Failed to install or validate T-Invest SDK.
pause
exit /b 1
