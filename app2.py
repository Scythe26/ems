from flask import Flask, render_template, jsonify, request
from gpiozero import OutputDevice, Device
from gpiozero.pins.mock import MockFactory
import threading
import time
import os
import shutil
import tempfile

# Use a mock factory for testing if not on a Pi
# This is a cleaner way to handle dummy devices
#try:
    #import RPi.GPIO
    # To run on a Pi, comment out the next line:
    # Device.pin_factory = MockFactory() 
#except (ImportError, RuntimeError):
   # print("Not on a Raspberry Pi. Using mock GPIO pins.")
    #Device.pin_factory = MockFactory()


app = Flask(__name__)

# --- GPIO Setup (BCM numbering) ---
# active_high=False means a LOW signal on the GPIO pin will ACTIVATE the relay.
RELAY_SOLAR = OutputDevice(17, active_high=False, initial_value=False)  # IN1
RELAY_GRID = OutputDevice(14, active_high=False, initial_value=False)   # IN2
RELAY_BATT = OutputDevice(27, active_high=False, initial_value=False)   # IN3
RELAY_LOAD = OutputDevice(2, active_high=False, initial_value=False)   # IN4


# --- System State ---
# This dictionary is our "single source of truth"
system_state = {
    "mode": "auto",  # "auto" or "manual"
    "power_source": "none", # "solar", "grid", "battery", or "none"
    "battery_level": 85.0,
    "solar_available": False,
    "grid_available": True,
    "load_on": False,
    "relay_status": {} # This will be updated periodically
}

# Use a lock to prevent race conditions when accessing system_state from multiple threads
state_lock = threading.Lock()

# --- Power Switching Functions (Ensures Break-Before-Make) ---
def switch_to_solar():
    with state_lock:
        RELAY_GRID.off()
        RELAY_BATT.off()
        time.sleep(0.2) # Small delay to ensure relays have switched off
        RELAY_SOLAR.on()
        system_state["power_source"] = "solar"
    print("Switched to SOLAR")

def switch_to_grid():
    with state_lock:
        RELAY_SOLAR.off()
        RELAY_BATT.off()
        time.sleep(0.2)
        RELAY_GRID.on()
        system_state["power_source"] = "grid"
    print("Switched to GRID")

def switch_to_battery():
    with state_lock:
        RELAY_SOLAR.off()
        RELAY_GRID.off()
        time.sleep(0.2)
        RELAY_BATT.on()
        system_state["power_source"] = "battery"
    print("Switched to BATTERY")

def all_sources_off():
    with state_lock:
        RELAY_SOLAR.off()
        RELAY_GRID.off()
        RELAY_BATT.off()
        system_state["power_source"] = "none"
    print("All sources OFF")

# --- Background System Management Thread ---
def system_manager():
    while True:
        try:
            with state_lock:
                # --- Part 1: Simulation (can be replaced with real sensor data) ---
                if system_state["power_source"] == "solar" and system_state["solar_available"]:
                    system_state["battery_level"] = min(100, system_state["battery_level"] + 0.5) # Slower charge
                elif system_state["power_source"] == "grid" and system_state["grid_available"]:
                     # Grid only maintains, doesn't charge in this logic
                     pass
                elif system_state["power_source"] == "battery":
                    # Drain battery only if load is on
                    if system_state["load_on"]:
                        system_state["battery_level"] = max(0, system_state["battery_level"] - 1.0) # Faster drain
                
                # --- Part 2: Automatic Control Logic ---
                if system_state["mode"] == "auto":
                    # Priority: Solar > Grid > Battery
                    if system_state["solar_available"]:
                        if system_state["power_source"] != "solar":
                            switch_to_solar()
                    elif system_state["grid_available"]:
                        if system_state["power_source"] != "grid":
                            switch_to_grid()
                    else:
                        if system_state["power_source"] != "battery":
                            switch_to_battery()
                    
                    # Automatic Load Shedding
                    if system_state["battery_level"] < 25 and system_state["power_source"] == "battery":
                        RELAY_LOAD.off()
                        system_state["load_on"] = False
                        print("AUTO: Load shedding enabled (Battery < 25%)")
                    elif system_state["battery_level"] > 30: # Hysteresis
                        RELAY_LOAD.on()
                        system_state["load_on"] = True

                # --- Part 3: Update Status for Frontend ---
                system_state["relay_status"] = {
                    "solar": RELAY_SOLAR.is_active,
                    "grid": RELAY_GRID.is_active,
                    "battery": RELAY_BATT.is_active,
                    "load": RELAY_LOAD.is_active
                }
                # Update load status from relay's actual state
                system_state["load_on"] = RELAY_LOAD.is_active

            time.sleep(2) # Run loop every 2 seconds
        except Exception as e:
            print(f"System manager thread error: {e}")
            time.sleep(5)

# --- Flask Web Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def get_status():
    with state_lock:
        # Return a copy to avoid modification issues
        return jsonify(system_state.copy())

@app.route('/control', methods=['POST'])
def control():
    data = request.json
    with state_lock:
        # --- Mode Control ---
        if "mode" in data:
            new_mode = data["mode"]
            if new_mode in ["auto", "manual"]:
                system_state["mode"] = new_mode
                print(f"System mode set to: {new_mode}")
                # If switching to auto, don't do anything else, let the manager thread take over
                if new_mode == "auto":
                    return jsonify(success=True, message="Mode set to auto.")

        # --- Manual Relay Control (Only works if not switching to auto) ---
        if "relay" in data and "state" in data:
            relay_name = data["relay"]
            state = data["state"] # True for ON, False for OFF

            # A manual action forces the system into manual mode
            system_state["mode"] = "manual"
            print("Manual override detected. Switching to MANUAL mode.")

            if relay_name == "solar":
                if state: switch_to_solar()
                else: all_sources_off()
            elif relay_name == "grid":
                if state: switch_to_grid()
                else: all_sources_off()
            elif relay_name == "battery":
                if state: switch_to_battery()
                else: all_sources_off()
            elif relay_name == "load":
                if state:
                    RELAY_LOAD.on()
                else:
                    RELAY_LOAD.off()
                system_state["load_on"] = state

        # --- Source Availability Toggles (for simulation) ---
        if "solar_available" in data:
            system_state["solar_available"] = data["solar_available"]
        if "grid_available" in data:
            system_state["grid_available"] = data["grid_available"]
            
    return jsonify(success=True)

# --- Main Execution ---
if __name__ == '__main__':
    # Initialize all relays to OFF at the start
    all_sources_off()
    RELAY_LOAD.off()
    
    # Start the background thread
    manager_thread = threading.Thread(target=system_manager, daemon=True)
    manager_thread.start()

    # Run the Flask app
    app.run(host='0.0.0.0', port=5000, debug=False) # Debug mode can cause threads to run twice
