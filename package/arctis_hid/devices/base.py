from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    pass


class AbstractOled(ABC):
    """Interface for devices that support custom OLED screen rendering."""

    @property
    @abstractmethod
    def width(self) -> int:
        """Display width in pixels."""

    @property
    @abstractmethod
    def height(self) -> int:
        """Display height in pixels."""

    @abstractmethod
    def draw_raw(self, frame: bytes) -> None:
        """Send a fully-encoded frame to the display.

        frame must be exactly the number of bytes the device expects
        (OLED_REPORT_SIZE * OLED_REPORTS_PER_FRAME).
        """

    @abstractmethod
    def clear(self) -> None:
        """Blank the display."""

    @abstractmethod
    def release(self) -> None:
        """Return OLED control to GG / Sonar (CMD_OLED_RELEASE 0x95)."""

    def __enter__(self) -> "AbstractOled":
        return self

    def __exit__(self, *_: object) -> None:
        self.release()


class AbstractHeadset(ABC):
    """Device-agnostic interface for a supported headset."""

    # ── lifecycle ──────────────────────────────────────────────────────────

    @abstractmethod
    def open(self) -> None:
        """Open HID handles. Called automatically by discover()."""

    @abstractmethod
    def close(self) -> None:
        """Stop the event loop (if running) and close all HID handles."""

    # ── queries ────────────────────────────────────────────────────────────

    @abstractmethod
    def get_status(self):
        """Return a snapshot of device status (battery, ANC, connectivity…)."""

    @abstractmethod
    def get_mic_eq(self):
        """Return a snapshot of mic/EQ parameters (volume, gain, bands…)."""

    @abstractmethod
    def get_firmware_version(self) -> str:
        """Return the firmware version string."""

    @abstractmethod
    def get_serial_number(self) -> str:
        """Return the device serial number."""

    # ── event mode ─────────────────────────────────────────────────────────

    @abstractmethod
    def on(self, event: str, callback: Callable) -> None:
        """Register a callback for a named event (e.g. 'VolumeEvent')."""

    @abstractmethod
    def off(self, event: str, callback: Callable) -> None:
        """Unregister a previously registered callback."""

    @abstractmethod
    def listen(self, timeout: float | None = None) -> None:
        """Block the calling thread, dispatching events until stopped or timeout."""

    @abstractmethod
    def start(self) -> None:
        """Start the event loop in a background daemon thread."""

    @abstractmethod
    def stop(self) -> None:
        """Signal the background event loop to stop and wait for it to exit."""

    # ── OLED ───────────────────────────────────────────────────────────────

    @property
    def oled(self) -> AbstractOled | None:
        """Return an OLED controller, or None if not supported / not yet implemented."""
        return None

    # ── context manager ────────────────────────────────────────────────────

    def __enter__(self) -> "AbstractHeadset":
        self.open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
