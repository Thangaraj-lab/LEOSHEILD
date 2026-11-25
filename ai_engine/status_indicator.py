"""Optional serial status indicator. Inspection never waits for it."""

from threading import Event, Thread
from time import monotonic
from uuid import uuid4

import serial
from serial.tools import list_ports

STATES = {"IDLE", "CAPTURING", "ANALYZING", "AWAITING_CAPTURE", "COMPLETED", "ERROR"}


def exchange(port, command, value=None, timeout=0.8):
    request_id = uuid4().hex[:16]
    parts = ["LEO", request_id, command]
    if value is not None:
        parts.append(value)
    port.write((" ".join(parts) + "\n").encode("ascii"))
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        line = port.read_until(b"\n", 128).decode("ascii", errors="replace").strip().split()
        if len(line) != 6 or line[:3] != parts[:3]:
            continue
        _, _, _, version, state, outcome = line
        if version != "1.0.0" or state not in STATES or outcome != "OK" or (value is not None and state != value):
            raise OSError("Unexpected indicator acknowledgment")
        return state
    raise TimeoutError("Indicator did not acknowledge request")


class StatusIndicator:
    def __init__(self, configured_port):
        self.configured_port = configured_port
        self.available = False
        self.desired = "IDLE"
        self._wake = Event()
        self._stop = Event()
        self._thread = None

    def start(self):
        if self.configured_port:
            self._thread = Thread(target=self._run, name="leo-status-indicator", daemon=True)
            self._thread.start()

    def stop(self):
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=3)

    def publish(self, state):
        if self.configured_port and state != self.desired:
            self.desired = state
            self._wake.set()

    def _port_name(self):
        if self.configured_port.lower() != "auto":
            return self.configured_port
        candidates = [item.device for item in list_ports.comports() if (item.vid, item.pid) == (0x10C4, 0xEA60)]
        return candidates[0] if len(candidates) == 1 else None

    def _run(self):
        while not self._stop.is_set():
            try:
                name = self._port_name()
                if name:
                    self._serve_port(name)
            except (OSError, serial.SerialException):
                pass
            finally:
                self.available = False
            self._stop.wait(2)

    def _serve_port(self, name):
        connection = serial.Serial(baudrate=115200, timeout=0.15, write_timeout=0.5)
        connection.port = name
        connection.dtr = False
        connection.rts = False
        with connection:
            exchange(connection, "PING")
            try:
                while not self._stop.is_set():
                    self._wake.clear()
                    exchange(connection, "SET_STATUS", self.desired)
                    self.available = True
                    self._wake.wait(1.5)
            finally:
                if self._stop.is_set():
                    exchange(connection, "ALL_OFF")
