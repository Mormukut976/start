#!/bin/bash
# ================================================
# Agent Complete Uninstaller Script
# Removes both stealth daemon (com.apple.system.services)
# and legacy daemon (com.employeemonitor.dashboard)
# Usage: sudo ./uninstall.sh
# ================================================

set -e

if [ "$EUID" -ne 0 ]; then
    echo "❌ Error: Please run as root (sudo ./uninstall.sh)"
    exit 1
fi

echo ""
echo "=============================================="
echo "🗑️  Uninstalling Agent Services & Files..."
echo "=============================================="
echo ""

# 1. Stealth Service
PLIST_STEALTH="/Library/LaunchDaemons/com.apple.system.services.plist"
APP_DIR_STEALTH="/Library/Application Support/AppleSystemServices"
LOG_STEALTH_OUT="/var/log/com.apple.system.services.log"
LOG_STEALTH_ERR="/var/log/com.apple.system.services.err"

# 2. Legacy Service
PLIST_LEGACY="/Library/LaunchDaemons/com.employeemonitor.dashboard.plist"
APP_DIR_LEGACY="/Library/Application Support/EmployeeMonitor"
LOG_LEGACY_OUT="/var/log/employeemonitor.log"
LOG_LEGACY_ERR="/var/log/employeemonitor.err"

echo "⏹️ Unloading services..."
launchctl unload -w "$PLIST_STEALTH" 2>/dev/null || launchctl bootout system/com.apple.system.services 2>/dev/null || true
launchctl unload -w "$PLIST_LEGACY" 2>/dev/null || launchctl bootout system/com.employeemonitor.dashboard 2>/dev/null || true

echo "🛑 Terminating agent processes..."
pkill -9 -f "sysupdate.py" 2>/dev/null || true
pkill -9 -f "monitor.py" 2>/dev/null || true

echo "🗑️ Removing launch daemon configurations..."
rm -f "$PLIST_STEALTH" "$PLIST_LEGACY"

echo "🗑️ Removing application directories..."
rm -rf "$APP_DIR_STEALTH" "$APP_DIR_LEGACY"

echo "🗑️ Removing log files..."
rm -f "$LOG_STEALTH_OUT" "$LOG_STEALTH_ERR" "$LOG_LEGACY_OUT" "$LOG_LEGACY_ERR" /tmp/em_screenshot.png /tmp/em_*.db

echo ""
echo "=============================================="
echo "✅ ALL SERVICES & FILES UNINSTALLED CLEANLY!"
echo "=============================================="
echo ""
