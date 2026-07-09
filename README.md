# 🖥️ EmployeeMonitor — Multi-Machine Central Dashboard

**2 Modes:**
1. **Central Server** - Ek jagah pe dashboard, sabhi machines ka data dikhaaye
2. **Agent** - Har employee Mac pe install karo, automatically central server ko data bhejega

---

## 📦 Files

```
app/
├── server.py               ← Central monitoring server
├── monitor.py              ← Agent (runs on each employee Mac)
├── launch.plist            ← Auto-start config for agent
├── build_installer.sh      ← Agent .pkg installer banane ka script
├── postinstall.sh          ← Package install ke baad chalta hai
└── templates/
    ├── dashboard.html          ← Local agent dashboard UI
    └── central_dashboard.html  ← Central multi-machine dashboard
```

---

## 🚀 Setup Guide

### STEP 1: Central Server Start Karo (Ek baar, tumhare main Mac pe)

Ye woh Mac hai jahan se tum **sabhi employees ka data ek jagah dekhoge**.

```bash
cd ~/Downloads/ppp/app

# Dependencies install karo
pip3 install flask psutil requests --break-system-packages

# Server start karo
python3 server.py
```

Server start hone ke baad terminal mein dikhega:
```
🖥️  Central Monitoring Server Started
🌐 Dashboard: http://0.0.0.0:5000
```

**Dashboard kholo:**
```
http://<tumhara-server-ip>:5000
```

Ab dropdown mein koi machine nahi hogi. Agents install karo toh dikhenga.

---

### STEP 2: Agent Install Karo (Har employee Mac pe)

#### 2a. .pkg Installer Banao (ek baar)

```bash
cd ~/Downloads/ppp/app
chmod +x build_installer.sh
./build_installer.sh
```

**Output:** `EmployeeMonitor-Installer.pkg` file ban jayegi

#### 2b. Target Mac Pe Install Karo

1. `EmployeeMonitor-Installer.pkg` ko target Mac pe copy karo (USB/AirDrop/email)
2. **Double-click** karo .pkg pe
3. Installer wizard follow karo → **Install**
4. Admin password daalo

#### 2c. Permissions Deni Hain ⚠️

**System Settings → Privacy & Security** mein yeh 3 cheezein enable karo:

| Permission | Kahan Milegi | Kya Add Karo |
|-----------|-------------|--------------|
| Screen Recording | Privacy & Security → Screen Recording | `python3` |
| Accessibility | Privacy & Security → Accessibility | `python3` |
| Full Disk Access | Privacy & Security → Full Disk Access | `python3` |

> 💡 `python3` add karne ke liye `+` dabao → `/usr/bin/python3` dhundho

#### 2d. Agent Ko Central Server Se Connect Karo

```bash
sudo nano /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

`ProgramArguments` section update karo — `--server` flag add karo:

```xml
<key>ProgramArguments</key>
<array>
    <string>/usr/bin/python3</string>
    <string>/Library/Application Support/EmployeeMonitor/monitor.py</string>
    <string>--server</string>
    <string>http://192.168.1.100:5000</string>
</array>
```

> ⚠️ `192.168.1.100` ki jagah apne **central server ka IP** daalo

**Save karo:** `Ctrl+O` → `Enter` → `Ctrl+X`

**Agent restart karo:**
```bash
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

---

### STEP 3: Done! Dashboard Kholo 🎉

Central server ke dashboard pe jao:
```
http://<server-ip>:5000
```

Dropdown mein employee ka Mac dikhai dega. Select karo aur monitor karo!

---

## 🌐 Access

| Dashboard | URL |
|-----------|-----|
| **Central (All Machines)** | `http://<server-ip>:5000` |
| **Agent Local** | `http://<agent-ip>:5001` |

**Internet se access ke liye:**
- Router pe port forwarding (5000 → server IP)
- Ya ngrok:
  ```bash
  brew install ngrok
  ngrok http 5000
  ```

---

## 🔧 Agent Control Karna

```bash
# Status check
launchctl list | grep employeemonitor

# Start
sudo launchctl load /Library/LaunchDaemons/com.employeemonitor.dashboard.plist

# Stop
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist

# Logs dekho
tail -f /var/log/employeemonitor.log
```

---

## 📊 Dashboard Features

| Feature | Description |
|---------|-------------|
| 📸 Live Screenshot | Har 8 second pe update |
| 🖥️ System Info | CPU, RAM, Disk, Uptime |
| 🌐 Browser History | Safari + Chrome + Firefox |
| 📱 Active Window | Kaunsa app use ho raha hai |
| ⚙️ Running Processes | CPU/Memory usage ke saath |
| 📁 Recent Files | Desktop/Documents/Downloads |
| 🔌 Network | Active connections |
| 🟢 Online Status | Har machine ka live status |

---

## ❓ Troubleshooting

**Machine dropdown mein nahi dikh rahi?**
- Agent chal raha hai? `launchctl list | grep employeemonitor`
- `--server` flag sahi IP hai?
- Central server chal raha hai? `python3 server.py`

**Screenshot nahi aa rahi?**
→ System Settings → Privacy → Screen Recording → python3 ✓

**Browser history nahi dikh rahi?**
→ System Settings → Privacy → Full Disk Access → python3 ✓

**Boot pe start nahi ho raha?**
```bash
sudo launchctl load -w /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
```

---

## 🗑️ Uninstall (Agent)

```bash
sudo launchctl unload /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo rm /Library/LaunchDaemons/com.employeemonitor.dashboard.plist
sudo rm -rf "/Library/Application Support/EmployeeMonitor"
```
