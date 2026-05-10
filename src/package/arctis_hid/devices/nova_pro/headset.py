from __future__ import annotations

import threading
from typing import Callable

from ...core.dispatcher import EventDispatcher
from ...core.transport import HidTransport
from ...core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    WirelessMode,
)
from ...exceptions import DeviceIOError
from ..base import AbstractHeadset, AbstractOled
from . import constants as C
from . import codec
from .models import ConnectivityData, DisplayData, MicEqData, StatusData


class ArctisNovaProWireless(AbstractHeadset):
    """HID API for the SteelSeries Arctis Nova Pro Wireless (and variants).

    Usage — command mode::

        with discover() as h:
            print(h.get_status())
            h.set_volume(75)

    Usage — event mode::

        with discover() as h:
            h.on("VolumeEvent", lambda e: print(e.percent))
            h.listen()   # blocks; Ctrl-C to exit
    """

    def __init__(self, ctrl_path: bytes, evt_path: bytes | None = None) -> None:
        self._ctrl_path = ctrl_path
        self._evt_path  = evt_path
        self._transport = HidTransport()
        self._dispatcher = EventDispatcher()
        self._stop_event: threading.Event = threading.Event()
        self._thread:     threading.Thread | None = None
        self._oled_controller: AbstractOled | None = None

    # ── lifecycle ──────────────────────────────────────────────────────────

    def open(self) -> None:
        self._transport.open(self._ctrl_path, self._evt_path)

    def close(self) -> None:
        self.stop()
        self._transport.close()

    # ── queries ────────────────────────────────────────────────────────────

    def get_status(self) -> StatusData:
        data = self._transport.query(C.CMD_STATUS)
        return codec.decode_status_packet(data)

    def get_mic_eq(self) -> MicEqData:
        data = self._transport.query(C.CMD_MIC_EQ)
        return codec.decode_mic_eq_packet(data)

    def get_firmware_version(self) -> str:
        data = self._transport.query(C.CMD_FIRMWARE)
        return codec.decode_ascii_response(data)

    def get_serial_number(self) -> str:
        data = self._transport.query(C.CMD_SERIAL)
        return codec.decode_ascii_response(data)

    def get_connectivity(self) -> ConnectivityData:
        data = self._transport.query(C.CMD_CONNECTIVITY)
        return codec.decode_connectivity_packet(data)

    def get_display(self) -> DisplayData:
        data = self._transport.query(C.CMD_DISPLAY)
        return codec.decode_display_packet(data)

    # ── writes ─────────────────────────────────────────────────────────────

    def set_volume(self, pct: float) -> None:
        """Set headset volume. pct: 0–100."""
        self._transport.write(C.CMD_VOL, [codec.encode_volume(pct)])
        self._save()

    def set_mic_volume(self, level: int) -> None:
        """Set mic volume. level: 1–10."""
        self._transport.write(C.CMD_MIC_VOL, [level])
        self._save()

    def set_sidetone(self, level: SidetoneLevel) -> None:
        self._transport.write(C.CMD_SIDETONE, [int(level)])
        self._save()

    def set_anc_mode(self, mode: AncMode) -> None:
        self._transport.write(C.CMD_ANC, [int(mode)])
        self._save()

    def set_transparency_level(self, level: int) -> None:
        """Set transparency level. level: 1–10. Only effective in TRANSPARENCY mode."""
        self._transport.write(C.CMD_TRANSP_LEVEL, [level])
        self._save()

    def set_oled_brightness(self, level: int) -> None:
        """Set OLED display brightness. level: 1–10."""
        self._transport.write(C.CMD_OLED_BRIGHT, [level])
        self._save()

    def set_gain(self, level: GainLevel) -> None:
        self._transport.write(C.CMD_GAIN, [codec.encode_gain(level)])
        self._save()

    def set_mic_led_brightness(self, level: int) -> None:
        """Set mic mute LED brightness. level: 1–10."""
        self._transport.write(C.CMD_MIC_LED, [level])
        self._save()

    def set_chatmix_enabled(self, enabled: bool) -> None:
        """Enable or disable the ChatMix dial. ChatMix events only fire when enabled."""
        self._transport.write(C.CMD_CHATMIX_EN, [0x01 if enabled else 0x00])
        self._save()

    def set_wireless_mode(self, mode: WirelessMode) -> None:
        """Set 2.4 GHz wireless mode. Note: no Col02 event fires — verify via get_status()."""
        self._transport.write(C.CMD_WIRELESS, [int(mode)])
        self._save()

    def set_bt_default(self, enabled: bool) -> None:
        self._transport.write(C.CMD_BT_DEFAULT, [0x01 if enabled else 0x00])
        self._save()

    def set_bt_auto_mute(self, mode: BtAutoMute) -> None:
        self._transport.write(C.CMD_BT_AUTOMUTE, [int(mode)])
        self._save()

    def set_audio_output(self, output: AudioOutput) -> None:
        self._transport.write(C.CMD_AUDIO_OUT, [int(output)])
        self._save()

    def set_stream_volumes(self, main: int, aux: int, mic: int) -> None:
        """Set stream output volumes. Each value: 0–100."""
        self._transport.write(C.CMD_STREAM_VOLS, [main, 0x00, aux, mic])
        self._save()

    def set_eq_preset(self, index: int) -> None:
        """Select an EQ preset. Use index 0x04 for custom EQ."""
        self._transport.write(C.CMD_EQ_PRESET, [index])
        self._save()

    def set_eq_bands(self, bands: list[int]) -> None:
        """Set all 10 custom EQ band levels.

        bands: list of 10 ints, each 0–40; 20 = flat/0 dB.
        Automatically selects the custom EQ preset first (index 0x04).
        """
        if len(bands) != 10:
            raise ValueError(f"expected 10 EQ band values, got {len(bands)}")
        self._transport.write(C.CMD_EQ_PRESET, [0x04])
        self._transport.write(C.CMD_EQ_BANDS, bands)
        self._save()

    def set_dim_timeout(self, step: TimeoutStep) -> None:
        self._transport.write(C.CMD_DIM_TIMEOUT, [int(step)])
        self._save()

    def set_home_screen_mode(self, mode: HomeScreenMode) -> None:
        self._transport.write(C.CMD_HOME_SCREEN, [int(mode)])
        self._save()

    def set_auto_off_timeout(self, step: TimeoutStep) -> None:
        self._transport.write(C.CMD_AUTO_OFF, [int(step)])
        self._save()

    def factory_reset(self) -> None:
        """Reset the headset to factory defaults (command 0xFD).

        **DESTRUCTIVE — irreversible.** All settings (EQ, ANC, volume, timeouts,
        BT config, etc.) are wiped. The device will disconnect and reboot.
        Do NOT call _save() (0x09) after this command.
        """
        self._transport.write(C.CMD_FACTORY_RESET)

    # ── event mode ─────────────────────────────────────────────────────────

    def on(self, event: str, callback: Callable) -> None:
        self._dispatcher.on(event, callback)

    def off(self, event: str, callback: Callable) -> None:
        self._dispatcher.off(event, callback)

    def listen(self, timeout: float | None = None) -> None:
        """Block and dispatch events until stop() is called or timeout expires."""
        self.start()
        if self._thread:
            self._thread.join(timeout)

    def start(self) -> None:
        """Start the event loop in a background daemon thread."""
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            args=(self._stop_event,),
            daemon=True,
            name="arctis-hid-poll",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the event loop to stop and wait for the thread to exit."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self._thread = None

    # ── OLED ───────────────────────────────────────────────────────────────

    @property
    def oled(self) -> "ArctisNovaProOled":
        if self._oled_controller is None:
            from .oled import ArctisNovaProOled
            self._oled_controller = ArctisNovaProOled(self._transport)
        return self._oled_controller  # type: ignore[return-value]

    # ── internal ───────────────────────────────────────────────────────────

    def _save(self) -> None:
        self._transport.write(C.CMD_SAVE)

    def _poll_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                packets = self._transport.poll(C.POLL_TIMEOUT_MS)
            except DeviceIOError:
                break
            for source, data in packets:
                self._process_packet(source, data)

    def _process_packet(self, source: str, data: list[int]) -> None:
        if len(data) < 2:
            return
        event = codec.decode_event(data)
        if event is not None:
            self._dispatcher.emit_typed(event)
