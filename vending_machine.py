import time
import socket
import RPi.GPIO as GPIO
from drv8825 import DRV8825, CW
from lcd1602 import LCD1602
from keypad import MatrixKeypad, KeySequenceDetector
from inventory import Inventory
from logger import VendingLogger

MOTOR_PINS = [
    {"name": "Motor 1", "pin_en": 14, "pin_step": 15, "pin_dir": 18},
    {"name": "Motor 2", "pin_en": 23, "pin_step": 24, "pin_dir": 25},
]

LCD_ADDRESS = 0x27
MCP_ADDRESS = 0x26
I2C_BUS = 1

COIN_VALUE_CENTS = 25
DISPENSE_REVS = 1.0
DISPENSE_DURATION = 1.0

SLOT_IDS = ["A1", "B2"]


class VendingMachine:
    def __init__(self, motors, lcd, keypad, inventory):
        self.motors = motors
        self.lcd = lcd
        self.keypad = keypad
        self.inventory = inventory
        self.logger = VendingLogger()

        self.credit_cents = 0
        self.selected_slot = None

        bindings = {
            "1": lambda: self._select("A1"),
            "2": lambda: self._select("B2"),
            "A1": lambda: self._select("A1"),
            "B2": lambda: self._select("B2"),
            "*": self._insert_coin,
            "#": self._refund,
            "D": self._show_ip,
        }

        self.detector = KeySequenceDetector(
            bindings=bindings,
            timeout=5.0,
            on_first_key=self._on_first_key,
            on_unbound=self._on_unbound,
        )

    def _show(self, line0, line1):
        # Updates both lines of the display at once
        self.lcd.write_row(line0[:16].ljust(16), 0)
        self.lcd.write_row(line1[:16].ljust(16), 1)

    def _show_idle(self):
        # Returns the display to the default prompt screen
        if self.selected_slot:
            self._show(f"Selected {self.selected_slot}", f"Credit: ${self.credit_cents/100:.2f}")
        else:
            self._show("Select item [1-2]", f"Credit: ${self.credit_cents/100:.2f}")

    def _on_first_key(self, key):
        # Acknowledges the first key while waiting for a second key to complete a sequence
        self._show(f"Key [{key}] pressed", f"Waiting...")

    def _on_unbound(self, seq):
        # Shown when the user types a key combination that doesn't map to anything
        self._show(f"Unknown [{seq}]", "Try again")
        time.sleep(1)
        self._show_idle()

    def _select(self, slot_id):
        # Stores the chosen slot and dispenses immediately if there's enough credit
        self.selected_slot = slot_id
        item = self.inventory.get(slot_id)
        if not item:
            self._show(f"{slot_id} Not found", "Try another")
        else:
            self._show(f"Selected {slot_id}", f"Price: {item.price_display}")
            if self.credit_cents >= item.price_cents:
                self._dispense()

    def _insert_coin(self):
        # Adds one coin's value to the current credit and auto-dispenses if ready
        self.credit_cents += COIN_VALUE_CENTS
        self.logger.log("COIN_INSERT", amount_cents=COIN_VALUE_CENTS, credit_after=self.credit_cents)
        self._show(f"Inserted ${COIN_VALUE_CENTS/100:.2f}", f"Credit: ${self.credit_cents/100:.2f}")
        time.sleep(1)
        if self.selected_slot:
            self._show_idle()

    def _refund(self):
        # Returns all current credit to the user and resets to zero
        if self.credit_cents == 0:
            self._show("No credit", "to refund")
        else:
            amount = f"${self.credit_cents/100:.2f}"
            self.logger.log("REFUND", amount_cents=self.credit_cents)
            self.credit_cents = 0
            self._show("REFUND", amount)
        time.sleep(2)
        self._show_idle()

    def _show_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except Exception:
            ip = "No network"
        self._show("IP Address:", ip)
        time.sleep(5)
        self._show_idle()

    def _dispense(self):
        # Validates stock and credit, runs the motor, then logs the transaction
        if not self.selected_slot:
            return
        item = self.inventory.get(self.selected_slot)
        idx = SLOT_IDS.index(self.selected_slot)
        motor = self.motors[idx]

        if not item.is_available:
            self._show(item.name[:16], "OUT OF STOCK")
            self.logger.log("OUT_OF_STOCK", slot=self.selected_slot, item=item.name)
            time.sleep(3)
        elif self.credit_cents < item.price_cents:
            self._show("Insufficient", f"Credit: ${self.credit_cents/100:.2f}")
            time.sleep(2)
        else:
            self.credit_cents -= item.price_cents
            self._show("Dispensing...", item.name[:16])
            motor.rotate(DISPENSE_REVS, CW, DISPENSE_DURATION)
            self.inventory.dispense(self.selected_slot)
            self.logger.log("DISPENSE", slot=self.selected_slot, item=item.name,
                            price_cents=item.price_cents, credit_after=self.credit_cents)
            time.sleep(2)
            if self.credit_cents > 0:
                self._show(f"Change: ${self.credit_cents/100:.2f}", "Press [#]")
                time.sleep(2)
        self.selected_slot = None
        self._show_idle()

    def run(self):
        # Main loop — polls the keypad and feeds keys to the sequence detector
        self._show_idle()
        while True:
            pressed = self.keypad.scan()
            self.detector.update(pressed)
            time.sleep(0.02)

    def shutdown(self):
        # Cleanly disables motors and closes peripherals on exit
        for motor in self.motors:
            motor.disable()
        self.lcd.close()
        self.keypad.close()


def _start_dashboard():
    # Launches the Flask web dashboard in a background thread so it doesn't block the machine
    import threading
    from report import app
    thread = threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False),
        daemon=True,
        name="dashboard",
    )
    thread.start()
    print("=" * 52)
    print("  Dashboard running — open on any device:")
    print("    http://<your-pi-ip>:5000")
    print("  Find your Pi IP:  hostname -I")
    print("=" * 52)


def main():
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)

    _start_dashboard()

    motors = [DRV8825(**cfg) for cfg in MOTOR_PINS]
    lcd = LCD1602(bus=I2C_BUS, address=LCD_ADDRESS)
    keypad = MatrixKeypad(bus=I2C_BUS, address=MCP_ADDRESS)
    inventory = Inventory()

    vm = VendingMachine(motors, lcd, keypad, inventory)
    try:
        vm.run()
    except KeyboardInterrupt:
        pass
    finally:
        vm.shutdown()


if __name__ == "__main__":
    main()
