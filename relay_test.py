import RPi.GPIO as GPIO
import time

# Define GPIO pins connected to the relay module's IN pins
RELAY_PINS = [14, 2, 3, 4]  # Example pins, adjust according to your wiring

def setup_gpio():
    """Sets up the GPIO pins for output."""
    GPIO.setmode(GPIO.BCM)
    for pin in RELAY_PINS:
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)  # Ensure relays are initially off

def test_relay(pin, delay=1):
    """Tests a single relay channel."""
    print(f"Testing relay on pin {pin}...")
    GPIO.output(pin, GPIO.LOW)  # Turn relay on
    time.sleep(delay)
    GPIO.output(pin, GPIO.HIGH)  # Turn relay off
    time.sleep(delay)

def main():
    """Main function to test all relay channels."""
    setup_gpio()

    try:
        while True:
            for pin in RELAY_PINS:
                test_relay(pin)
            time.sleep(2)  # Add a longer delay between cycles
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        GPIO.cleanup()  # Reset GPIO settings on exit

if __name__ == "__main__":
    main()
