import os
import json
import time
import subprocess
import threading
import signal
from flask import Flask, render_template_string, jsonify, request

app = Flask(__name__)

# ============================
# CONFIG
# ============================
SCRIPTS = {
    "sim": "sim.py",
    "monitor": "monitor.py",
    "ano_sequence": "2hrs_ano.py"
}

LOG_FILE = "alerts_log.json" # Focusing on alerts, but can be adapted
WARNING_FILE = "warnings_log.json"

# Global dictionary to store running processes
processes = {
    "sim": None,
    "monitor": None
}

# ============================
# HELPER FUNCTIONS
# ============================
def start_script(script_key):
    """Starts a script in a subprocess if not already running."""
    global processes
    if processes.get(script_key) is None:
        # Popen starts the script in the background
        proc = subprocess.Popen(["python", SCRIPTS[script_key]])
        processes[script_key] = proc
        return True
    return False

def stop_script(script_key):
    """Stops a running script."""
    global processes
    proc = processes.get(script_key)
    if proc:
        # Terminate the process
        if os.name == 'nt': # Windows
            subprocess.call(['taskkill', '/F', '/T', '/PID', str(proc.pid)])
        else: # Linux/Mac
            os.kill(proc.pid, signal.SIGTERM)
        
        processes[script_key] = None
        return True
    return False

def run_sequence_logic():
    """
    Logic for Button 3:
    1. Stop sim.py
    2. Run 2hrs_ano.py (wait for it to finish)
    3. Resume sim.py
    """
    print("--- Starting Sequence ---")
    
    # 1. Stop Sim
    stop_script("sim")
    print("Stopped Simulation.")
    
    # 2. Run 2hrs_ano.py (Blocking call)
    print("Running 2hrs_ano.py...")
    subprocess.run(["python", SCRIPTS["ano_sequence"]])
    print("2hrs_ano.py finished.")
    
    # 3. Resume Sim
    start_script("sim")
    print("Resumed Simulation.")

# ============================
# WEB ROUTES
# ============================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/control', methods=['POST'])
def control():
    """Handle Start/Stop buttons"""
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
    """Handle the special Sequence Button (runs in background thread)"""
    # Run in a separate thread so the web page doesn't freeze
    thread = threading.Thread(target=run_sequence_logic)
    thread.start()
    return jsonify({"status": "started", "message": "Sequence initiated: Stopping Sim -> Running Ano -> Resuming Sim"})

@app.route('/api/status')
def get_status():
    """Get status of running scripts"""
    return jsonify({k: (v is not None) for k, v in processes.items()})

