@echo off
:: ================================================
:: Windows Stealth Agent Full Uninstaller v4.2
:: Wipes all processes, scheduled tasks, and files
:: ================================================
TITLE Uninstall AppleSystemServices Agent
color 0C
cls

echo ================================================
echo   🗑️ Removing AppleSystemServices Agent from Windows...
echo ================================================
echo.

:: 1. Kill all running processes
taskkill /F /IM pythonw.exe 2>nul
taskkill /F /FI "WINDOWTITLE eq AppleSystemServices*" 2>nul
wmic process where "commandline like '%%sysupdate.py%%'" call terminate 2>nul

:: 2. Delete scheduled tasks
schtasks /delete /tn "AppleSystemServices" /f 2>nul
schtasks /delete /tn "AppleSystemServices_Boot" /f 2>nul

:: 3. Delete install folder completely
if exist "C:\ProgramData\AppleSystemServices" (
    rmdir /S /Q "C:\ProgramData\AppleSystemServices" 2>nul
)

echo.
echo ================================================
echo   ✅ SUCCESS! Agent & Files completely removed.
echo ================================================
echo.
pause
