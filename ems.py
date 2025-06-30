from flask import Flask, render_template_string, jsonify, request
from gpiozero import OutputDevice
import threading
import time

app = Flask(__name__)

# GPIO Setup (BCM numbering)
RELAY_SOLAR = OutputDevice(17, active_high=False)  # IN1
RELAY_GRID = OutputDevice(18, active_high=False)   # IN2
RELAY_BATT = OutputDevice(27, active_high=False)   # IN3
RELAY_LOAD = OutputDevice(22, active_high=False)   # IN4

# System state
system_state = {
    "mode": "auto",
    "power_source": "battery",
    "battery_level": 85,
    "solar_available": False,
    "grid_available": True,
    "critical_load": True,
    "non_critical_load": True,
    "relay_status": {
        "solar": RELAY_SOLAR.value,
        "grid": RELAY_GRID.value,
        "battery": RELAY_BATT.value,
        "load": RELAY_LOAD.value
    }
}

# Simulated battery drain/charge thread
def simulate_system():
    while True:
        # Update relay status
        system_state["relay_status"] = {
            "solar": RELAY_SOLAR.value,
            "grid": RELAY_GRID.value,
            "battery": RELAY_BATT.value,
            "load": RELAY_LOAD.value
        }
        
        # Simulate battery changes
        if system_state["power_source"] == "solar" and system_state["solar_available"]:
            # Charging from solar
            system_state["battery_level"] = min(100, system_state["battery_level"] + 1)
        elif system_state["power_source"] == "grid" and system_state["grid_available"]:
            # Charging from grid
            system_state["battery_level"] = min(100, system_state["battery_level"] + 0.5)
        else:
            # Discharging
            system_state["battery_level"] = max(0, system_state["battery_level"] - 0.3)
        
        # Auto mode logic
        if system_state["mode"] == "auto":
            # Power source priority: Solar > Grid > Battery
            if system_state["solar_available"]:
                switch_to_solar()
            elif system_state["grid_available"]:
                switch_to_grid()
            else:
                switch_to_battery()
            
            # Load shedding when battery low
            if system_state["battery_level"] < 25:
                RELAY_LOAD.off()
                system_state["non_critical_load"] = False
            else:
                RELAY_LOAD.on()
                system_state["non_critical_load"] = True
        
        time.sleep(1)

# Power switching functions
def switch_to_solar():
    RELAY_SOLAR.on()
    RELAY_GRID.off()
    RELAY_BATT.off()
    system_state["power_source"] = "solar"

def switch_to_grid():
    RELAY_SOLAR.off()
    RELAY_GRID.on()
    RELAY_BATT.off()
    system_state["power_source"] = "grid"

def switch_to_battery():
    RELAY_SOLAR.off()
    RELAY_GRID.off()
    RELAY_BATT.on()
    system_state["power_source"] = "battery"

# Start simulation thread
sim_thread = threading.Thread(target=simulate_system, daemon=True)
sim_thread.start()

