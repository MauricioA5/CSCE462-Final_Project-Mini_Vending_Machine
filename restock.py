# Utility script to refill all slots to their max quantity. Run directly on the Pi.

from inventory import Inventory

def main():
    inv = Inventory()
    inv.restock_all()
    print("All slots restocked!")

if __name__ == "__main__":
    main()
