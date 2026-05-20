"""Encode and decode all Nova Pro HID packets.

All protocol quirks are isolated here so the rest of the package
works with clean Python types and never touches raw byte values.
"""
from __future__ import annotations

from typing import Any, NamedTuple

from ...core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    BtStatus,
    ConnectivityMode,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    WirelessLinkState,
    WirelessMode,
)
from . import constants as C
from .models import (
    AncModeEvent,
    AudioOutputEvent,
    AutoOffEvent,
    BatteryData,
    BatteryEvent,
    BtAutoMuteEvent,
    BtDefaultEvent,
    ChatMixEvent,
    DimTimeoutEvent,
    DisplayData,
    EqBandEvent,
    EqPresetEvent,
    GainEvent,
    HomeScreenEvent,
    MicEqData,
    MicLedEvent,
    MicMuteEvent,
    MicVolumeEvent,
    OledBrightnessEvent,
    SidetoneEvent,
    StatusData,
    StreamVolumesEvent,
    TransparencyEvent,
    VolumeLimiterData,
    VolumeEvent,
    WirelessModeEvent,
)

# ── Private intermediate types ─────────────────────────────────────────────
# Used internally between codec and headset to carry raw connectivity bytes.
# Not part of the public API.

class _B0ConnRaw(NamedTuple):
    """Connectivity/power fields extracted from a 0xB0 status packet."""
    mode_raw:      int    # B0[4]: 0x01=wireless-only, 0x02=BT-pairing, 0x04=wireless+BT
    bt_active:     bool   # B0[5]: 0x01=True
    wireless_raw:  int    # B0[14]: 0x00=ignore, 0x04=searching, 0x08=active
    headset_power: bool   # B0[15]: 0x08=True


class _B5QueryRaw(NamedTuple):
    """Connectivity fields extracted from a 0xB5 query response."""
    mode_raw:     int    # B5[2]: 0x01/0x02/0x04
    bt_connected: bool   # B5[3]: 0x01=True


class _B5EventRaw(NamedTuple):
    """Connectivity fields from a 0xB5 Col02 event packet."""
    mode_raw:     int    # data[2]
    bt_connected: bool   # data[3]: 0x01=True
    wireless_raw: int    # data[4]: 0x00=ignore, 0x04=searching, 0x08=active


class _B7EventRaw(NamedTuple):
    """Battery + power fields from a 0xB7 Col02 event packet."""
    headset_pct:   float
    dock_pct:      float
    headset_power: bool   # data[4]: 0x08=True


# ── Connectivity derivation helpers ───────────────────────────────────────

def _derive_bt_status(mode_raw: int, bt_active: bool, bt_connected: bool) -> BtStatus:
    """Derive BtStatus from the three raw connectivity scalars.

    Priority: CONNECTED > PAIRING > ON > OFF.
    bt_connected is False when derived from 0xB0 alone (not available in that packet).
    """
    if bt_connected:
        return BtStatus.CONNECTED
    if mode_raw == 0x02:
        return BtStatus.PAIRING
    if mode_raw == 0x04 or bt_active:
        return BtStatus.ON
    return BtStatus.OFF


def _derive_wireless(wireless_raw: int, mode_raw: int) -> bool:
    """Derive wireless active state from wireless_raw with mode_raw fallback.

    wireless_raw 0x08 = active, 0x04 = searching (off), 0x00 = unknown.
    When unknown, mode_raw 0x01 (WIRELESS_ONLY) or 0x04 (WIRELESS_AND_BT) imply wireless is up.
    """
    if wireless_raw == 0x08:
        return True
    if wireless_raw == 0x04:
        return False
    return mode_raw in (0x01, 0x04)


# ── Volume ─────────────────────────────────────────────────────────────────
# Inverted: 0x38 (56) = 0%,  0x00 = 100%

def encode_volume(pct: float) -> int:
    return round((1.0 - max(0.0, min(100.0, pct)) / 100.0) * 56)


def decode_volume(raw: int) -> float:
    return max(0.0, min(100.0, (0x38 - raw) / 56 * 100))


