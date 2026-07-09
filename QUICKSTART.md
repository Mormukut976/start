# 🚀 QUICK START — Multi-Machine Employee Monitor

Sabhi employees ki Macs ko ek central dashboard se monitor karo! 

---

## 📁 Files Created

```
app/
├── server.py                   ← Central server (multiple machines)
├── monitor.py                  ← Agent (runs on each Mac)
├── build_installer.sh          ← Build .pkg installer
├── templates/
│   ├── dashboard.html          ← Local agent UI
│   └── central_dashboard.html  ← Central multi-machine UI
├── README.md                   ← Complete documentation
└── COMPLETE_GUIDE.md           ← Detailed setup & troubleshooting
```

---

## ⚡ 3-STEP SETUP

### STEP 1: Start Central Server (Main Mac)

```bash
cd ~/Downloads/ppp/app
pip3 install flask psutil requests --break-system-packages
python3 server.py
```

Dashboard: **http://<your-ip>:5000**

---

### STEP 2: Build Agent Installer

**With server URL** (recommended):
```bash
./build_installer.sh http://192.168.1.100:5000
```

**Without server** (configure later):
```bash
./build_installer.sh
```

Output: `EmployeeMonitor-Agent.pkg`

---

### STEP 3: Install on Employee Macs

1. Copy `.pkg` to employee Mac
2. Double-click → Install
3. **Grant permissions:**
   - System Settings → Privacy & Security
   - Enable: Screen Recording, Accessibility, Full Disk Access
   - Add: `python3` (`/usr/bin/python3`)

---

## ✅ Done!

Central dashboard pe jao: **http://<server-ip>:5000**

Dropdown se koi bhi machine select karke monitor karo! 🎉

---

## 🎯 Features

✅ Multi-machine dropdown selector  
✅ Real-time screenshots (every 8s)  
✅ Browser history (Safari, Chrome, Firefox)  
✅ Active window tracking  
✅ CPU, RAM, Disk usage  
✅ Running processes  
✅ Recent files  
✅ Network connections  
✅ Online/offline status  
✅ Auto-reconnect on network issues  

---

## 📚 More Info

- **README.md** — Full documentation
- **COMPLETE_GUIDE.md** — Detailed setup & troubleshooting
- **Logs:** `/var/log/employeemonitor.log`

---

## 🔧 Commands

### Agent Control
```bash
# Status
launchctl list | grep employeemonitor

# Stop
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist

# Start
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist

# Logs
tail -f /var/log/employeemonitor.log
```

### Server
```bash
# Start
python3 server.py

# Background (with screen)
screen -S monitor
python3 server.py
# Ctrl+A then D to detach
```

---

## 🌐 Access

| Dashboard | URL | Purpose |
|-----------|-----|---------|
| **Central** | `http://<server-ip>:5000` | All machines |
| **Local Agent** | `http://<agent-ip>:5001` | Single machine |

---

## ❓ Issues?

**Machine not in dropdown?**
- Check agent running: `launchctl list | grep employeemonitor`
- Check server URL in: `/Library/LaunchDaemons/com.employeemonitor.dashboard.plist`
- Restart agent: `sudo launchctl unload ... && sudo launchctl load ...`

**Screenshot not working?**
- System Settings → Privacy → Screen Recording → Add `python3`

**History empty?**
- System Settings → Privacy → Full Disk Access → Add `python3`

**Full troubleshooting:** See `COMPLETE_GUIDE.md`

---

**Happy Monitoring! 🖥️📊**
