from __future__ import annotations

import time

import hid

from ..exceptions import DeviceIOError

PACKET_SIZE = 64
REPORT_ID   = 0x06
POLL_TIMEOUT_MS  = 50
QUERY_DELAY_S    = 0.10


class HidTransport:
    """Low-level HID I/O for two collections on the same interface.

    Col01 (ctrl) — bidirectional: send queries/writes, read responses.
    Col02 (evt)  — read-only: unsolicited device events.
    """

    def __init__(self) -> None:
        self._ctrl: hid.device | None = None
        self._evt:  hid.device | None = None

    def open(self, ctrl_path: bytes, evt_path: bytes | None = None) -> None:
        self._ctrl = hid.device()
        self._ctrl.open_path(ctrl_path)
        self._ctrl.set_nonblocking(1)

        if evt_path:
            self._evt = hid.device()
            self._evt.open_path(evt_path)
            self._evt.set_nonblocking(1)

    def close(self) -> None:
        for dev in (self._ctrl, self._evt):
            if dev is not None:
                try:
                    dev.close()
                except Exception:
                    pass
        self._ctrl = None
        self._evt  = None

    def write(self, cmd: int, payload: list[int] | bytes = ()) -> None:
        """Send a 64-byte interrupt OUT packet to Col01."""
        if self._ctrl is None:
            raise DeviceIOError("transport not open")
        pkt = bytearray(PACKET_SIZE)
        pkt[0] = REPORT_ID
        pkt[1] = cmd
        for i, b in enumerate(payload):
            if 2 + i >= PACKET_SIZE:
                break
            pkt[2 + i] = b
        ret = self._ctrl.write(list(pkt))
        if ret < 0:
            raise DeviceIOError(f"write failed (cmd=0x{cmd:02X})")

    def query(self, cmd: int, timeout_ms: int = 200) -> list[int]:
        """Send a query packet and return the first matching response."""
        if self._ctrl is None:
            raise DeviceIOError("transport not open")
        self.write(cmd)
        time.sleep(QUERY_DELAY_S)
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            data = self._ctrl.read(PACKET_SIZE, POLL_TIMEOUT_MS)
            if data and data[1] == cmd:
                return list(data)
        raise DeviceIOError(f"no response for cmd=0x{cmd:02X}")

    def poll(self, timeout_ms: int = POLL_TIMEOUT_MS) -> list[tuple[str, list[int]]]:
        """Non-blocking read of both handles. Returns [(source, data), ...]."""
        results: list[tuple[str, list[int]]] = []
        for dev, label in ((self._ctrl, "CTRL"), (self._evt, "EVT")):
            if dev is None:
                continue
            data = dev.read(PACKET_SIZE, timeout_ms)
            if data:
                results.append((label, list(data)))
        return results

    def write_feature_report(self, report_id: int, data: bytes) -> None:
        """Send a large HID feature report to Col01 (used for OLED draw)."""
        if self._ctrl is None:
            raise DeviceIOError("transport not open")
        payload = bytes([report_id]) + data
        ret = self._ctrl.send_feature_report(list(payload))
        if ret < 0:
            raise DeviceIOError(f"feature report write failed (report_id=0x{report_id:02X})")