# ── Battery ────────────────────────────────────────────────────────────────

def decode_battery(raw: int) -> float:
    return min(100.0, raw / 8 * 100)


# ── Gain ───────────────────────────────────────────────────────────────────
# Write, event, and query all use the same encoding: 0x01 = low, 0x02 = high.

def encode_gain(level: GainLevel) -> int:
    return 0x02 if level == GainLevel.HIGH else 0x01


def decode_gain_query(raw: int) -> GainLevel:
    return GainLevel.LOW if raw == 0x01 else GainLevel.HIGH


def decode_gain_event(raw: int) -> GainLevel:
    return GainLevel.LOW if raw == 0x01 else GainLevel.HIGH


# ── ASCII string packets (0x10 firmware, 0x12 serial) ──────────────────────

def decode_ascii_response(data: list[int]) -> str:
    payload = bytes(data[2:])
    return payload.split(b"\x00")[0].decode("ascii", errors="replace")


# ── 0xB0 connectivity/power extraction ────────────────────────────────────

def decode_b0_conn(data: list[int]) -> _B0ConnRaw:
    """Extract connectivity and power fields from a 0xB0 status packet."""
    return _B0ConnRaw(
        mode_raw      = data[C.B0_CONN],
        bt_active     = data[C.B0_BT] == 0x01,
        wireless_raw  = data[C.B0_WIRELESS_LINK],
        headset_power = data[C.B0_PWR] == 0x08,
    )


# ── 0xB0 status packet ─────────────────────────────────────────────────────

def decode_status_packet(data: list[int]) -> StatusData:
    mode_raw    = data[C.B0_CONN]
    bt_active   = data[C.B0_BT] == 0x01
    wireless_raw = data[C.B0_WIRELESS_LINK]
    return StatusData(
        headset_battery_pct = decode_battery(data[C.B0_HBAT]),
        dock_battery_pct    = decode_battery(data[C.B0_DBAT]),
        transparency_level  = data[C.B0_TRANSP_LEVEL],
        mic_muted           = data[C.B0_MUTE] == 0x01,
        anc_mode            = AncMode(data[C.B0_ANC]),
        mic_led_brightness  = data[C.B0_MIC_LED],
        wireless_mode       = WirelessMode(data[C.B0_MODE2G]),
        bt_default          = data[C.B0_BT_DEFAULT] == 0x01,
        bt_auto_mute        = BtAutoMute(data[C.B0_BT_AUTOMUTE]),
        auto_off_timeout    = TimeoutStep(data[C.B0_AUTO_OFF]),
        headset_power       = data[C.B0_PWR] == 0x08,
        wireless            = _derive_wireless(wireless_raw, mode_raw),
        bt                  = _derive_bt_status(mode_raw, bt_active, bt_connected=False),
    )


# ── 0xB5 connectivity query extraction ────────────────────────────────────

def decode_b5_query(data: list[int]) -> _B5QueryRaw:
    """Extract connectivity fields from a 0xB5 query response."""
    return _B5QueryRaw(
        mode_raw     = data[C.B5_CONN],
        bt_connected = data[C.B5_BT_CONNECTED] == 0x01,
    )


# ── 0x26 volume limiter packet ────────────────────────────────────────────

def decode_vol_limiter_packet(data: list[int]) -> VolumeLimiterData:
    return VolumeLimiterData(
        limiter_on = data[C.B26_LIMITER] == 0x01,
    )


# ── 0xB7 battery query packet ─────────────────────────────────────────────

def decode_battery_packet(data: list[int]) -> BatteryData:
    return BatteryData(
        headset_pct    = decode_battery(data[C.B7_HBAT]),
        dock_pct       = decode_battery(data[C.B7_DBAT]),
        headset_powered = data[C.B7_PWR] == 0x08,
    )


# ── 0x80 display settings packet ──────────────────────────────────────────

def decode_display_packet(data: list[int]) -> DisplayData:
    return DisplayData(
        dim_timeout      = TimeoutStep(data[C.B80_DIM_TIMEOUT]),
        oled_brightness  = data[C.B80_OLED_BRIGHT],
        home_screen_mode = HomeScreenMode(data[C.B80_HOME_SCREEN]),
        sonar_running    = data[C.B80_SONAR] == 0x01,
    )


