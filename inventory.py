# Tracks item stock levels and persists them to inventory.csv.

import csv
import os
from dataclasses import dataclass

CSV_PATH = os.path.join(os.path.dirname(__file__), "inventory.csv")
CSV_FIELDS = ["slot_id", "name", "price_cents", "quantity", "max_quantity"]


@dataclass
class VendingItem:
    slot_id: str
    name: str
    price_cents: int
    quantity: int
    max_quantity: int = 3

    @property
    def price_display(self) -> str:
        return f"${self.price_cents / 100:.2f}"

    @property
    def is_available(self) -> bool:
        return self.quantity > 0

    def dispense(self) -> bool:
        # Decrements stock by one; returns False if already empty
        if self.quantity > 0:
            self.quantity -= 1
            return True
        return False

    def restock(self):
        # Resets quantity back to its max
        self.quantity = self.max_quantity


class Inventory:
    DEFAULT_ITEMS = [
        VendingItem("A1", "Orbit", 100, 2, max_quantity=2),
        VendingItem("B2", "Orbit", 100, 2, max_quantity=2),
    ]

    def __init__(self, csv_path: str = CSV_PATH):
        self.csv_path = csv_path
        self.items: list[VendingItem] = []
        self._load()

    def _load(self):
        # Reads inventory from disk; seeds defaults if the file doesn't exist yet
        if not os.path.exists(self.csv_path):
            self.items = list(self.DEFAULT_ITEMS)
            self._save()
            print(f"[inventory] created {self.csv_path} with default items")
            return

        self.items = []
        with open(self.csv_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.items.append(VendingItem(
                    slot_id=row["slot_id"],
                    name=row["name"],
                    price_cents=int(row["price_cents"]),
                    quantity=int(row["quantity"]),
                    max_quantity=int(row["max_quantity"]),
                ))
        print(f"[inventory] loaded {len(self.items)} items from {self.csv_path}")

    def _save(self):
        # Writes current item list to disk
        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for item in self.items:
                writer.writerow({
                    "slot_id": item.slot_id,
                    "name": item.name,
                    "price_cents": item.price_cents,
                    "quantity": item.quantity,
                    "max_quantity": item.max_quantity,
                })

    def get(self, slot_id: str) -> VendingItem | None:
        # Always reloads from disk so web manager edits are reflected immediately
        self._load()
        return next((item for item in self.items if item.slot_id == slot_id), None)

    def dispense(self, slot_id: str) -> bool:
        # Reloads before decrementing to avoid overwriting a concurrent web change
        self._load()
        item = next((i for i in self.items if i.slot_id == slot_id), None)
        if item and item.dispense():
            self._save()
            return True
        return False

    def restock_all(self):
        # Fills every slot back to its max quantity
        for item in self.items:
            item.restock()
        self._save()
        print("[inventory] all slots restocked")
