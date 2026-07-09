#!/usr/bin/env python3
"""
EmployeeMonitor Agent v3.0 (Cloud-Compatible)
- Runs on each employee Mac
- Sends all data to Central Server (local or cloud)
- Polls server for remote commands (no direct connection needed)
- Also provides local dashboard on port 5001

Usage:
  python3 monitor.py                                              # Local only
  python3 monitor.py --server http://192.168.1.100:5000           # Local server
  python3 monitor.py --server https://your-app.onrender.com       # Cloud server
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
from datetime import datetime

# ==================== LOG SETUP ====================
LOG_PATH = '/var/log/employeemonitor.log'
if not os.access('/var/log', os.W_OK):
    LOG_PATH = '/tmp/employeemonitor.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(LOG_PATH)]
)
log = logging.getLogger("monitor")

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
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install",
             "flask", "psutil", "requests",
             "--quiet", "--break-system-packages"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
ensure_deps()

import psutil
from flask import Flask, render_template, jsonify, request, send_file
import requests as req_lib

# ==================== TEMPLATE DIR ====================
TEMPLATE_DIR = '/Library/Application Support/EmployeeMonitor/templates'
if not os.path.exists(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ==================== MACHINE ID ====================
def get_machine_id():
    hostname = platform.node().replace(' ', '_').lower()
    # Remove special chars
    import re
    hostname = re.sub(r'[^a-z0-9_\-]', '', hostname)
    return hostname or 'unknown_mac'

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
        disk = psutil.disk_usage('/')
        uptime_sec = time.time() - psutil.boot_time()
        hours = int(uptime_sec // 3600)
        minutes = int((uptime_sec % 3600) // 60)
        return {
            "hostname": platform.node(),
            "os": platform.system() + " " + platform.mac_ver()[0],
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
        path = "/tmp/em_screenshot.png"
        subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-t", "png", path],
            check=True, timeout=8,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return path if os.path.exists(path) else None
    except Exception as e:
        log.warning(f"screenshot error: {e}")
        return None

# ==================== ACTIVE WINDOW ====================
def get_active_window():
    try:
        script = 'tell application "System Events" to get name of first process whose frontmost is true'
        result = subprocess.check_output(
            ["osascript", "-e", script],
            stderr=subprocess.DEVNULL, timeout=5
        ).decode().strip()
        return result
    except:
        return "Unknown"

# ==================== BROWSER HISTORY ====================
def get_browser_history():
    history = []

    # Safari
    safari_path = os.path.expanduser("~/Library/Safari/History.db")
    if os.path.exists(safari_path):
        try:
            tmp = "/tmp/em_safari.db"
            shutil.copy2(safari_path, tmp)
            conn = sqlite3.connect(tmp)
            c = conn.cursor()
            c.execute("""
                SELECT i.url, v.title
                FROM history_visits v
                JOIN history_items i ON v.history_item = i.id
                ORDER BY v.visit_time DESC LIMIT 30
            """)
            for row in c.fetchall():
                history.append({"browser": "Safari", "url": row[0], "title": row[1] or row[0]})
            conn.close()
            os.remove(tmp)
        except Exception as e:
            log.debug(f"Safari history: {e}")

    # Chrome
    chrome_path = os.path.expanduser("~/Library/Application Support/Google/Chrome/Default/History")
    if os.path.exists(chrome_path):
        try:
            tmp = "/tmp/em_chrome.db"
            shutil.copy2(chrome_path, tmp)
            conn = sqlite3.connect(tmp)
            c = conn.cursor()
            c.execute("SELECT url, title FROM urls ORDER BY last_visit_time DESC LIMIT 30")
            for row in c.fetchall():
                history.append({"browser": "Chrome", "url": row[0], "title": row[1] or row[0]})
            conn.close()
            os.remove(tmp)
        except Exception as e:
            log.debug(f"Chrome history: {e}")

    # Firefox
    ff_base = os.path.expanduser("~/Library/Application Support/Firefox/Profiles/")
    if os.path.exists(ff_base):
        try:
            for profile in os.listdir(ff_base):
                places = os.path.join(ff_base, profile, "places.sqlite")
                if os.path.exists(places):
                    tmp = "/tmp/em_firefox.db"
                    shutil.copy2(places, tmp)
                    conn = sqlite3.connect(tmp)
                    c = conn.cursor()
                    c.execute("SELECT url, title FROM moz_places ORDER BY last_visit_date DESC LIMIT 30")
                    for row in c.fetchall():
                        history.append({"browser": "Firefox", "url": row[0], "title": row[1] or row[0]})
                    conn.close()
                    os.remove(tmp)
                    break
        except Exception as e:
            log.debug(f"Firefox history: {e}")

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
        dirs = [
            os.path.expanduser("~/Desktop"),
            os.path.expanduser("~/Documents"),
            os.path.expanduser("~/Downloads")
        ]
        # Only include dirs that exist
        dirs = [d for d in dirs if os.path.exists(d)]
        result = subprocess.check_output(
            ["find"] + dirs + ["-type", "f", "-mtime", "-3", "-not", "-path", "*/.*"],
            stderr=subprocess.DEVNULL, timeout=10
        ).decode().strip().split('\n')
        files = [f for f in result if f.strip()]
        files.sort(key=lambda f: os.path.getmtime(f) if os.path.exists(f) else 0, reverse=True)
        return files[:40]
    except:
        return []

# ==================== INSTALLED APPS ====================
def get_installed_apps():
    apps = []
    dirs = ["/Applications", "/System/Applications", os.path.expanduser("~/Applications")]
    for d in dirs:
        if os.path.exists(d):
            for a in os.listdir(d):
                if a.endswith(".app"):
                    apps.append(a.replace(".app", ""))
    return sorted(list(set(apps)))[:100]

# ==================== NETWORK ====================
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

# ==================== LOCAL COMMAND EXECUTION ====================
def execute_command(cmd):
    BLOCKED = ['rm -rf /', 'mkfs', 'dd if=', ':(){:|:&};:']
    for b in BLOCKED:
        if b in cmd:
            return {"success": False, "error": "Command blocked"}
    try:
        result = subprocess.check_output(
            cmd, shell=True, stderr=subprocess.STDOUT, timeout=30
        )
        return {"success": True, "output": result.decode(errors='replace')}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Timed out"}
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
    for attempt in range(5):  # Retry 5 times
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
            # Poll for pending command
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
                    
                    # Execute command
                    result = execute_command(command)
                    
                    # Send result back
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
        
        time.sleep(3)  # Poll every 3 seconds

# ==================== AGENT WORKER THREAD ====================
def agent_worker():
    if not CENTRAL_SERVER:
        return

    log.info(f"Agent worker starting → {CENTRAL_SERVER}")

    # Keep trying to register until success
    while not register_with_server():
        log.warning("Retrying registration in 15s...")
        time.sleep(15)

    # Send initial data immediately after registration
    log.info("Sending initial data to server...")
    try:
        send_to_server('info', get_system_info())
        send_to_server('active_window', {'active': get_active_window()})
        send_to_server('history', get_browser_history())
        send_to_server('processes', get_processes())
        send_to_server('files', get_recent_files())
        send_to_server('network', get_network_info())
        send_to_server('apps', get_installed_apps())
        log.info("✅ Initial data sent successfully")
    except Exception as e:
        log.error(f"Initial data send failed: {e}")

    loop_count = 0
    while True:
        try:
            # System info + active window — every 10s
            send_to_server('info', get_system_info())
            send_to_server('active_window', {'active': get_active_window()})

            # Screenshot + Processes + Network — every 20s
            if loop_count % 2 == 0:
                path = capture_screenshot()
                if path and os.path.exists(path):
                    with open(path, 'rb') as f:
                        send_to_server('screenshot', base64.b64encode(f.read()).decode())
                send_to_server('processes', get_processes())
                send_to_server('network', get_network_info())

            # Browser history — every 30s
            if loop_count % 3 == 0:
                send_to_server('history', get_browser_history())

            # Recent files — every 60s
            if loop_count % 6 == 0:
                send_to_server('files', get_recent_files())

            # Installed apps — every 5 min
            if loop_count % 30 == 0:
                send_to_server('apps', get_installed_apps())

            # Heartbeat every cycle
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
        print(f"  🖥️  EmployeeMonitor Agent v3.0 (Cloud-Ready)")
        print(f"{'='*55}")
        print(f"  🔑 Machine ID : {MACHINE_ID}")
        print(f"  🌐 Local Dashboard : http://{ip}:5001")
        if CENTRAL_SERVER:
            print(f"  📡 Reporting to : {CENTRAL_SERVER}")
        print(f"  📋 Logs : {LOG_PATH}")
        print(f"{'='*55}\n")

    log.info(f"Agent starting | Machine: {MACHINE_ID} | IP: {ip}")

    # Start agent thread if server specified
    if CENTRAL_SERVER:
        t = threading.Thread(target=agent_worker, daemon=True)
        t.start()
        
        # Start command poller thread
        cmd_t = threading.Thread(target=command_poller, daemon=True)
        cmd_t.start()

    app.run(
        host='0.0.0.0',
        port=5001,
        debug=False,
        threaded=True,
        use_reloader=False
    )
