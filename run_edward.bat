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

if not exist ".venv-tinvest\Scripts\python.exe" (
    echo Creating T-Invest Python 3.12 virtual environment...
    py -3.12 -m venv .venv-tinvest
    if errorlevel 1 (
        echo ERROR: Python 3.12 was not found.
        echo Install Python 3.12 x64 and try again.
        pause
        exit /b 1
    )
)

echo.
echo Checking Edward installation...
.venv\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :install_error
.venv\Scripts\python.exe -m pip install -e .
if errorlevel 1 goto :install_error

echo.
echo Checking T-Invest adapter installation...
.venv-tinvest\Scripts\python.exe -m pip install --upgrade pip
if errorlevel 1 goto :tinvest_error
.venv-tinvest\Scripts\python.exe -m pip install -r runtime\requirements.txt --extra-index-url https://opensource.tbank.ru/api/v4/projects/238/packages/pypi/simple
if errorlevel 1 goto :tinvest_error

.venv-tinvest\Scripts\python.exe -c "from t_tech.invest import Client; print('T-Invest SDK OK')"
if errorlevel 1 goto :tinvest_error

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
echo ERROR: Failed to install Edward dependencies.
pause
exit /b 1

:tinvest_error
echo.
echo ERROR: Failed to install or validate T-Invest SDK.
echo T-Invest SDK requires the dedicated Python 3.12 runtime.
pause
exit /b 1
