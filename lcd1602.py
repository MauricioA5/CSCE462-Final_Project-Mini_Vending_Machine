# Drives a 16x2 character display over I2C.

import time
import smbus2

_CMD_CLEAR  = 0x01
_CMD_HOME   = 0x02
_CMD_ENTRY  = 0x06
_CMD_ON     = 0x0C
_CMD_4BIT_2L = 0x28
_CMD_DDRAM  = 0x80

_BACKLIGHT = 0x08
_ENABLE    = 0x04
_RS        = 0x01

_ROW_OFFSETS = [0x00, 0x40]


class LCD1602:
    COLS = 16
    ROWS = 2

    def __init__(self, bus=1, address=0x27, backlight=True):
        self.bus = smbus2.SMBus(bus)
        self.address = address
        self._bl = _BACKLIGHT if backlight else 0x00
        self._init()

    def _i2c_write(self, byte):
        self.bus.write_byte(self.address, byte | self._bl)

    def _pulse(self, data):
        # Toggles the enable line to latch a nibble into the display
        self._i2c_write(data | _ENABLE)
        time.sleep(0.0005)
        self._i2c_write(data & ~_ENABLE)
        time.sleep(0.0001)

    def _write_nibble(self, nibble, mode):
        data = (nibble & 0xF0) | mode
        self._i2c_write(data)
        self._pulse(data)

    def _send_byte(self, value, mode):
        # Sends a full byte as two 4-bit nibbles (display only accepts 4-bit mode)
        self._write_nibble(value & 0xF0, mode)
        self._write_nibble((value << 4) & 0xF0, mode)

    def _cmd(self, cmd):
        self._send_byte(cmd, 0)

    def _char(self, c):
        self._send_byte(c, _RS)

    def _init(self):
        # Wakes the display and puts it in 4-bit, 2-line mode
        time.sleep(0.05)
        for _ in range(3):
            self._write_nibble(0x30, 0)
            time.sleep(0.005)
        self._write_nibble(0x20, 0)
        time.sleep(0.001)
        self._cmd(_CMD_4BIT_2L)
        self._cmd(_CMD_ON)
        self._cmd(_CMD_CLEAR)
        time.sleep(0.002)
        self._cmd(_CMD_ENTRY)

    def clear(self):
        self._cmd(_CMD_CLEAR)
        time.sleep(0.002)

    def home(self):
        self._cmd(_CMD_HOME)
        time.sleep(0.002)

    def set_cursor(self, col, row):
        col = max(0, min(col, self.COLS - 1))
        row = max(0, min(row, self.ROWS - 1))
        self._cmd(_CMD_DDRAM | (col + _ROW_OFFSETS[row]))

    def write(self, text, col=0, row=0):
        # Writes text starting at the given column and row
        self.set_cursor(col, row)
        for ch in text[: self.COLS - col]:
            self._char(ord(ch))

    def write_row(self, text, row):
        # Overwrites an entire row, padding with spaces to clear old content
        self.write(text[:self.COLS].ljust(self.COLS), 0, row)

    def set_backlight(self, on):
        self._bl = _BACKLIGHT if on else 0x00
        self._i2c_write(0)

    def close(self):
        # Clears the screen and turns off the backlight before releasing the bus
        self.clear()
        self.set_backlight(False)
        self.bus.close()
