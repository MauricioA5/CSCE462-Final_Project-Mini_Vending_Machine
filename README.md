# Raspberry Pi Vending Machine

A two-slot vending machine controller that runs on a Raspberry Pi with a web dashboard for management.

---

## Setup

```bash
pip install RPi.GPIO smbus2 flask
```

- `RPi.GPIO` — controls the GPIO pins to run the stepper motors
- `smbus2` — handles I2C communication with the keypad and LCD
- `flask` — serves the web dashboard

---

## Running

Start the vending machine:
```bash
python3 vending_machine.py
```

Run just the web dashboard:
```bash
python report.py
```

Restock all slots from the terminal:
```bash
python restock.py
```

---

## Using the Keypad

| Input | Action |
|---|---|
| `1` | Select slot A1 |
| `2` | Select slot B2 |
| `*` | Insert $0.25 |
| `#` | Refund credit |
| `D` | Show IP address |

Press `*` multiple times to add more credit. Once credit meets or exceeds the item price, the machine dispenses automatically.

Press `D` at any time to display the Pi's IP address on the LCD for 5 seconds — useful for finding the dashboard URL without needing a separate terminal.

---

## Web Dashboard

Open `http://<pi-ip>:5000` on any device on the same network.

The main page shows revenue, stock levels, and recent transactions.

Log in as manager (default password: `admin`) to:
- Edit item names, prices, and quantities
- Restock all slots to their maximum
- Reset and archive the transaction log
- Change the manager password