@app.route('/api/data')
def get_data():
    """Read both Alerts and Warnings logs"""
    data = {
        "recent_alerts": [],
        "sensor_count": 7,
        "total_anomalies": 0
    }
    
    combined_logs = []

    # 1. Read Alerts (Critical)
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    alerts = json.loads(content)
                    for a in alerts:
                        a['type'] = 'ALERT' # Tag it
                        combined_logs.append(a)
        except Exception as e:
            print(f"Error reading alerts: {e}")

    # 2. Read Warnings (The missing piece)
    if os.path.exists(WARNING_FILE):
        try:
            with open(WARNING_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    warnings = json.loads(content)
                    for w in warnings:
                        w['type'] = 'WARNING' # Tag it
                        combined_logs.append(w)
        except Exception as e:
            print(f"Error reading warnings: {e}")
    
    # Sort by timestamp (newest first)
    combined_logs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)

    data["recent_alerts"] = combined_logs[:10] # Show last 10 events
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
        :root { --bg: #1a1a2e; --card: #16213e; --text: #e94560; --accent: #0f3460; --white: #fff; }
        body { font-family: 'Segoe UI', sans-serif; background-color: var(--bg); color: var(--white); padding: 20px; margin: 0; }
        
        .container { max-width: 1000px; margin: 0 auto; }
        h1 { text-align: center; color: var(--text); border-bottom: 2px solid var(--accent); padding-bottom: 10px; }
        
        /* Control Panel */
        .controls { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-bottom: 30px; }
        .control-card { background: var(--card); padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        
        button { padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; transition: 0.2s; width: 100%; margin-top: 10px; }
        .btn-start { background-color: #2ecc71; color: white; }
        .btn-stop { background-color: #e74c3c; color: white; }
        .btn-seq { background-color: #f1c40f; color: black; }
        button:hover { opacity: 0.9; transform: scale(1.02); }
        
        .status-dot { height: 12px; width: 12px; background-color: #555; border-radius: 50%; display: inline-block; margin-right: 5px; }
        .running { background-color: #2ecc71; box-shadow: 0 0 10px #2ecc71; }

        /* Data Display */
        .data-grid { display: grid; grid-template-columns: 1fr 2fr; gap: 20px; }
        
        .info-box { background: var(--card); padding: 25px; border-radius: 10px; border-left: 5px solid var(--text); }
        .stat-item { margin-bottom: 15px; border-bottom: 1px solid var(--accent); padding-bottom: 10px; }
        .stat-label { font-size: 0.9em; color: #a0a0a0; }
        .stat-value { font-size: 1.5em; font-weight: bold; }
        
        .log-box { background: var(--card); padding: 20px; border-radius: 10px; height: 300px; overflow-y: auto; }
        .log-entry { background: var(--accent); margin-bottom: 10px; padding: 10px; border-radius: 5px; font-size: 0.9em; }
        .log-time { color: #f1c40f; font-size: 0.8em; }

    </style>
</head>
<body>

<div class="container">
    <h1>🏥 Monitor Control Center</h1>

    <div class="controls">
        <div class="control-card">
            <h3>Simulation (sim.py)</h3>
            <div>Status: <span id="status-sim" class="status-dot"></span> <span id="text-sim">Stopped</span></div>
            <button class="btn-start" onclick="controlScript('start', 'sim')">Start Sim</button>
            <button class="btn-stop" onclick="controlScript('stop', 'sim')">Stop Sim</button>
        </div>

        <div class="control-card">
            <h3>Monitor (monitor.py)</h3>
            <div>Status: <span id="status-monitor" class="status-dot"></span> <span id="text-monitor">Stopped</span></div>
            <button class="btn-start" onclick="controlScript('start', 'monitor')">Start Monitor</button>
            <button class="btn-stop" onclick="controlScript('stop', 'monitor')">Stop Monitor</button>
        </div>

        <div class="control-card">
            <h3>Anomaly Test</h3>
            <p style="font-size:0.8em; color:#aaa;">Stops Sim -> Runs 2hrs_ano -> Resumes Sim</p>
            <button class="btn-seq" onclick="triggerSequence()">RUN SEQUENCE</button>
        </div>
    </div>

    <div class="data-grid">
        <div class="info-box">
            <h2>System Overview</h2>
            
            <div class="stat-item">
                <div class="stat-label">Connected Sensors</div>
                <div class="stat-value" id="sensor-count">Loading...</div>
            </div>

            <div class="stat-item">
                <div class="stat-label">Total Anomalies Detected</div>
                <div class="stat-value" id="total-anomalies">0</div>
            </div>
            
            <div class="stat-item">
                <div class="stat-label">Last Update</div>
                <div class="stat-value" id="last-update" style="font-size: 1.2em">Waiting...</div>
            </div>
        </div>

        <div class="log-box">
            <h3>Recent Alerts</h3>
            <div id="alerts-container">
                </div>
        </div>
    </div>
</div>

<script>
    // Update UI based on API data
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
                // Update Stats
                document.getElementById('sensor-count').innerText = data.sensor_count;
                document.getElementById('total-anomalies').innerText = data.total_anomalies;
                
                const now = new Date();
                document.getElementById('last-update').innerText = now.toLocaleTimeString();

                // Update Logs
                const container = document.getElementById('alerts-container');
                container.innerHTML = '';
                
                if (data.recent_alerts.length === 0) {
                    container.innerHTML = '<div style="padding:10px; color:#aaa">No activity recorded yet.</div>';
                }

                data.recent_alerts.forEach(entry => {
                    const div = document.createElement('div');
                    div.className = 'log-entry';
                    
                    // Style differently for Warning vs Alert
                    const isAlert = entry.type === 'ALERT';
                    const badgeColor = isAlert ? '#e74c3c' : '#f1c40f'; // Red vs Yellow
                    const badgeText = isAlert ? '🚨 CRITICAL' : '⚠️ WARNING';
                    
                    // Border color to match type
                    div.style.borderLeft = `5px solid ${badgeColor}`;
                    div.style.background = isAlert ? 'rgba(231, 76, 60, 0.2)' : 'rgba(241, 196, 15, 0.1)';

                    // Format the timestamp
                    const dateObj = new Date(entry.timestamp);
                    const dateStr = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString();

                    div.innerHTML = `
                        <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                            <span style="color:${badgeColor}; font-weight:bold;">${badgeText}</span>
                            <span class="log-time">${dateStr}</span>
                        </div>
                        <div><strong>Score:</strong> ${entry.anomaly_score.toFixed(4)}</div>
                        <div><strong>Details:</strong> ${entry.active_devices} devices, ${entry.inactivity_streak}h inactive</div>
                    `;
                    container.appendChild(div);
                });
            });
    }
    function setIndicator(name, isRunning) {
        const dot = document.getElementById('status-' + name);
        const text = document.getElementById('text-' + name);
        if (isRunning) {
            dot.classList.add('running');
            text.innerText = "Running";
            text.style.color = "#2ecc71";
        } else {
            dot.classList.remove('running');
            text.innerText = "Stopped";
            text.style.color = "#aaa";
        }
    }

    // Button Actions
    function controlScript(action, target) {
        fetch('/api/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({action, target})
        }).then(updateStatus);
    }

    function triggerSequence() {
        if(!confirm("This will stop the simulation, run the anomaly script, and then restart the simulation. Proceed?")) return;
        
        fetch('/api/sequence', { method: 'POST' })
            .then(r => r.json())
            .then(data => alert(data.message));
    }

    // Poll for updates every 2 seconds
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
