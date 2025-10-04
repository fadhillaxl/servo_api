from gpiozero import Servo
from time import sleep

# MG90S setup on GPIO13 (pin 11)
servo = Servo(13, min_pulse_width=0.5/1000, max_pulse_width=2.5/1000)

def set_angle(angle: int):
    if angle < 0: angle = 0
    if angle > 180: angle = 180
    # Convert 0–180° to -1..+1
    value = (angle - 90) / 90
    servo.value = value
    sleep(0.5)  # give servo time to reach target
    print(f"Moved to {angle}°")

try:
    while True:
        ang = int(input("Enter angle (0–180): "))
        set_angle(ang)

except KeyboardInterrupt:
    print("\nExiting...")
    servo.detach()