@app.route('/')
def dashboard():
    return render_template_string('''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Energy Management Prototype</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            body {
                background-color: #f0f8ff;
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            }
            .dashboard-card {
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                border-radius: 15px;
                margin-bottom: 20px;
                background: white;
            }
            .card-header {
                border-radius: 15px 15px 0 0 !important;
            }
            .power-source {
                transition: all 0.3s ease;
                border: 2px solid #dee2e6;
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 10px;
            }
            .power-source.active {
                border-color: #0d6efd;
                background-color: #e7f1ff;
                transform: scale(1.02);
                box-shadow: 0 0 10px rgba(13, 110, 253, 0.25);
            }
            .battery-indicator {
                height: 30px;
                background: linear-gradient(90deg, #dc3545, #ffc107, #28a745);
                border-radius: 15px;
                overflow: hidden;
                position: relative;
            }
            .battery-level {
                height: 100%;
                background-color: #0d6efd;
                width: 85%;
                border-radius: 15px;
                transition: width 0.5s ease;
            }
            .battery-label {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                font-weight: bold;
                color: white;
                text-shadow: 0 0 3px rgba(0,0,0,0.5);
            }
            .status-indicator {
                width: 20px;
                height: 20px;
                border-radius: 50%;
                display: inline-block;
                margin-right: 8px;
            }
            .status-on {
                background-color: #28a745;
                box-shadow: 0 0 8px rgba(40, 167, 69, 0.6);
            }
            .status-off {
                background-color: #dc3545;
            }
            .btn-mode {
                font-weight: bold;
                padding: 10px 20px;
            }
            .btn-mode.active {
                box-shadow: 0 0 0 0.25rem rgba(13, 110, 253, 0.25);
            }
            .simulation-control {
                cursor: pointer;
            }
            .simulation-control:hover {
                background-color: #f8f9fa;
            }
        </style>
    </head>
    <body>
        <div class="container py-4">
            <div class="text-center mb-4">
                <h1 class="display-4 text-primary">Energy Management Prototype</h1>
                <p class="lead">Using Power Bank as Battery & Phone Charger as Grid</p>
            </div>
            
            <!-- Status Panel -->
            <div class="dashboard-card card">
                <div class="card-header bg-primary text-white">
                    <h5 class="mb-0">System Status</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <!-- Operation Mode -->
                        <div class="col-md-4 mb-3">
                            <h5>Operation Mode</h5>
                            <div class="d-flex justify-content-between">
                                <button id="auto-btn" class="btn btn-outline-primary btn-mode w-50 me-2">AUTO</button>
                                <button id="manual-btn" class="btn btn-outline-secondary btn-mode w-50">MANUAL</button>
                            </div>
                        </div>
                        
                        <!-- Battery Status -->
                        <div class="col-md-4 mb-3">
                            <h5>Battery Level</h5>
                            <div class="battery-indicator mb-2">
                                <div id="battery-level" class="battery-level" style="width: 85%"></div>
                                <div id="battery-label" class="battery-label">85%</div>
                            </div>
                            <div id="battery-status" class="text-muted">Powered by: Battery</div>
                        </div>
                        
                        <!-- Load Status -->
                        <div class="col-md-4 mb-3">
                            <h5>Load Status</h5>
                            <div class="mb-2">
                                <span class="status-indicator status-on"></span>
                                <span id="critical-load">Critical Load: ON</span>
                            </div>
                            <div>
                                <span class="status-indicator status-on"></span>
                                <span id="non-critical-load">Non-Critical Load: ON</span>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Power Sources -->
                    <div class="row mt-4">
                        <div class="col-md-4">
                            <div id="solar-source" class="power-source">
                                <h4>Solar Power</h4>
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <span class="status-indicator status-off"></span>
                                        <span id="solar-status">Status: OFF</span>
                                    </div>
                                    <div id="solar-percent">0%</div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div id="grid-source" class="power-source">
                                <h4>Grid Power</h4>
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <span class="status-indicator status-off"></span>
                                        <span id="grid-status">Status: OFF</span>
                                    </div>
                                    <div id="grid-percent">100%</div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-4">
                            <div id="battery-source" class="power-source active">
                                <h4>Battery Power</h4>
                                <div class="d-flex justify-content-between align-items-center">
                                    <div>
                                        <span class="status-indicator status-on"></span>
                                        <span id="batt-status">Status: ON</span>
                                    </div>
                                    <div id="battery-percent">85%</div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Control Panel -->
            <div class="dashboard-card card">
                <div class="card-header bg-secondary text-white">
                    <h5 class="mb-0">Control Panel</h5>
                </div>
                <div class="card-body">
                    <!-- Relay Controls -->
                    <div class="row mb-4">
                        <div class="col-md-3 col-6 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5 class="card-title">Solar Relay</h5>
                                    <div class="form-check form-switch">
                                        <input class="form-check-input relay-switch" 
                                               type="checkbox" 
                                               data-relay="solar">
                                        <label class="form-check-label" id="solar-relay-status">OFF</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5 class="card-title">Grid Relay</h5>
                                    <div class="form-check form-switch">
                                        <input class="form-check-input relay-switch" 
                                               type="checkbox" 
                                               data-relay="grid">
                                        <label class="form-check-label" id="grid-relay-status">OFF</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5 class="card-title">Battery Relay</h5>
                                    <div class="form-check form-switch">
                                        <input class="form-check-input relay-switch" 
                                               type="checkbox" 
                                               data-relay="battery" checked>
                                        <label class="form-check-label" id="batt-relay-status">ON</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-3 col-6 mb-3">
                            <div class="card h-100">
                                <div class="card-body">
                                    <h5 class="card-title">Load Relay</h5>
                                    <div class="form-check form-switch">
                                        <input class="form-check-input relay-switch" 
                                               type="checkbox" 
                                               data-relay="load" checked>
                                        <label class="form-check-label" id="load-relay-status">ON</label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <!-- Simulation Controls -->
                    <div class="row">
                        <div class="col-md-6">
                            <div class="card simulation-control" id="toggle-solar">
                                <div class="card-body text-center">
                                    <h5>Solar Availability</h5>
                                    <div class="d-flex justify-content-center align-items-center">
                                        <div class="status-indicator status-off" id="solar-avail-indicator"></div>
                                        <span id="solar-avail-text">Not Available</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="card simulation-control" id="toggle-grid">
                                <div class="card-body text-center">
                                    <h5>Grid Availability</h5>
                                    <div class="d-flex justify-content-center align-items-center">
                                        <div class="status-indicator status-on" id="grid-avail-indicator"></div>
                                        <span id="grid-avail-text">Available</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Information Panel -->
            <div class="dashboard-card card">
                <div class="card-header bg-info text-white">
                    <h5 class="mb-0">Prototype Setup Guide</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <h5>Hardware Setup:</h5>
                            <ul>
                                <li>Power Bank → Raspberry Pi (via USB)</li>
                                <li>Phone Charger → Relay 2 (Grid Input)</li>
                                <li>Solar Panel → Relay 1 (Optional)</li>
                                <li>Load LEDs → Relay Outputs</li>
                            </ul>
                            <div class="alert alert-warning">
                                <strong>Note:</strong> All components use 5V USB power for safety
                            </div>
                        </div>
                        <div class="col-md-6">
                            <h5>Demonstration Steps:</h5>
                            <ol>
                                <li>Click "Grid Available" to simulate power outage</li>
                                <li>Click "Solar Available" to simulate sunlight</li>
                                <li>Switch to Manual mode for direct control</li>
                                <li>Watch battery drain and load shedding</li>
                            </ol>
                            <div class="alert alert-success">
                                <strong>Tip:</strong> Try covering the solar panel during demo!
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <script>
            // Update system status every 2 seconds
            function updateStatus() {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        // Update battery level
                        document.getElementById('battery-level').style.width = data.battery_level + '%';
                        document.getElementById('battery-label').textContent = Math.round(data.battery_level) + '%';
                        document.getElementById('battery-percent').textContent = Math.round(data.battery_level) + '%';
                        
                        // Update power source highlighting
                        document.querySelectorAll('.power-source').forEach(el => {
                            el.classList.remove('active');
                        });
                        document.getElementById(data.power_source + '-source').classList.add('active');
                        
                        // Update power status text
                        document.getElementById('battery-status').textContent = 'Powered by: ' + 
                            data.power_source.charAt(0).toUpperCase() + data.power_source.slice(1);
                        
                        // Update relay switches
                        document.querySelectorAll('.relay-switch').forEach(switchEl => {
                            const relay = switchEl.dataset.relay;
                            switchEl.checked = data.relay_status[relay];
                            document.getElementById(relay + '-relay-status').textContent = 
                                data.relay_status[relay] ? 'ON' : 'OFF';
                        });
                        
                        // Update load statuses
                        document.getElementById('critical-load').textContent = 'Critical Load: ' + 
                            (data.critical_load ? 'ON' : 'OFF');
                        document.querySelector('#critical-load').previousElementSibling.className = 
                            'status-indicator ' + (data.critical_load ? 'status-on' : 'status-off');
                        
                        document.getElementById('non-critical-load').textContent = 'Non-Critical Load: ' + 
                            (data.non_critical_load ? 'ON' : 'OFF');
                        document.querySelector('#non-critical-load').previousElementSibling.className = 
                            'status-indicator ' + (data.non_critical_load ? 'status-on' : 'status-off');
                        
                        // Update solar status
                        document.getElementById('solar-status').textContent = 'Status: ' + 
                            (data.relay_status.solar ? 'ON' : 'OFF');
                        document.querySelector('#solar-status').previousElementSibling.className = 
                            'status-indicator ' + (data.relay_status.solar ? 'status-on' : 'status-off');
                        
                        // Update grid status
                        document.getElementById('grid-status').textContent = 'Status: ' + 
                            (data.relay_status.grid ? 'ON' : 'OFF');
                        document.querySelector('#grid-status').previousElementSibling.className = 
                            'status-indicator ' + (data.relay_status.grid ? 'status-on' : 'status-off');
                        
                        // Update availability indicators
                        document.getElementById('solar-avail-text').textContent = 
                            data.solar_available ? 'Available' : 'Not Available';
                        document.getElementById('solar-avail-indicator').className = 
                            'status-indicator ' + (data.solar_available ? 'status-on' : 'status-off');
                        
                        document.getElementById('grid-avail-text').textContent = 
                            data.grid_available ? 'Available' : 'Not Available';
                        document.getElementById('grid-avail-indicator').className = 
                            'status-indicator ' + (data.grid_available ? 'status-on' : 'status-off');
                        
                        // Update mode buttons
                        document.getElementById('auto-btn').classList.toggle('active', data.mode === 'auto');
                        document.getElementById('manual-btn').classList.toggle('active', data.mode === 'manual');
                    });
            }
            
            // Control handlers
            document.getElementById('auto-btn').addEventListener('click', () => {
                fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: 'auto'})
                });
            });
            
            document.getElementById('manual-btn').addEventListener('click', () => {
                fetch('/control', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({mode: 'manual'})
                });
            });
            
            document.querySelectorAll('.relay-switch').forEach(switchEl => {
                switchEl.addEventListener('change', function() {
                    fetch('/control', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            relay: this.dataset.relay,
                            state: this.checked
                        })
                    });
                });
            });
            
            document.getElementById('toggle-solar').addEventListener('click', () => {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        const newState = !data.solar_available;
                        fetch('/control', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({solar_available: newState})
                        });
                    });
            });
            
            document.getElementById('toggle-grid').addEventListener('click', () => {
                fetch('/status')
                    .then(response => response.json())
                    .then(data => {
                        const newState = !data.grid_available;
                        fetch('/control', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({grid_available: newState})
                        });
                    });
            });
            
            // Initial update and set interval
            updateStatus();
            setInterval(updateStatus, 2000);
        </script>
    </body>
    </html>
    ''')

@app.route('/status')
def get_status():
    return jsonify(system_state)

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    
    # Mode toggle
    if "mode" in data:
        system_state["mode"] = data["mode"]
    
    # Manual relay control
    if "relay" in data and "state" in data:
        relay_name = data["relay"]
        state = data["state"]
        
        if relay_name == "solar":
            RELAY_SOLAR.value = state
            if state:
                system_state["power_source"] = "solar"
        elif relay_name == "grid":
            RELAY_GRID.value = state
            if state:
                system_state["power_source"] = "grid"
        elif relay_name == "battery":
            RELAY_BATT.value = state
            if state:
                system_state["power_source"] = "battery"
        elif relay_name == "load":
            RELAY_LOAD.value = state
            system_state["non_critical_load"] = state
    
    # Source availability toggles
    if "solar_available" in data:
        system_state["solar_available"] = data["solar_available"]
    
    if "grid_available" in data:
        system_state["grid_available"] = data["grid_available"]
    
    return jsonify(success=True)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)