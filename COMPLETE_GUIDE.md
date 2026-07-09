# 🚀 Complete Installation Guide — EmployeeMonitor Multi-Machine Dashboard

## 📋 Overview

**Architecture:**
- **Central Server** (1 Mac) — Shows ALL machines in one dashboard
- **Agents** (Multiple Macs) — Silently collect & send data to server

**Ports:**
- Server: `5000` (central dashboard)
- Agent: `5001` (local dashboard)

---

## SETUP 1: Central Server (Main Mac)

Ye woh Mac hai jahan se tum sabhi machines ko monitor karoge.

### Install & Start

```bash
cd ~/Downloads/ppp/app

# Install dependencies
pip3 install flask psutil requests --break-system-packages

# Start server
python3 server.py
```

**Output:**
```
🖥️  Central Monitoring Server Started
🌐 Dashboard: http://0.0.0.0:5000
```

### Access Dashboard

```
http://<server-mac-ip>:5000
```

**Note:** Abhi dropdown empty hoga. Agents connect hone ke baad machines dikhengi.

### Keep Server Running (Optional)

Background mein server chalane ke liye screen ya tmux use karo:

```bash
# Using screen
screen -S monitor
python3 server.py
# Press Ctrl+A then D to detach

# Re-attach later
screen -r monitor
```

Ya startup pe auto-run ke liye launchd service banao (advanced).

---

## SETUP 2: Agent Installation (Employee Macs)

### Method A: With Central Server (Recommended)

Agar tumhe pata hai central server ka IP, to seedha installer banao:

```bash
cd ~/Downloads/ppp/app

# Build installer with server URL
./build_installer.sh http://192.168.1.100:5000
```

Replace `192.168.1.100` with your actual central server IP.

**Output:** `EmployeeMonitor-Agent.pkg`

---

### Method B: Local-Only (Manual Connect Later)

Pehle simple installer banao, baad mein manually server add karo:

```bash
cd ~/Downloads/ppp/app
./build_installer.sh
```

---

### Deploy on Target Macs

1. **Copy** `EmployeeMonitor-Agent.pkg` to employee Mac
2. **Double-click** → Install
3. Enter **admin password**

---

### Grant Permissions ⚠️ (IMPORTANT)

Installation ke baad ye permissions deni zaroori hai:

**System Settings → Privacy & Security**

| Permission | Location | Add |
|-----------|----------|-----|
| **Screen Recording** | Privacy & Security → Screen Recording | ✓ `python3` |
| **Accessibility** | Privacy & Security → Accessibility | ✓ `python3` |
| **Full Disk Access** | Privacy & Security → Full Disk Access | ✓ `python3` |

**How to add python3:**
1. Click `+` button
2. Press `Cmd+Shift+G`
3. Type: `/usr/bin/python3`
4. Click **Open**

---

### Connect to Central Server (If not done during install)

Agar Method B use kiya hai, to manually server add karo:

```bash
sudo nano /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

`ProgramArguments` section edit karo:

**Before:**
```xml
<array>
    <string>/usr/bin/python3</string>
    <string>/Library/Application Support/EmployeeMonitor/monitor.py</string>
</array>
```

**After:**
```xml
<array>
    <string>/usr/bin/python3</string>
    <string>/Library/Application Support/EmployeeMonitor/monitor.py</string>
    <string>--server</string>
    <string>http://192.168.1.100:5000</string>  <!-- Central server IP -->
</array>
```

**Save:** `Ctrl+O` → `Enter` → `Ctrl+X`

**Restart agent:**
```bash
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

---

## ✅ Verification

### 1. Check if agent is running

```bash
launchctl list | grep employeemonitor
```

Should show PID (process ID).

### 2. Check logs

```bash
tail -f /var/log/employeemonitor.log
```

Should show:
```
Agent mode: reporting to http://...
Registered with central server
```

### 3. Check central dashboard

Open: `http://<server-ip>:5000`

Dropdown mein employee Mac ka naam dikhai dena chahiye!

---

## 🌐 Access Dashboards

| Dashboard | URL | Shows |
|-----------|-----|-------|
| **Central (All Machines)** | `http://<server-ip>:5000` | Multi-machine selector |
| **Agent Local** | `http://<agent-ip>:5001` | Single machine data |

