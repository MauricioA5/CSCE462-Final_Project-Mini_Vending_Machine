# Appends vending machine events to transactions.csv.

import csv
import os
from datetime import datetime

LOG_PATH = os.path.join(os.path.dirname(__file__), "transactions.csv")
LOG_FIELDS = ["timestamp", "event", "slot", "item", "price_cents", "amount_cents", "credit_after"]


class VendingLogger:
    def __init__(self, log_path: str = LOG_PATH):
        self.log_path = log_path
        # Create the file with headers if it doesn't exist yet
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
                writer.writeheader()

    def log(self, event: str, slot: str = "", item: str = "",
            price_cents: int = 0, amount_cents: int = 0, credit_after: int = 0):
        # Appends one row for every transaction (dispense, coin insert, refund, etc.)
        row = {
            "timestamp":    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event":        event,
            "slot":         slot,
            "item":         item,
            "price_cents":  price_cents,
            "amount_cents": amount_cents,
            "credit_after": credit_after,
        }
        with open(self.log_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            writer.writerow(row)
        print(f"[logger] {row['timestamp']} {event} slot={slot} item={item}")
