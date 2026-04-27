# Controls a stepper motor via a step/direction driver board.

import RPi.GPIO as GPIO
import time

CW, CCW = GPIO.HIGH, GPIO.LOW


class DRV8825:
    DEFAULT_STEPS = 200 * 8

    def __init__(self, name, pin_en, pin_step, pin_dir, steps_per_rev=DEFAULT_STEPS):
        self.name = name
        self.pin_en = pin_en
        self.pin_step = pin_step
        self.pin_dir = pin_dir
        self.steps_per_rev = steps_per_rev

        for pin in (pin_en, pin_step, pin_dir):
            GPIO.setup(pin, GPIO.OUT, initial=GPIO.LOW)
        GPIO.output(pin_en, GPIO.HIGH)  # start disabled

    def enable(self):
        # Powers the motor so it can move
        GPIO.output(self.pin_en, GPIO.LOW)

    def disable(self):
        # Cuts power to the motor after a move to avoid heat buildup
        GPIO.output(self.pin_en, GPIO.HIGH)

    def step(self, direction, steps, step_delay):
        # Sends the requested number of pulses in the given direction
        GPIO.output(self.pin_dir, direction)
        for _ in range(steps):
            GPIO.output(self.pin_step, GPIO.HIGH)
            time.sleep(step_delay)
            GPIO.output(self.pin_step, GPIO.LOW)
            time.sleep(step_delay)

    def rotate(self, revolutions=1.0, direction=CW, duration_seconds=1.0):
        # Turns the motor a set number of revolutions over a fixed time, then disables it
        total_steps = int(self.steps_per_rev * revolutions)
        step_delay = duration_seconds / (total_steps * 2)
        dir_label = "CW" if direction == CW else "CCW"
        print(f"[{self.name}] {revolutions} rev {dir_label} ({total_steps} steps in {duration_seconds:.2f}s)")

        self.enable()
        try:
            self.step(direction, total_steps, step_delay)
        finally:
            self.disable()
