#!/bin/bash
# Post-install script

echo "🔧 Installing Employee Monitor..."

# Copy main app
mkdir -p "/Library/Application Support/EmployeeMonitor"
cp -R "$1/../app/monitor.py" "/Library/Application Support/EmployeeMonitor/"
cp -R "$1/../app/templates" "/Library/Application Support/EmployeeMonitor/"

# Set permissions
chmod +x "/Library/Application Support/EmployeeMonitor/monitor.py"

# Copy launch daemon
cp "$1/../app/launch.plist" "/Library/LaunchDaemons/com.employeemonitor.dashboard.plist"

# Load launch daemon
launchctl load "/Library/LaunchDaemons/com.employeemonitor.dashboard.plist"

# Grant permissions via TCC (Privacy settings)
# Note: User must manually approve in System Settings > Privacy

echo ""
echo "=============================================="
echo "✅ EMPLOYEE MONITOR INSTALLED SUCCESSFULLY!"
echo "=============================================="
echo ""
echo "📌 IMPORTANT:"
echo "1. Go to System Settings > Privacy & Security"
echo "2. Enable Screen Recording for Terminal"
echo "3. Enable Accessibility for Terminal"
echo "4. Enable Full Disk Access for Terminal"
echo ""
echo "🌐 Dashboard URL: http://$(hostname).local:5000"
echo "📱 Access from your MacBook Air"
echo "=============================================="
