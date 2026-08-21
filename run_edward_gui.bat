@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Edward Trading Platform v0.1 - GUI
echo ========================================
echo.

set "LOG_FILE=%~dp0runtime\edward_gui.log"

echo Full console output is saved to: %LOG_FILE%
echo.

echo Installing Edward...
.venv\Scripts\python.exe -m pip install --upgrade pip >> "%LOG_FILE%" 2>&1
.venv\Scripts\python.exe -m pip install -e . >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :install_error

echo.
echo Checking T-Invest adapter...
.venv-tinvest\Scripts\python.exe -m pip install -r runtime\requirements.txt --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple >> "%LOG_FILE%" 2>&1
if errorlevel 1 goto :tinvest_error

echo Starting Edward GUI...
echo Live launcher output will be written to the log file.

.venv\Scripts\python.exe -m edward.ui.gui_launcher >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" echo Edward GUI finished with error code %EXIT_CODE%.

echo.
echo ================= CONSOLE LOG =================
type "%LOG_FILE%"
echo =============== END CONSOLE LOG ===============
echo.
echo Log file: %LOG_FILE%
pause
exit /b %EXIT_CODE%

:install_error
echo ERROR: Failed to install Edward dependencies.
echo See log: %LOG_FILE%
type "%LOG_FILE%"
pause
exit /b 1

:tinvest_error
echo ERROR: Failed to install or validate T-Invest SDK.
echo See log: %LOG_FILE%
type "%LOG_FILE%"
pause
exit /b 1
