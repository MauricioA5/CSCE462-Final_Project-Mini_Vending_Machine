# Reads a 4x4 matrix keypad and translates key presses into actions.

import time
import smbus2

_IODIRA = 0x00
_OLATA  = 0x14
_GPPUA  = 0x0C
_GPIOA  = 0x12

_ROW_BITS = [7, 6, 5, 4]
_COL_BITS = [3, 2, 1, 0]

KEYMAP = [
    ["1", "2", "3", "A"],
    ["4", "5", "6", "B"],
    ["7", "8", "9", "C"],
    ["*", "0", "#", "D"],
]


class MatrixKeypad:
    def __init__(self, bus=1, address=0x26):
        self.bus = smbus2.SMBus(bus)
        self.address = address
        self._last_keys = []
        self._init()

    def _write(self, reg, val):
        self.bus.write_byte_data(self.address, reg, val)

    def _read(self, reg):
        return self.bus.read_byte_data(self.address, reg)

    def _init(self):
        # Configures rows as outputs and columns as inputs with pull-ups
        self._write(_IODIRA, 0x0F)
        self._write(_OLATA, 0xFF)
        col_mask = sum(1 << b for b in _COL_BITS)
        self._write(_GPPUA, col_mask)

    def _drive_row(self, row):
        # Pulls one row low so pressed keys in that row can be detected
        mask = 0xFF
        for i, bit in enumerate(_ROW_BITS):
            if i == row:
                mask &= ~(1 << bit)
        self._write(_OLATA, mask)

    def _release_rows(self):
        # Returns all rows to idle (high) state
        self._write(_OLATA, 0xFF)

    def scan(self):
        # Returns a list of all keys currently held down
        pressed = []
        for r in range(4):
            self._drive_row(r)
            time.sleep(0.001)
            port = self._read(_GPIOA)
            for c, bit in enumerate(_COL_BITS):
                if not (port & (1 << bit)):
                    pressed.append(KEYMAP[r][c])
        self._release_rows()
        return pressed

    def close(self):
        self._release_rows()
        self.bus.close()


class KeySequenceDetector:
    """Matches single keys or two-key sequences (e.g. "A"+"1" → "A1") to bound actions."""

    def __init__(self, bindings, timeout=3.0, on_first_key=None, on_unbound=None):
        self.bindings = bindings
        self.timeout = timeout
        self.on_first_key = on_first_key  # called while waiting for the second key
        self.on_unbound = on_unbound      # called when a sequence has no binding

        self._first = None
        self._time = None
        self._last = []

    def update(self, pressed):
        # Called every scan loop; fires the appropriate binding when a sequence completes
        now = time.monotonic()
        if self._first and (now - self._time) > self.timeout:
            self._reset()

        new_keys = [k for k in pressed if k not in self._last]

        for key in new_keys:
            if self._first is None:
                if key in self.bindings:
                    self.bindings[key]()
                else:
                    self._first = key
                    self._time = now
                    if self.on_first_key:
                        self.on_first_key(key)
            else:
                seq = self._first + key
                if seq in self.bindings:
                    self.bindings[seq]()
                else:
                    seq_rev = key + self._first
                    if seq_rev in self.bindings:
                        self.bindings[seq_rev]()
                    elif self.on_unbound:
                        self.on_unbound(seq)
                self._reset()

        self._last = pressed

    def _reset(self):
        self._first = None
        self._time = None
