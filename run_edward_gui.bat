@echo off
setlocal
cd /d "%~dp0"

set "LOG_FILE=%~dp0runtime\edward_gui.log"

echo ========================================
echo Edward Trading Platform v0.1 - GUI
echo ========================================
echo.
echo Full console output is saved to: %LOG_FILE%
echo.

>"%LOG_FILE%" echo ========================================
>>"%LOG_FILE%" echo Edward Trading Platform v0.1 - GUI
>>"%LOG_FILE%" echo Started: %date% %time%
>>"%LOG_FILE%" echo ========================================

if not exist ".venv\Scripts\python.exe" (
    echo Creating Python 3.14 virtual environment...
    >>"%LOG_FILE%" echo Creating Python 3.14 virtual environment...
    py -3.14 -m venv .venv >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.14 was not found.
        >>"%LOG_FILE%" echo ERROR: Python 3.14 was not found.
        pause
        exit /b 1
    )
)

if not exist ".venv-tinvest\Scripts\python.exe" (
    echo Creating T-Invest Python 3.12 virtual environment...
    >>"%LOG_FILE%" echo Creating T-Invest Python 3.12 virtual environment...
    py -3.12 -m venv .venv-tinvest >>"%LOG_FILE%" 2>&1
    if errorlevel 1 (
        echo ERROR: Python 3.12 was not found.
        >>"%LOG_FILE%" echo ERROR: Python 3.12 was not found.
        pause
        exit /b 1
    )
)

echo Installing Edward...
echo.
>>"%LOG_FILE%" echo Installing Edward...
.venv\Scripts\python.exe -m pip install --upgrade pip >>"%LOG_FILE%" 2>&1
.venv\Scripts\python.exe -m pip install -e . >>"%LOG_FILE%" 2>&1
if errorlevel 1 goto :install_error

echo Checking T-Invest adapter...
>>"%LOG_FILE%" echo Checking T-Invest adapter...
.venv-tinvest\Scripts\python.exe -m pip install -r runtime\requirements.txt --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple >>"%LOG_FILE%" 2>&1
if errorlevel 1 goto :tinvest_error

echo Starting Edward GUI...
>>"%LOG_FILE%" echo Starting Edward GUI...
echo Live launcher output will be written to the log file.
>>"%LOG_FILE%" echo Starting Edward GUI...

.venv\Scripts\python.exe -m edward.ui.gui_launcher >>"%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%

if not "%EXIT_CODE%"=="0" (
    echo Edward GUI finished with error code %EXIT_CODE%.
    >>"%LOG_FILE%" echo Edward GUI finished with error code %EXIT_CODE%.
)

echo.
echo ================= CONSOLE LOG =================
type "%LOG_FILE%"
echo ============== END CONSOLE LOG ==============
echo.
echo Log file: %LOG_FILE%
pause
exit /b %EXIT_CODE%

:install_error
echo ERROR: Failed to install Edward dependencies.
>>"%LOG_FILE%" echo ERROR: Failed to install Edward dependencies.
echo.
echo ================= CONSOLE LOG =================
type "%LOG_FILE%"
echo ============== END CONSOLE LOG ==============
pause
exit /b 1

:tinvest_error
echo ERROR: Failed to install or validate T-Invest SDK.
>>"%LOG_FILE%" echo ERROR: Failed to install or validate T-Invest SDK.
echo.
echo ================= CONSOLE LOG =================
type "%LOG_FILE%"
echo ============== END CONSOLE LOG ==============
pause
exit /b 1
