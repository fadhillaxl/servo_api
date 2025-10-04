from gpiozero import Servo
from time import sleep
import warnings

# Suppress gpiozero warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="gpiozero")

# GPIO pins array - add or remove pins as needed
gpio_pins = [13, 18, 19, 26]

# Multiple servo setup - servos are created based on the gpio_pins array
servos = {}
print("Initializing servos...")
for i, pin in enumerate(gpio_pins, 1):
    try:
        servos[i] = Servo(pin, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)
        print(f"  Servo {i} initialized on GPIO pin {pin}")
    except Exception as e:
        print(f"  Error initializing servo {i} on GPIO pin {pin}: {e}")
print()

def set_angle(servo_id: int, angle: int):
    if servo_id not in servos:
        print(f"Error: Servo {servo_id} not found. Available servos: {list(servos.keys())}")
        return
    
    if angle < 0: angle = 0
    if angle > 180: angle = 180
    
    # Convert 0–180° to -1..+1
    value = (angle - 90) / 90
    servos[servo_id].value = value
    sleep(0.5)  # give servo time to reach target
    print(f"Servo {servo_id} moved to {angle}°")

def list_servos():
    print("Available servos:")
    for servo_id in servos.keys():
        gpio_pin = gpio_pins[servo_id - 1]  # servo_id starts from 1, array index from 0
        print(f"  Servo {servo_id}: GPIO pin {gpio_pin}")

def set_all_servos(angle: int):
    """Move all servos to the same angle"""
    print(f"Moving all servos to {angle}°...")
    for servo_id in servos:
        set_angle(servo_id, angle)

try:
    print("Multi-Servo Controller")
    print("Commands:")
    print("  <servo_id> <angle> - Move specific servo (e.g., '1 90')")
    print("  all <angle> - Move all servos to same angle (e.g., 'all 90')")
    print("  list - Show available servos")
    print("  quit - Exit program")
    print()
    
    list_servos()
    print()
    
    while True:
        command = input("Enter command: ").strip().lower()
        
        if command == "quit":
            break
        elif command == "list":
            list_servos()
        elif command.startswith("all "):
            try:
                angle = int(command.split()[1])
                set_all_servos(angle)
            except (ValueError, IndexError):
                print("Invalid command. Use: all <angle>")
        else:
            try:
                parts = command.split()
                if len(parts) == 2:
                    servo_id = int(parts[0])
                    angle = int(parts[1])
                    set_angle(servo_id, angle)
                else:
                    print("Invalid command. Use: <servo_id> <angle>, 'all <angle>', 'list', or 'quit'")
            except ValueError:
                print("Invalid command. Use: <servo_id> <angle>, 'all <angle>', 'list', or 'quit'")

except KeyboardInterrupt:
    print("\nExiting...")

finally:
    # Cleanup all servos
    print("Detaching all servos...")
    for servo_id, servo in servos.items():
        try:
            servo.detach()
            print(f"Servo {servo_id} detached")
        except Exception as e:
            print(f"Error detaching servo {servo_id}: {e}")
    print("All servos detached. Goodbye!")
