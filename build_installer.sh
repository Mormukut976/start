#!/bin/bash
# ================================================
# EmployeeMonitor Agent .pkg Installer Builder v3.0
# Run this once to create agent installer.pkg
#
# Usage:
#   ./build_installer.sh                                    # Local-only agent
#   ./build_installer.sh http://192.168.1.100:5000           # Agent reports to local server
#   ./build_installer.sh https://your-app.onrender.com       # Agent reports to cloud server (RECOMMENDED)
# ================================================

set -e

APP_NAME="EmployeeMonitor"
PKG_NAME="EmployeeMonitor-Agent.pkg"
INSTALL_DIR="/Library/Application Support/EmployeeMonitor"
PLIST_DST="/Library/LaunchDaemons/com.employeemonitor.dashboard.plist"

# Optional: Central server URL from first argument
CENTRAL_SERVER="${1:-}"

echo ""
echo "================================================"
echo "  🔧 Building $APP_NAME Agent Installer..."
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
cp monitor.py "$PAYLOAD_DIR$INSTALL_DIR/"
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
    <string>com.employeemonitor.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Library/Application Support/EmployeeMonitor/monitor.py</string>
        <string>--server</string>
        <string>$CENTRAL_SERVER</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/employeemonitor.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/employeemonitor.err</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
PLIST
else
    # Local-only mode: no central server
    cat > "$PAYLOAD_DIR$PLIST_DST" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.employeemonitor.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Library/Application Support/EmployeeMonitor/monitor.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/var/log/employeemonitor.log</string>
    <key>StandardErrorPath</key>
    <string>/var/log/employeemonitor.err</string>
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

INSTALL_DIR="/Library/Application Support/EmployeeMonitor"
PLIST_PATH="/Library/LaunchDaemons/com.employeemonitor.dashboard.plist"

# Set correct permissions
chmod -R 755 "$INSTALL_DIR"
chmod 644 "$PLIST_PATH"
chown root:wheel "$PLIST_PATH"

# Install Python dependencies silently
/usr/bin/python3 -m pip install flask psutil requests \
    --quiet --break-system-packages 2>/dev/null || \
/usr/bin/python3 -m pip install flask psutil requests \
    --quiet 2>/dev/null || true

# Unload if already running (ignore errors)
launchctl unload "$PLIST_PATH" 2>/dev/null || true

# Load the daemon
launchctl load -w "$PLIST_PATH"

# Get IP for dashboard URL
IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost")

# Check if agent mode is configured
AGENT_SERVER=$(grep -A5 "ProgramArguments" "$PLIST_PATH" | grep "http" | sed 's/.*<string>//' | sed 's/<\/string>//' | head -1 || echo "")

echo ""
echo "======================================================"
echo "  ✅ EmployeeMonitor Agent Installed!"
echo "======================================================"
echo ""
if [ -n "$AGENT_SERVER" ]; then
    echo "  📡 Reporting to: $AGENT_SERVER"
    echo "  🌐 Local Dashboard: http://$IP:5001"
else
    echo "  🌐 Local Dashboard: http://$IP:5001"
    echo ""
    echo "  ℹ️  To connect to central server:"
    echo "  Edit: /Library/LaunchDaemons/com.employeemonitor.dashboard.plist"
    echo "  Add --server http://<central-ip>:5000"
fi
echo ""
echo "  ⚠️  GRANT PERMISSIONS in System Settings → Privacy & Security:"
echo "  1. Screen Recording → Add: python3 ✓"
echo "  2. Accessibility → Add: python3 ✓"
echo "  3. Full Disk Access → Add: python3 ✓"
echo ""
echo "======================================================"
exit 0
SCRIPT

chmod +x "$SCRIPTS_DIR/postinstall"

# -------- Build .pkg --------
echo "📦 Packaging..."

pkgbuild \
    --root "$PAYLOAD_DIR" \
    --scripts "$SCRIPTS_DIR" \
    --identifier "com.employeemonitor.dashboard" \
    --version "2.0" \
    --install-location "/" \
    "$PKG_NAME"

echo ""
echo "================================================"
echo "  ✅ Package created: $PKG_NAME"
echo ""
echo "  HOW TO DEPLOY on employee Macs:"
echo "  1. Copy $PKG_NAME to target Mac"
echo "  2. Double-click → Install"
echo "  3. Grant permissions in System Settings"
if [ -n "$CENTRAL_SERVER" ]; then
    echo "  4. Machine will auto-connect to: $CENTRAL_SERVER"
    echo "  5. Open $CENTRAL_SERVER to see the dashboard"
else
    echo "  4. Open http://<mac-ip>:5001 for local dashboard"
    echo "  5. Or add central server later in plist file"
fi
echo "================================================"
echo ""
