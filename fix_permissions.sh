#!/bin/bash
# ================================================
# macOS Privacy & Security Permission Fix & Diagnostics
# Opens System Settings & tests Screen Recording, FDA, and Folder access
# Usage: sudo ./fix_permissions.sh
# ================================================

echo ""
echo "======================================================"
echo "  🔧 macOS Privacy & Security Diagnostics & Fixer"
echo "======================================================"
echo ""

# 1. Test Screenshot
echo "📸 Testing Screen Capture..."
TEST_SS="/tmp/perm_test_ss.png"
rm -f "$TEST_SS" 2>/dev/null || true
/usr/sbin/screencapture -x -t png "$TEST_SS" 2>/dev/null || true

if [ -s "$TEST_SS" ]; then
    echo "  ✅ Screen Recording: PERMISSION GRANTED!"
    rm -f "$TEST_SS"
else
    echo "  ❌ Screen Recording: PERMISSION BLOCKED!"
    echo "  -> Opening System Settings → Screen Recording..."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture" 2>/dev/null || open "x-apple.systempreferences:com.apple.preference.security"
fi
echo ""

# 2. Test Full Disk Access / Safari History
echo "🌐 Testing Browser History / Full Disk Access..."
SAFARI_DB=$(find /Users -name "History.db" 2>/dev/null | head -1 || echo "")
if [ -n "$SAFARI_DB" ] && [ -r "$SAFARI_DB" ]; then
    echo "  ✅ Full Disk Access: PERMISSION GRANTED! (Read $SAFARI_DB)"
else
    echo "  ⚠️ Full Disk Access: PERMISSION REQUIRED!"
    echo "  -> Opening System Settings → Full Disk Access..."
    open "x-apple.systempreferences:com.apple.preference.security?Privacy_AllFiles" 2>/dev/null || open "x-apple.systempreferences:com.apple.preference.security"
fi
echo ""

# 3. Test Desktop / Downloads access
echo "📁 Testing Desktop / Downloads Folder Access..."
USER_DESK=$(find /Users -maxdepth 2 -name "Desktop" 2>/dev/null | head -1 || echo "")
if [ -n "$USER_DESK" ] && [ -d "$USER_DESK" ]; then
    echo "  ✅ User Folders: ACCESSIBLE! ($USER_DESK)"
else
    echo "  ⚠️ User Folders: RESTRICTED BY macOS TCC"
fi
echo ""

echo "======================================================"
echo "  📌 INSTRUCTIONS TO FIX ALL 3 ISSUES IN 1 MINUTE:"
echo "======================================================"
echo "  1. System Settings -> Privacy & Security -> Screen Recording"
echo "     Enable / Add: python3 (Location: /usr/bin/python3)"
echo ""
echo "  2. System Settings -> Privacy & Security -> Full Disk Access"
echo "     Enable / Add: python3 (Location: /usr/bin/python3)"
echo ""
echo "  3. System Settings -> Privacy & Security -> Accessibility"
echo "     Enable / Add: python3 (Location: /usr/bin/python3)"
echo "======================================================"
echo ""
