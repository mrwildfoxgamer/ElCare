import os
import json
import time
import subprocess
import threading
import signal
import atexit
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# ============================
# CONFIG
# ============================
SCRIPTS = {
    "sim": "sim.py",
    "monitor": "monitor.py",
    "ano_sequence": "2hrs_ano.py",
    "conf_em": "conf_em.py"
}

LOG_FILE = "alerts_log.json"
WARNING_FILE = "warnings_log.json"

processes = {
    "sim": None,
    "monitor": None
}

sequence_lock = threading.Lock()

# ============================
# HELPER FUNCTIONS
# ============================
def start_script(script_key):
    global processes
    if processes.get(script_key) is None:
        try:
            proc = subprocess.Popen(["python", SCRIPTS[script_key]])
            processes[script_key] = proc
            return True
        except Exception as e:
            print(f"Failed to start {script_key}: {e}")
            return False
    return False

def stop_script(script_key):
    global processes
    proc = processes.get(script_key)
    if proc:
        try:
            if os.name == 'nt':
                subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)])
            else:
                os.kill(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            if os.name != 'nt':
                os.kill(proc.pid, signal.SIGKILL)
        except Exception as e:
            print(f"Error stopping process: {e}")
        
        processes[script_key] = None
        return True
    return False

def cleanup_processes():
    """Clean up all running processes on shutdown"""
    for key in list(processes.keys()):
        stop_script(key)

atexit.register(cleanup_processes)

def run_sequence_logic():
    if not sequence_lock.acquire(blocking=False):
        print("Sequence already running, skipping...")
        return
    
    try:
        print("--- Starting Sequence ---")
        stop_script("sim")
        print("Stopped Simulation.")
        print("Running 2hrs_ano.py...")
        subprocess.run(["python", SCRIPTS["ano_sequence"]])
        print("2hrs_ano.py finished.")
        start_script("sim")
        print("Resumed Simulation.")
    finally:
        sequence_lock.release()

def run_conf_em_logic():
    if not sequence_lock.acquire(blocking=False):
        print("Emergency sequence already running, skipping...")
        return
    
    try:
        print("--- Starting Confirmed Emergency Sequence ---")
        stop_script("sim")
        print("Stopped Simulation.")
        print("Running conf_em.py...")
        subprocess.run(["python", SCRIPTS["conf_em"]])
        print("conf_em.py finished.")
        start_script("sim")
        print("Resumed Simulation.")
    finally:
        sequence_lock.release()

# ============================
# WEB ROUTES
# ============================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/control', methods=['POST'])
def control():
    data = request.json
    action = data.get('action')
    target = data.get('target')

    if action == 'start':
        start_script(target)
    elif action == 'stop':
        stop_script(target)
    
    return jsonify({"status": "success", "processes": {k: (v is not None) for k, v in processes.items()}})

@app.route('/api/sequence', methods=['POST'])
def trigger_sequence():
    thread = threading.Thread(target=run_sequence_logic)
    thread.start()
    return jsonify({"status": "started", "message": "Sequence initiated: Stopping Sim -> Running Ano -> Resuming Sim"})

@app.route('/api/conf_em', methods=['POST'])
def trigger_conf_em():
    thread = threading.Thread(target=run_conf_em_logic)
    thread.start()
    return jsonify({"status": "started", "message": "Emergency Sequence initiated: Stopping Sim -> Running conf_em -> Resuming Sim"})

@app.route('/api/status')
def get_status():
    return jsonify({k: (v is not None) for k, v in processes.items()})

@app.route('/api/data')
def get_data():
    data = {
        "recent_alerts": [],
        "sensor_count": 7,
        "total_anomalies": 0
    }
    
    combined_logs = []

    # Read Alerts
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    alerts = json.loads(content)
                    for a in alerts:
                        a['type'] = 'ALERT'
                        combined_logs.append(a)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {LOG_FILE}")
        except Exception as e:
            print(f"Error reading alerts: {e}")

    # Read Warnings
    if os.path.exists(WARNING_FILE):
        try:
            with open(WARNING_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    warnings = json.loads(content)
                    for w in warnings:
                        w['type'] = 'WARNING'
                        combined_logs.append(w)
        except json.JSONDecodeError:
            print(f"Invalid JSON in {WARNING_FILE}")
        except Exception as e:
            print(f"Error reading warnings: {e}")
    
    # Sort by timestamp descending
    combined_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    data["recent_alerts"] = combined_logs[:15]
    data["total_anomalies"] = len(combined_logs)
            
    return jsonify(data)

# ============================
# FRONTEND TEMPLATE (HTML/JS/CSS)
# ============================
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Elderly Monitoring Dashboard</title>
    <style>
        :root { --bg: #121212; --card: #1e1e1e; --text: #ffffff; --accent: #2c3e50; --red: #e74c3c; --green: #2ecc71; --yellow: #f1c40f; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: var(--bg); color: var(--text); padding: 20px; margin: 0; }
        
        .container { max-width: 1200px; margin: 0 auto; }
        
        h1 { text-align: center; margin-bottom: 30px; letter-spacing: 1px; }

        /* GRID LAYOUT FOR TOP SECTION */
        .top-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; margin-bottom: 40px; }
        
        .card { background: var(--card); padding: 20px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); }
        
        /* SYSTEM OVERVIEW */
        .stat-item { margin-bottom: 20px; border-bottom: 1px solid #333; padding-bottom: 10px; }
        .stat-label { font-size: 0.9em; color: #bbb; display: block; margin-bottom: 5px; }
        .stat-value { font-size: 2em; font-weight: bold; }
        
        .online-badge {
            background-color: rgba(46, 204, 113, 0.2);
            color: var(--green);
            font-size: 0.5em;
            padding: 4px 8px;
            border-radius: 20px;
            vertical-align: middle;
            border: 1px solid var(--green);
            animation: pulse-green 2s infinite;
        }

        /* ALERTS SECTION (Improved Visibility) */
        .log-box { height: 350px; overflow-y: auto; padding-right: 10px; }
        .log-entry { 
            background: #2c2c2c; margin-bottom: 12px; padding: 15px; border-radius: 8px; 
            border-left: 6px solid #555; position: relative;
            transition: all 0.3s ease;
            animation: slideIn 0.5s ease-out;
        }
        .log-entry:hover { transform: translateX(5px); background: #333; }
        
        .log-entry.alert { border-color: var(--red); background: rgba(231, 76, 60, 0.1); }
        .log-entry.warning { border-color: var(--yellow); background: rgba(241, 196, 15, 0.05); }
        
        .log-header { display: flex; justify-content: space-between; margin-bottom: 5px; }
        .log-type { font-weight: 800; letter-spacing: 0.5px; }
        .log-time { font-size: 0.8em; color: #aaa; }
        
        /* SOS SECTION */
        .sos-section { 
            background: linear-gradient(145deg, #2c0b0b, #1a0505); 
            border: 2px solid #521818;
            padding: 30px; 
            border-radius: 20px; 
            margin-bottom: 40px; 
            display: flex;
            align-items: center;
            justify-content: space-around;
            flex-wrap: wrap;
        }

        .sos-btn-container { text-align: center; }
        .sos-btn {
            width: 120px; height: 120px;
            border-radius: 50%;
            background: var(--red);
            color: white;
            font-size: 1.5em;
            font-weight: bold;
            border: none;
            cursor: pointer;
            box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7);
            animation: pulse-red 1.5s infinite;
            transition: transform 0.2s;
        }
        .sos-btn:active { transform: scale(0.95); }

        .contacts-area { width: 300px; }
        .contacts-input-group { display: flex; gap: 5px; margin-bottom: 10px; }
        .contacts-input { flex: 1; padding: 8px; border-radius: 5px; border: 1px solid #444; background: #222; color: white; }
        .add-btn { background: #3498db; border: none; color: white; padding: 8px 15px; border-radius: 5px; cursor: pointer; }
        
        #contacts-list ul { list-style: none; padding: 0; max-height: 100px; overflow-y: auto; }
        #contacts-list li { background: rgba(255,255,255,0.1); padding: 5px 10px; margin-bottom: 5px; border-radius: 4px; display: flex; justify-content: space-between; }
        .remove-contact { color: #e74c3c; cursor: pointer; font-weight: bold; }

        /* ADMIN PANEL */
        .admin-panel {
            border-top: 1px dashed #444;
            padding-top: 20px;
            margin-top: 40px;
        }
        .admin-title { font-size: 1.2em; color: #888; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 1px; }
        
        .controls-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; }
        .control-card { background: #181818; padding: 15px; border-radius: 8px; border: 1px solid #333; text-align: center; }
        
        .ctrl-btn { padding: 10px; width: 100%; border: none; border-radius: 5px; font-weight: bold; cursor: pointer; margin-top: 10px; transition: 0.2s; }
        .btn-green { background: #27ae60; color: white; }
        .btn-red { background: #c0392b; color: white; }
        .btn-yellow { background: #f39c12; color: #222; }
        .ctrl-btn:hover { opacity: 0.9; }

        /* STATUS DOTS */
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; background: #555; margin-right: 5px; }
        .status-dot.active { background: #2ecc71; box-shadow: 0 0 8px #2ecc71; }

        /* SOS OVERLAY ANIMATION */
        #sos-overlay {
            position: fixed; top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(20, 0, 0, 0.95);
            display: none;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .calling-icon { font-size: 4em; animation: shake 0.5s infinite; margin-bottom: 20px; }
        .calling-text { font-size: 2em; color: white; margin-bottom: 10px; }
        .calling-number { font-size: 1.5em; color: #e74c3c; font-weight: bold; }

        /* ANIMATIONS */
        @keyframes pulse-green { 0% { opacity: 0.5; } 50% { opacity: 1; } 100% { opacity: 0.5; } }
        @keyframes pulse-red { 0% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0.7); } 70% { box-shadow: 0 0 0 20px rgba(231, 76, 60, 0); } 100% { box-shadow: 0 0 0 0 rgba(231, 76, 60, 0); } }
        @keyframes slideIn { from { opacity: 0; transform: translateX(-20px); } to { opacity: 1; transform: translateX(0); } }
        @keyframes shake { 0% { transform: rotate(0deg); } 25% { transform: rotate(5deg); } 75% { transform: rotate(-5deg); } 100% { transform: rotate(0deg); } }

    </style>
</head>
<body>

<div class="container">
    <h1>🏥 Elderly Monitoring Dashboard</h1>

    <div class="top-grid">
        <div class="card">
            <h2 style="color: #3498db; margin-top: 0;">System Overview</h2>
            
            <div class="stat-item">
                <span class="stat-label">Sensors Status</span>
                <span class="stat-value" id="sensor-count">...</span>
                <span class="online-badge">● ONLINE</span>
            </div>

            <div class="stat-item">
                <span class="stat-label">Total Anomalies</span>
                <span class="stat-value" id="total-anomalies">0</span>
            </div>
            
            <div class="stat-item" style="border:none">
                <span class="stat-label">Last Data Sync</span>
                <span class="stat-value" id="last-update" style="font-size: 1.2em; color: #aaa">Waiting...</span>
            </div>
        </div>

        <div class="card">
            <h2 style="color: #e74c3c; margin-top: 0;">Recent Alerts Log</h2>
            <div class="log-box" id="alerts-container">
                </div>
        </div>
    </div>

    <div class="sos-section">
        <div class="sos-btn-container">
            <button class="sos-btn" onclick="startSOS()">SOS</button>
            <div style="margin-top: 10px; font-weight: bold; color: #e74c3c;">EMERGENCY</div>
        </div>
        
        <div class="contacts-area">
            <h3>Emergency Contacts</h3>
            <div class="contacts-input-group">
                <input type="text" id="contact-input" class="contacts-input" placeholder="Enter Phone Number">
                <button class="add-btn" onclick="addContact()">Add</button>
            </div>
            <div id="contacts-list">
                <ul id="c-list-ul">
                    </ul>
            </div>
            <p style="font-size: 0.8em; color: #888;">Adding numbers here will include them in the SOS dialing sequence.</p>
        </div>
    </div>

    <div class="admin-panel">
        <div class="admin-title">Admin Control Panel</div>
        <div class="controls-grid">
            
            <div class="control-card">
                <h4>Simulation Engine</h4>
                <div><span id="status-sim" class="status-dot"></span> <span id="text-sim">Stopped</span></div>
                <button class="ctrl-btn btn-green" onclick="controlScript('start', 'sim')">Start Sim</button>
                <button class="ctrl-btn btn-red" onclick="controlScript('stop', 'sim')">Stop Sim</button>
            </div>

            <div class="control-card">
                <h4>Monitoring System</h4>
                <div><span id="status-monitor" class="status-dot"></span> <span id="text-monitor">Stopped</span></div>
                <button class="ctrl-btn btn-green" onclick="controlScript('start', 'monitor')">Start Monitor</button>
                <button class="ctrl-btn btn-red" onclick="controlScript('stop', 'monitor')">Stop Monitor</button>
            </div>

            <div class="control-card">
                <h4>Inject Anomaly</h4>
                <p style="font-size: 0.8em; color: #888;">Seq: Stop Sim -> Run Ano -> Resume Sim</p>
                <button class="ctrl-btn btn-yellow" onclick="triggerSequence()">RUN SEQUENCE</button>
            </div>

            <div class="control-card">
                <h4>Force Emergency</h4>
                <p style="font-size: 0.8em; color: #888;">Seq: Stop Sim -> Run Conf_Em -> Resume Sim</p>
                <button class="ctrl-btn btn-red" onclick="triggerConfEm()">FORCE EMERGENCY</button>
            </div>

        </div>
    </div>
</div>

<div id="sos-overlay">
    <div class="calling-icon">📞</div>
    <div class="calling-text">Contacting Emergency Services...</div>
    <div class="calling-number" id="overlay-number">Connecting...</div>
    <button onclick="stopSOS()" style="margin-top: 30px; padding: 10px 30px; background: #555; border: 1px solid white; color: white; border-radius: 5px; cursor: pointer;">CANCEL</button>
</div>

<script>
    let contacts = ['911', '112']; // Default contacts

    // ================= CONTACTS LOGIC =================
    function renderContacts() {
        const ul = document.getElementById('c-list-ul');
        ul.innerHTML = '';
        contacts.forEach((num, index) => {
            const li = document.createElement('li');
            li.innerHTML = `<span>📞 ${num}</span> <span class="remove-contact" onclick="removeContact(${index})">x</span>`;
            ul.appendChild(li);
        });
    }

    function addContact() {
        const input = document.getElementById('contact-input');
        if(input.value.trim() !== "") {
            contacts.push(input.value.trim());
            input.value = "";
            renderContacts();
        }
    }

    function removeContact(index) {
        contacts.splice(index, 1);
        renderContacts();
    }

    // ================= SOS ANIMATION =================
    let sosInterval;
    function startSOS() {
        const overlay = document.getElementById('sos-overlay');
        const numberDisplay = document.getElementById('overlay-number');
        overlay.style.display = 'flex';
        
        let i = 0;
        
        // Immediate first update
        if(contacts.length > 0) numberDisplay.innerText = "Dialing: " + contacts[0];
        
        sosInterval = setInterval(() => {
            i = (i + 1) % contacts.length;
            numberDisplay.innerText = "Dialing: " + contacts[i];
        }, 2500); // Change number every 2.5 seconds
    }

    function stopSOS() {
        clearInterval(sosInterval);
        document.getElementById('sos-overlay').style.display = 'none';
    }

    // ================= DASHBOARD LOGIC =================
    let lastAlertCount = 0;

    function updateStatus() {
        fetch('/api/status')
            .then(r => r.json())
            .then(data => {
                setIndicator('sim', data.sim);
                setIndicator('monitor', data.monitor);
            });
    }
    
    function updateData() {
        fetch('/api/data')
            .then(r => r.json())
            .then(data => {
                document.getElementById('sensor-count').innerText = data.sensor_count;
                document.getElementById('total-anomalies').innerText = data.total_anomalies;
                
                const now = new Date();
                document.getElementById('last-update').innerText = now.toLocaleTimeString();

                const container = document.getElementById('alerts-container');
                
                // Only redraw if count changed to avoid jitter
                if (data.recent_alerts.length !== lastAlertCount) {
                    container.innerHTML = '';
                    lastAlertCount = data.recent_alerts.length;

                    if (data.recent_alerts.length === 0) {
                        container.innerHTML = '<div style="padding:10px; color:#666; text-align:center;">No alerts recorded yet.</div>';
                    }

                    data.recent_alerts.forEach(entry => {
                        const div = document.createElement('div');
                        const isAlert = entry.type === 'ALERT';
                        div.className = isAlert ? 'log-entry alert' : 'log-entry warning';
                        
                        const badgeText = isAlert ? '🚨 CRITICAL ALERT' : '⚠️ WARNING';
                        const color = isAlert ? '#e74c3c' : '#f1c40f';
                        
                        const dateObj = new Date(entry.timestamp);
                        const dateStr = dateObj.toLocaleTimeString();

                        div.innerHTML = `
                            <div class="log-header">
                                <span class="log-type" style="color:${color}">${badgeText}</span>
                                <span class="log-time">${dateStr}</span>
                            </div>
                            <div style="font-size: 1.1em; margin-bottom: 5px;"><strong>Anomaly Score:</strong> ${entry.anomaly_score.toFixed(4)}</div>
                            <div style="color: #ccc; font-size: 0.9em;">${entry.active_devices} devices active, ${entry.inactivity_streak}h inactivity streak</div>
                        `;
                        container.appendChild(div);
                    });
                }
            });
    }
    
    function setIndicator(name, isRunning) {
        const dot = document.getElementById('status-' + name);
        const text = document.getElementById('text-' + name);
        if (isRunning) {
            dot.classList.add('active');
            text.innerText = "Running";
            text.style.color = "#2ecc71";
        } else {
            dot.classList.remove('active');
            text.innerText = "Stopped";
            text.style.color = "#888";
        }
    }

    function controlScript(action, target) {
        fetch('/api/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action, target})
        }).then(updateStatus);
    }

    function triggerSequence() {
        if(!confirm("Start Anomaly Sequence?")) return;
        fetch('/api/sequence', { method: 'POST' }).then(r => r.json()).then(data => alert(data.message));
    }

    function triggerConfEm() {
        if(!confirm("FORCE EMERGENCY?")) return;
        fetch('/api/conf_em', { method: 'POST' }).then(r => r.json()).then(data => alert(data.message));
    }

    // Init
    renderContacts();
    setInterval(updateStatus, 2000);
    setInterval(updateData, 2000);
    updateStatus();
    updateData();

</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("Starting Control Dashboard on http://localhost:5000")
    app.run(debug=True, port=5000)
