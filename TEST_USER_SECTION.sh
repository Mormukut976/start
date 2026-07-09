#!/bin/bash
# Test Script - User Section Display

echo "======================================"
echo "🧪 Testing User Section Display"
echo "======================================"
echo ""

cd ~/Downloads/ppp/app

# Kill old server if running
echo "1. Stopping old server (if running)..."
pkill -f "python3 server.py" 2>/dev/null
sleep 2

# Verify template has user section
echo "2. Verifying template file..."
if grep -q "userInfoBanner" templates/central_dashboard.html; then
    echo "   ✅ User section found in template"
else
    echo "   ❌ User section NOT found!"
    exit 1
fi

# Start server
echo ""
echo "3. Starting Central Server..."
echo ""
python3 server.py &
SERVER_PID=$!
sleep 3

echo ""
echo "======================================"
echo "✅ Server Started (PID: $SERVER_PID)"
echo "======================================"
echo ""
echo "🌐 Open in browser:"
echo "   http://localhost:5000"
echo ""
echo "📋 What to check:"
echo "   1. Top bar shows: 👥 User: dropdown"
echo "   2. Select a user from dropdown"
echo "   3. Big blue banner should appear with:"
echo "      - User icon (circle)"
echo "      - User name in big text"
echo "      - Status: 🟢 ONLINE or 🔴 OFFLINE"
echo "      - Last Seen"
echo "      - Machine ID"
echo ""
echo "🔧 If not visible:"
echo "   - Hard refresh: Cmd+Shift+R (Mac)"
echo "   - Or clear browser cache"
echo ""
echo "🛑 To stop server:"
echo "   kill $SERVER_PID"
echo ""
echo "======================================"
