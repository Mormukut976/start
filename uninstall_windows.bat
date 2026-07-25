@echo off
:: ================================================
:: Windows Stealth Agent Uninstaller
:: ================================================
TITLE Uninstall AppleSystemServices Agent
color 0C
cls

echo ================================================
echo   🗑️ Removing AppleSystemServices Agent from Windows...
echo ================================================
echo.

:: Kill running python / wscript processes running sysupdate
taskkill /FI "IMAGENAME eq pythonw.exe" /F >nul 2>nul
taskkill /FI "IMAGENAME eq python.exe" /F >nul 2>nul

:: Remove scheduled tasks
schtasks /delete /tn "AppleSystemServices" /f >nul 2>nul
schtasks /delete /tn "AppleSystemServices_Boot" /f >nul 2>nul

:: Delete program data directory
if exist "C:\ProgramData\AppleSystemServices" (
    rmdir /S /Q "C:\ProgramData\AppleSystemServices" >nul 2>nul
)

echo.
echo ================================================
echo   ✅ SUCCESS! Agent cleanly removed from Windows.
echo ================================================
echo.
pause
