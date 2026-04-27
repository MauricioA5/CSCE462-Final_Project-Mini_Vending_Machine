# Web dashboard for the vending machine. Routes: / (analytics), /records, /manager, /login

import csv
import glob
import hashlib
import os
import secrets
import shutil
from datetime import datetime
from flask import (Flask, render_template, redirect,
                   request, url_for, session, send_file)

BASE_DIR       = os.path.dirname(__file__)
LOG_PATH       = os.path.join(BASE_DIR, "transactions.csv")
INVENTORY_PATH = os.path.join(BASE_DIR, "inventory.csv")
PASSWORD_FILE  = os.path.join(BASE_DIR, ".manager_password")
CSV_FIELDS     = ["slot_id", "name", "price_cents", "quantity", "max_quantity"]
LOG_FIELDS     = ["timestamp", "event", "slot", "item", "price_cents", "amount_cents", "credit_after"]

DEFAULT_PASSWORD = "admin"

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# ── password helpers ──────────────────────────────────────────────────────────

def _hash(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()

def _get_password_hash() -> str:
    # Returns stored hash, writing the default on first run
    if os.path.exists(PASSWORD_FILE):
        return open(PASSWORD_FILE).read().strip()
    h = _hash(DEFAULT_PASSWORD)
    open(PASSWORD_FILE, "w").write(h)
    return h

def _check_password(pw: str) -> bool:
    return _hash(pw) == _get_password_hash()

def _set_password(pw: str):
    open(PASSWORD_FILE, "w").write(_hash(pw))

def _manager_logged_in() -> bool:
    return session.get("manager") is True

# ── data helpers ──────────────────────────────────────────────────────────────

def _load_transactions():
    # Reads all rows from the transaction log
    if not os.path.exists(LOG_PATH):
        return []
    with open(LOG_PATH, newline="") as f:
        return list(csv.DictReader(f))


def _load_stock():
    # Reads inventory from CSV and casts numeric fields
    if not os.path.exists(INVENTORY_PATH):
        return []
    with open(INVENTORY_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["price_cents"]  = int(r["price_cents"])
        r["quantity"]     = int(r["quantity"])
        r["max_quantity"] = int(r["max_quantity"])
    return rows


def _save_stock(items: list[dict]):
    # Writes the inventory list back to CSV
    with open(INVENTORY_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in items:
            writer.writerow({k: item[k] for k in CSV_FIELDS})


def _list_record_files():
    # Returns metadata for all transaction CSV files, newest first
    pattern = os.path.join(BASE_DIR, "transactions*.csv")
    files = []
    for path in sorted(glob.glob(pattern), key=os.path.getmtime, reverse=True):
        name     = os.path.basename(path)
        size_kb  = os.path.getsize(path) / 1024
        modified = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M")
        files.append({
            "name":     name,
            "size":     f"{size_kb:.1f} KB",
            "modified": modified,
            "current":  name == "transactions.csv",
        })
    return files

# ── routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    rows  = _load_transactions()
    stock = _load_stock()

    revenue   = sum(int(r["price_cents"])  for r in rows if r["event"] == "DISPENSE")
    dispenses = sum(1                       for r in rows if r["event"] == "DISPENSE")
    refunded  = sum(int(r["amount_cents"])  for r in rows if r["event"] == "REFUND")
    coins     = sum(int(r["amount_cents"])  for r in rows if r["event"] == "COIN_INSERT")
    oos_count = sum(1                       for r in rows if r["event"] == "OUT_OF_STOCK")

    slot_data: dict = {}
    for r in rows:
        if r["event"] != "DISPENSE":
            continue
        key = r["slot"]
        if key not in slot_data:
            slot_data[key] = {"slot": key, "item": r["item"], "units": 0, "revenue": 0}
        slot_data[key]["units"]   += 1
        slot_data[key]["revenue"] += int(r["price_cents"])
    slot_summary = sorted(slot_data.values(), key=lambda x: x["slot"])

    return render_template(
        "dashboard.html",
        page="dashboard",
        now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        revenue=revenue, dispenses=dispenses,
        refunded=refunded, coins=coins, oos_count=oos_count,
        stock=stock, slot_summary=slot_summary,
        recent=list(reversed(rows))[:50],
        total_rows=len(rows),
    )


@app.route("/records")
def records():
    return render_template("records.html", page="records", files=_list_record_files())


@app.route("/records/download/<filename>")
def records_download(filename):
    # Only serve files that exist in BASE_DIR and start with "transactions"
    safe = os.path.basename(filename)
    path = os.path.join(BASE_DIR, safe)
    if not os.path.exists(path) or not safe.startswith("transactions"):
        return "File not found.", 404
    return send_file(path, as_attachment=True, download_name=safe)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if _check_password(request.form.get("password", "")):
            session["manager"] = True
            return redirect(url_for("manager"))
        return render_template("login.html", page="login", error="Incorrect password.")
    return render_template("login.html", page="login", error=None)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))


@app.route("/manager")
def manager():
    if not _manager_logged_in():
        return redirect(url_for("login"))
    flash     = request.args.get("flash", "")
    flash_err = request.args.get("err", "0") == "1"
    return render_template("manager.html", page="manager",
                           stock=_load_stock(), flash=flash, flash_err=flash_err)


@app.route("/manager/save", methods=["POST"])
def manager_save():
    if not _manager_logged_in():
        return redirect(url_for("login"))
    slot_ids       = request.form.getlist("slot_id")
    names          = request.form.getlist("name")
    price_dollars  = request.form.getlist("price_dollars")
    quantities     = request.form.getlist("quantity")
    max_quantities = request.form.getlist("max_quantity")
    try:
        items = []
        for slot_id, name, price, qty, max_qty in zip(
                slot_ids, names, price_dollars, quantities, max_quantities):
            items.append({
                "slot_id":      slot_id.strip(),
                "name":         name.strip(),
                "price_cents":  round(float(price) * 100),
                "quantity":     int(qty),
                "max_quantity": int(max_qty),
            })
        _save_stock(items)
        return redirect(url_for("manager", flash="Changes saved successfully."))
    except Exception as e:
        return redirect(url_for("manager", flash=f"Error saving: {e}", err="1"))


@app.route("/manager/restock", methods=["POST"])
def manager_restock():
    if not _manager_logged_in():
        return redirect(url_for("login"))
    slot_ids       = request.form.getlist("slot_id")
    names          = request.form.getlist("name")
    price_dollars  = request.form.getlist("price_dollars")
    max_quantities = request.form.getlist("max_quantity")
    try:
        items = []
        for slot_id, name, price, max_qty in zip(
                slot_ids, names, price_dollars, max_quantities):
            mq = int(max_qty)
            items.append({
                "slot_id":      slot_id.strip(),
                "name":         name.strip(),
                "price_cents":  round(float(price) * 100),
                "quantity":     mq,
                "max_quantity": mq,
            })
        _save_stock(items)
        return redirect(url_for("manager", flash="All slots restocked to max."))
    except Exception as e:
        return redirect(url_for("manager", flash=f"Error restocking: {e}", err="1"))


@app.route("/manager/reset-analytics", methods=["POST"])
def reset_analytics():
    if not _manager_logged_in():
        return redirect(url_for("login"))
    # Archive the current log before clearing so history is preserved
    if os.path.exists(LOG_PATH):
        stamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive = LOG_PATH.replace(".csv", f"_archive_{stamp}.csv")
        shutil.move(LOG_PATH, archive)
    with open(LOG_PATH, "w", newline="") as f:
        csv.DictWriter(f, fieldnames=LOG_FIELDS).writeheader()
    return redirect(url_for("manager", flash="Analytics archived and reset."))


@app.route("/manager/change-password", methods=["POST"])
def change_password():
    if not _manager_logged_in():
        return redirect(url_for("login"))
    pw1 = request.form.get("pw1", "")
    pw2 = request.form.get("pw2", "")
    if pw1 != pw2:
        return redirect(url_for("manager", flash="Passwords do not match.", err="1"))
    if len(pw1) < 4:
        return redirect(url_for("manager", flash="Password must be at least 4 characters.", err="1"))
    _set_password(pw1)
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    _get_password_hash()
    print("=" * 52)
    print("  Vending Machine Dashboard")
    print("  Open on any device on your network:")
    print("    http://<your-pi-ip>:5000")
    print("  Find your Pi IP:  hostname -I")
    print(f"  Default manager password: {DEFAULT_PASSWORD}")
    print("=" * 52)
    app.run(host="0.0.0.0", port=5000, debug=False)