# ── 0x20 mic/EQ packet ─────────────────────────────────────────────────────

def decode_mic_eq_packet(data: list[int]) -> MicEqData:
    return MicEqData(
        volume_pct      = decode_volume(data[C.M20_VOL]),
        gain            = decode_gain_query(data[C.M20_GAIN]),
        eq_preset_index = data[C.M20_EQ_PRESET],
        eq_bands        = list(data[C.M20_EQ]),
        usb_input       = data[C.M20_USB],
        mic_volume      = data[C.M20_MICVOL],
        sidetone        = SidetoneLevel(data[C.M20_SIDETONE]),
        audio_output    = AudioOutput(data[C.M20_AUDIO]),
        chatmix_game    = data[C.M20_GAME],
        chatmix_chat    = data[C.M20_CHAT],
        stream_main_vol = data[C.M20_SMAIN],
        stream_aux_vol  = data[C.M20_SAUX],
        stream_mic_vol  = data[C.M20_SMIC],
    )


# ── Event decoder ──────────────────────────────────────────────────────────
# Maps opcode (data[1]) → typed event dataclass or private raw container,
# or None for unknown/noise.
#
# 0xB5 and 0xB7 return private _B5EventRaw / _B7EventRaw NamedTuples.
# headset._process_packet handles these specially to update ConnectivityStatus
# before emitting the public ConnectivityEvent / BatteryEvent.

def decode_event(data: list[int]) -> Any | None:
    if len(data) < 4:
        return None
    cmd = data[1]

    if cmd == 0x10:
        return None  # firmware push noise

    if cmd == 0x25:
        return VolumeEvent(percent=decode_volume(data[2]))

    if cmd == 0xB7:
        return _B7EventRaw(
            headset_pct   = decode_battery(data[2]),
            dock_pct      = decode_battery(data[3]),
            headset_power = data[4] == 0x08,
        )

    if cmd == 0xB5:
        return _B5EventRaw(
            mode_raw     = data[2],
            bt_connected = data[3] == 0x01,
            wireless_raw = data[C.B5_WIRELESS_LINK],
        )

    if cmd == 0x85:
        return OledBrightnessEvent(level=data[2])

    if cmd == 0x39:
        return SidetoneEvent(level=SidetoneLevel(data[2]))

    if cmd == 0xBD:
        return AncModeEvent(mode=AncMode(data[2]))

    if cmd == 0xBB:
        return MicMuteEvent(muted=data[2] == 0x01)

    if cmd == 0x45:
        return ChatMixEvent(game=data[2], chat=data[3])

    if cmd == 0x27:
        return GainEvent(level=decode_gain_event(data[2]))

    if cmd == 0x37:
        return MicVolumeEvent(level=data[2])

    if cmd == 0x83:
        return DimTimeoutEvent(step=TimeoutStep(data[2]))

    if cmd == 0x89:
        return HomeScreenEvent(mode=HomeScreenMode(data[2]))

    if cmd == 0xBF:
        return MicLedEvent(level=data[2])

    if cmd == 0xC1:
        return AutoOffEvent(step=TimeoutStep(data[2]))

    if cmd == 0xB9:
        return TransparencyEvent(level=data[2])

    if cmd == 0xC3:
        return WirelessModeEvent(mode=WirelessMode(data[2]))

    if cmd == 0xB2:
        return BtDefaultEvent(enabled=data[2] == 0x01)

    if cmd == 0xB3:
        return BtAutoMuteEvent(mode=BtAutoMute(data[2]))

    if cmd == 0x47:
        return StreamVolumesEvent(main=data[2], aux=data[4], mic=data[5])

    if cmd == 0x43:
        return AudioOutputEvent(output=AudioOutput(data[2]))

    if cmd == 0x2E:
        return EqPresetEvent(index=data[2])

    if cmd == 0x31:
        return EqBandEvent(band=data[2], level=data[3])

    return None
