from flask import Flask, render_template, jsonify, request
from gpiozero import OutputDevice
import threading
import time
import os
import tempfile

# Create a secure temporary directory
temp_dir = tempfile.mkdtemp()
os.environ['TMPDIR'] = temp_dir

app = Flask(__name__)

# GPIO Setup (BCM numbering)
try:
    RELAY_SOLAR = OutputDevice(14, active_high=False)  # IN1
    RELAY_GRID = OutputDevice(18, active_high=False)   # IN2
    RELAY_BATT = OutputDevice(27, active_high=False)   # IN3
    RELAY_LOAD = OutputDevice(2, active_high=False)   # IN4
except Exception as e:
    print(f"GPIO initialization error: {e}. Using dummy devices.")
    # Create dummy devices for testing
    class DummyDevice:
        def __init__(self): self.value = False
        def on(self): self.value = True
        def off(self): self.value = False
    RELAY_SOLAR = DummyDevice()
    RELAY_GRID = DummyDevice()
    RELAY_BATT = DummyDevice()
    RELAY_LOAD = DummyDevice()

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
        try:
            # Update relay status
            system_state["relay_status"] = {
                "solar": RELAY_SOLAR.value,
                "grid": RELAY_GRID.value,
                "battery": RELAY_BATT.value,
                "load": RELAY_LOAD.value
            }
            
            # Simulate battery changes
            if system_state["power_source"] == "solar" and system_state["solar_available"]:
                system_state["battery_level"] = min(100, system_state["battery_level"] + 1)
            elif system_state["power_source"] == "grid" and system_state["grid_available"]:
                system_state["battery_level"] = min(100, system_state["battery_level"] + 0.5)
            else:
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
        except Exception as e:
            print(f"Simulation error: {e}")
            time.sleep(5)

# Power switching functions
def switch_to_solar():
    try:
        RELAY_SOLAR.on()
        RELAY_GRID.off()
        RELAY_BATT.off()
        system_state["power_source"] = "solar"
    except Exception as e:
        print(f"Solar switch error: {e}")

def switch_to_grid():
    try:
        RELAY_SOLAR.off()
        RELAY_GRID.on()
        RELAY_BATT.off()
        system_state["power_source"] = "grid"
    except Exception as e:
        print(f"Grid switch error: {e}")

def switch_to_battery():
    try:
        RELAY_SOLAR.off()
        RELAY_GRID.off()
        RELAY_BATT.on()
        system_state["power_source"] = "battery"
    except Exception as e:
        print(f"Battery switch error: {e}")

# Start simulation thread
sim_thread = threading.Thread(target=simulate_system, daemon=True)
sim_thread.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def get_status():
    return jsonify(system_state)

@app.route('/control', methods=['POST'])
def control():
    try:
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
    except Exception as e:
        print(f"Control error: {e}")
        return jsonify(success=False, error=str(e)), 500

def cleanup_temp_dir():
    try:
        import shutil
        shutil.rmtree(temp_dir)
        print(f"Cleaned up temp directory: {temp_dir}")
    except Exception as e:
        print(f"Cleanup error: {e}")

if __name__ == '__main__':
    try:
        app.run(host='0.0.0.0', port=5000, debug=True)
    finally:
        cleanup_temp_dir()
