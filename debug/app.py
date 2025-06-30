from flask import Flask, render_template, jsonify, request
from gpiozero import OutputDevice
import threading
import time
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('EMS')

app = Flask(__name__)

# GPIO Setup (BCM numbering)
try:
    RELAY_SOLAR = OutputDevice(17, active_high=False)  # IN1
    RELAY_GRID = OutputDevice(18, active_high=False)   # IN2
    RELAY_BATT = OutputDevice(27, active_high=False)   # IN3
    RELAY_LOAD = OutputDevice(22, active_high=False)   # IN4
    logger.info("GPIO initialized successfully")
except Exception as e:
    logger.error(f"GPIO initialization error: {e}")
    # Fallback to simulated relays
    class SimulatedRelay:
        def __init__(self, name):
            self.name = name
            self.value = False
        def on(self):
            self.value = True
            logger.info(f"{self.name} relay ON")
        def off(self):
            self.value = False
            logger.info(f"{self.name} relay OFF")
    RELAY_SOLAR = SimulatedRelay("Solar")
    RELAY_GRID = SimulatedRelay("Grid")
    RELAY_BATT = SimulatedRelay("Battery")
    RELAY_LOAD = SimulatedRelay("Load")

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

def set_power_source(source):
    """Set active power source and disable others"""
    logger.debug(f"Switching to {source} power")
    
    # Turn off all power relays first
    RELAY_SOLAR.off()
    RELAY_GRID.off()
    RELAY_BATT.off()
    
    # Enable the requested source
    if source == "solar":
        RELAY_SOLAR.on()
    elif source == "grid":
        RELAY_GRID.on()
    elif source == "battery":
        RELAY_BATT.on()
    
    # Update system state
    system_state["power_source"] = source
    system_state["relay_status"]["solar"] = RELAY_SOLAR.value
    system_state["relay_status"]["grid"] = RELAY_GRID.value
    system_state["relay_status"]["battery"] = RELAY_BATT.value

# Simulated battery drain/charge thread
def simulate_system():
    while True:
        try:
            # Update relay status in state
            system_state["relay_status"] = {
                "solar": RELAY_SOLAR.value,
                "grid": RELAY_GRID.value,
                "battery": RELAY_BATT.value,
                "load": RELAY_LOAD.value
            }
            
            # Auto mode logic
            if system_state["mode"] == "auto":
                # Power source priority: Solar > Grid > Battery
                if system_state["solar_available"]:
                    set_power_source("solar")
                elif system_state["grid_available"]:
                    set_power_source("grid")
                else:
                    set_power_source("battery")
                
                # Load shedding when battery low
                if system_state["battery_level"] < 25:
                    RELAY_LOAD.off()
                    system_state["non_critical_load"] = False
                else:
                    RELAY_LOAD.on()
                    system_state["non_critical_load"] = True
            
            # Simulate battery changes
            if system_state["power_source"] == "solar" and system_state["solar_available"]:
                system_state["battery_level"] = min(100, system_state["battery_level"] + 1)
            elif system_state["power_source"] == "grid" and system_state["grid_available"]:
                system_state["battery_level"] = min(100, system_state["battery_level"] + 0.5)
            else:
                system_state["battery_level"] = max(0, system_state["battery_level"] - 0.5)
            
            time.sleep(1)
        except Exception as e:
            logger.error(f"Simulation error: {e}")
            time.sleep(5)

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
        logger.debug(f"Control request: {data}")
        
        # Mode toggle
        if "mode" in data:
            system_state["mode"] = data["mode"]
            logger.info(f"Mode changed to: {data['mode']}")
        
        # Manual relay control
        if "relay" in data and "state" in data:
            relay_name = data["relay"]
            state = data["state"]
            
            # Handle power source relays
            if relay_name in ["solar", "grid", "battery"]:
                if state:
                    # Turn on this source and turn off others
                    set_power_source(relay_name)
                else:
                    # If turning off the active source, fall back to battery
                    if system_state["power_source"] == relay_name:
                        set_power_source("battery")
            # Handle load relay separately
            elif relay_name == "load":
                RELAY_LOAD.value = state
                system_state["non_critical_load"] = state
        
        # Source availability toggles
        if "solar_available" in data:
            system_state["solar_available"] = data["solar_available"]
            logger.info(f"Solar available: {data['solar_available']}")
        
        if "grid_available" in data:
            system_state["grid_available"] = data["grid_available"]
            logger.info(f"Grid available: {data['grid_available']}")
        
        return jsonify(success=True)
    except Exception as e:
        logger.error(f"Control error: {e}")
        return jsonify(success=False, error=str(e)), 500

if __name__ == '__main__':
    logger.info("Starting Energy Management System")
    app.run(host='0.0.0.0', port=5000, debug=True)