---

## 🔧 Agent Management

### Start Agent
```bash
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

### Stop Agent
```bash
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

### Restart Agent
```bash
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

### View Real-time Logs
```bash
tail -f /var/log/employeemonitor.log
```

### View Error Logs
```bash
tail -f /var/log/employeemonitor.err
```

---

## 🔥 Troubleshooting

### Machine not appearing in dropdown?

**Check:**
1. Agent running? `launchctl list | grep employeemonitor`
2. Server URL correct in plist? `cat /Library/LaunchDaemons/com.employeemonitor.dashboard.plist`
3. Network connectivity? `ping <server-ip>`
4. Server running? Check server Mac terminal

**Fix:**
```bash
# Check agent logs
tail -20 /var/log/employeemonitor.log

# Restart agent
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

---

### Screenshot not showing?

**Fix:**
1. System Settings → Privacy & Security → **Screen Recording**
2. Add `python3` (use `/usr/bin/python3`)
3. Restart agent

---

### Browser history empty?

**Fix:**
1. System Settings → Privacy & Security → **Full Disk Access**
2. Add `python3`
3. Restart agent

---

### Agent not starting at boot?

**Fix:**
```bash
sudo launchctl load -w /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

The `-w` flag enables persistence across reboots.

---

### Central server dashboard shows "Machine offline"?

Agent ke saath kuch problem hai:

```bash
# On agent Mac, check if it's running
launchctl list | grep employeemonitor

# Check logs
tail -20 /var/log/employeemonitor.log

# Look for connection errors
grep -i "error\|failed" /var/log/employeemonitor.log
```

---

## 🗑️ Uninstallation

### Remove Agent

```bash
# Stop the agent
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist

# Delete files
sudo rm /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo rm -rf "/Library/Application Support/EmployeeMonitor"

# Optional: remove logs
sudo rm /var/log/employeemonitor.log
sudo rm /var/log/employeemonitor.err
```

### Stop Central Server

```bash
# If running in terminal, press Ctrl+C
# If using screen:
screen -r monitor
# Press Ctrl+C
```

---

## 📊 What Data is Collected?

| Data Type | Frequency | Details |
|-----------|-----------|---------|
| System Info | 10 sec | CPU, RAM, Disk, Uptime, IP |
| Active Window | 10 sec | Currently focused application |
| Screenshot | 15 sec | Desktop screenshot |
| Browser History | 30 sec | Safari, Chrome, Firefox (last 30 entries) |
| Processes | 15 sec | Running processes with CPU/RAM usage |
| Recent Files | 60 sec | Files modified in last 3 days (Desktop/Documents/Downloads) |
| Network | 15 sec | Active connections, bytes sent/received |
| Installed Apps | 5 min | Apps in /Applications |

---

## 🔐 Security Notes

- **Data stored in memory** on central server (not persistent database)
- **Machines removed** after 24 hours of inactivity
- **Screenshots stored** in `/var/lib/centralmonitor/` or `~/.centralmonitor/`
- **No internet connection** needed - works on local network
- **No encryption** - use VPN if accessing over internet

---

## 🌍 Access from Internet (Optional)

### Option 1: Port Forwarding

1. Router settings mein jao
2. Port forwarding setup karo:
   - External Port: `5000`
   - Internal IP: `<server-mac-ip>`
   - Internal Port: `5000`
3. Access via: `http://<your-public-ip>:5000`

### Option 2: Ngrok (Easiest)

```bash
# Install ngrok
brew install ngrok

# Run ngrok
ngrok http 5000
```

Output mein `https://xyz.ngrok.io` URL milega - ye kisi ko bhi share kar sakte ho!

---

## 📞 Support

**Check logs first:**
```bash
# Agent logs
tail -50 /var/log/employeemonitor.log

# Server logs (in terminal where server is running)
# Or if logged to file:
tail -50 /var/log/centralmonitor.log
```

**Common issues:**
- Permissions not granted → Screenshots/history won't work
- Wrong server IP in plist → Machine won't appear in dropdown
- Firewall blocking → Can't connect to server
- Agent not running → `launchctl load` command se start karo

---

**Enjoy your multi-machine monitoring dashboard! 🎉**
