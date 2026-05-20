from __future__ import annotations

import threading
from typing import Callable

import hid

_RECONNECT_INTERVAL_S = 2.0

from ...core.dispatcher import EventDispatcher
from ...core.transport import HidTransport
from ...core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    BtStatus,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    UsbInput,
    WirelessMode,
)
from ...exceptions import DeviceIOError
from ..base import AbstractHeadset, AbstractOled
from . import constants as C
from . import codec
from .models import (
    BatteryData,
    BatteryEvent,
    ConnectivityEvent,
    ConnectivityStatus,
    DeviceDisconnectedEvent,
    DeviceReconnectedEvent,
    DisplayData,
    MicEqData,
    StatusData,
    VolumeLimiterData,
)


class ArctisNovaProWireless(AbstractHeadset):
    """HID API for the SteelSeries Arctis Nova Pro Wireless (and variants).

    Usage — command mode::

        with discover() as h:
            print(h.get_status())
            print(h.connectivity)
            h.set_volume(75)

    Usage — event mode::

        with discover() as h:
            h.on("ConnectivityEvent", lambda e: print(e.connectivity))
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

        # ── internal connectivity state ────────────────────────────────────
        # Updated incrementally by queries and events; never exposed directly.
        self._cs_usb:           bool = True   # True from the moment the instance is created
        self._cs_headset_power: bool = False  # unknown until first query
        self._cs_wireless_raw:  int  = 0x00  # 0x00=unknown, 0x04=searching, 0x08=active
        self._cs_mode_raw:      int  = 0x01  # default: WIRELESS_ONLY
        self._cs_bt_active:     bool = False
        self._cs_bt_connected:  bool = False

    # ── lifecycle ──────────────────────────────────────────────────────────

    def open(self) -> None:
        self._transport.open(self._ctrl_path, self._evt_path)

    def close(self) -> None:
        self.stop()
        self._transport.close()

    # ── connectivity ───────────────────────────────────────────────────────

    @property
    def connectivity(self) -> ConnectivityStatus:
        """Live connectivity state, derived from all query and event sources."""
        return self._build_connectivity()

    def _build_connectivity(self) -> ConnectivityStatus:
        """Build a ConnectivityStatus from the current internal scalars."""
        return ConnectivityStatus(
            usb           = self._cs_usb,
            headset_power = self._cs_headset_power,
            wireless      = codec._derive_wireless(self._cs_wireless_raw, self._cs_mode_raw),
            bt            = codec._derive_bt_status(
                                self._cs_mode_raw,
                                self._cs_bt_active,
                                self._cs_bt_connected,
                            ),
        )

    # ── queries ────────────────────────────────────────────────────────────

    def get_status(self) -> StatusData:
        data = self._transport.query(C.CMD_STATUS)
        self._apply_b0_conn(codec.decode_b0_conn(data))
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

    def get_connectivity(self) -> ConnectivityStatus:
        """Query 0xB5 and return the updated ConnectivityStatus."""
        data = self._transport.query(C.CMD_CONNECTIVITY)
        self._apply_b5_conn(codec.decode_b5_query(data), from_event=False)
        return self.connectivity

    def get_display(self) -> DisplayData:
        data = self._transport.query(C.CMD_DISPLAY)
        return codec.decode_display_packet(data)

    def get_volume_limiter(self) -> VolumeLimiterData:
        data = self._transport.query(C.CMD_VOL_LIMITER)
        return codec.decode_vol_limiter_packet(data)

    def get_battery(self) -> BatteryData:
        data = self._transport.query(C.CMD_BATTERY)
        self._cs_headset_power = data[C.B7_PWR] == 0x08
        return codec.decode_battery_packet(data)

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

    def set_usb_input(self, input: UsbInput) -> None:
        """Select USB input. Note: no Col02 event fires — no query reflects this value."""
        self._transport.write(C.CMD_USB_INPUT, [int(input)])
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

    # ── internal — connectivity state ──────────────────────────────────────

    def _apply_b0_conn(self, raw: codec._B0ConnRaw) -> None:
        """Apply connectivity/power fields from a 0xB0 status packet.

        Updates mode_raw, bt_active, headset_power, and wireless_raw
        (wireless_raw is only updated when the packet carries a non-zero value).
        bt_connected is NOT available in 0xB0 and is intentionally left unchanged.
        """
        self._cs_mode_raw      = raw.mode_raw
        self._cs_bt_active     = raw.bt_active
        self._cs_headset_power = raw.headset_power
        if raw.wireless_raw != 0x00:
            self._cs_wireless_raw = raw.wireless_raw

    def _apply_b5_conn(self, raw: codec._B5QueryRaw | codec._B5EventRaw, *, from_event: bool) -> None:
        """Apply connectivity fields from a 0xB5 query or event packet.

        For query (from_event=False): updates mode_raw, bt_connected.
        For event (from_event=True): also updates wireless_raw (if non-zero)
        and derives bt_active from mode_raw.
        bt_active is NOT carried in the 0xB5 query path.
        """
        self._cs_mode_raw    = raw.mode_raw
        self._cs_bt_connected = raw.bt_connected
        if from_event:
            # Derive bt_active from mode: BT is "active" when mode includes BT
            self._cs_bt_active = raw.mode_raw in (0x02, 0x04)
            if hasattr(raw, "wireless_raw") and raw.wireless_raw != 0x00:  # type: ignore[union-attr]
                self._cs_wireless_raw = raw.wireless_raw  # type: ignore[union-attr]

    # ── internal — poll loop ───────────────────────────────────────────────

    def _save(self) -> None:
        self._transport.write(C.CMD_SAVE)

    def _poll_loop(self, stop_event: threading.Event) -> None:
        while not stop_event.is_set():
            try:
                packets = self._transport.poll(C.POLL_TIMEOUT_MS)
            except DeviceIOError:
                self._transport.close()
                self._cs_usb = False
                self._dispatcher.emit_typed(DeviceDisconnectedEvent())
                if not self._reconnect_until_found(stop_event):
                    break
                self._cs_usb = True
                self._dispatcher.emit_typed(DeviceReconnectedEvent())
                continue
            for source, data in packets:
                self._process_packet(source, data)

    def _reconnect_until_found(self, stop_event: threading.Event) -> bool:
        """Retry opening the HID device until it reappears or stop is requested.

        Returns True when reconnected, False if stop was requested.
        """
        while not stop_event.is_set():
            try:
                ctrl_path, evt_path = self._find_device_paths()
                self._ctrl_path = ctrl_path
                self._evt_path  = evt_path
                self._transport.open(ctrl_path, evt_path)
                return True
            except Exception:
                stop_event.wait(_RECONNECT_INTERVAL_S)
        return False

    def _find_device_paths(self) -> tuple[bytes, bytes | None]:
        """Enumerate HID devices to locate the ctrl and evt paths."""
        ctrl_path: bytes | None = None
        evt_path:  bytes | None = None
        for info in hid.enumerate():
            if info["vendor_id"] != C.VID:
                continue
            if info["product_id"] not in C.PIDS:
                continue
            if info["interface_number"] != C.INTERFACE:
                continue
            usage = info.get("usage_page", 0)
            path  = info["path"]
            if usage == C.USAGE_CONTROL and ctrl_path is None:
                ctrl_path = path
            elif usage == C.USAGE_EVENTS and evt_path is None:
                evt_path = path
        if ctrl_path is None:
            raise DeviceIOError("device not found during reconnection scan")
        return ctrl_path, evt_path

    def _process_packet(self, source: str, data: list[int]) -> None:
        if len(data) < 2:
            return
        event = codec.decode_event(data)
        if event is None:
            return
        if isinstance(event, codec._B5EventRaw):
            self._apply_b5_conn(event, from_event=True)
            self._dispatcher.emit_typed(ConnectivityEvent(connectivity=self.connectivity))
        elif isinstance(event, codec._B7EventRaw):
            self._cs_headset_power = event.headset_power
            self._dispatcher.emit_typed(BatteryEvent(
                headset_pct=event.headset_pct,
                dock_pct=event.dock_pct,
            ))
            self._dispatcher.emit_typed(ConnectivityEvent(connectivity=self.connectivity))
        else:
            self._dispatcher.emit_typed(event)
