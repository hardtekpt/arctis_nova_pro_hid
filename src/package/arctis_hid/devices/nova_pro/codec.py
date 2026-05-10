"""Encode and decode all Nova Pro HID packets.

All protocol quirks are isolated here so the rest of the package
works with clean Python types and never touches raw byte values.
"""
from __future__ import annotations

from typing import Any

from ...core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    ConnectivityMode,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    WirelessMode,
)
from . import constants as C
from .models import (
    AncModeEvent,
    AudioOutputEvent,
    AutoOffEvent,
    BatteryEvent,
    BtAutoMuteEvent,
    BtDefaultEvent,
    ChatMixEvent,
    ConnectivityData,
    ConnectivityEvent,
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
    VolumeEvent,
    WirelessModeEvent,
)

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


# ── 0xB0 status packet ─────────────────────────────────────────────────────

def decode_status_packet(data: list[int]) -> StatusData:
    return StatusData(
        headset_battery_pct = decode_battery(data[C.B0_HBAT]),
        dock_battery_pct    = decode_battery(data[C.B0_DBAT]),
        connectivity_mode   = ConnectivityMode(data[C.B0_CONN]),
        bt_active           = data[C.B0_BT] == 0x01,
        mic_muted           = data[C.B0_MUTE] == 0x01,
        anc_mode            = AncMode(data[C.B0_ANC]),
        mic_led_brightness  = data[C.B0_MIC_LED],
        wireless_mode       = WirelessMode(data[C.B0_MODE2G]),
        bt_default          = data[C.B0_BT_DEFAULT] == 0x01,
        bt_auto_mute        = BtAutoMute(data[C.B0_BT_AUTOMUTE]),
        auto_off_timeout    = TimeoutStep(data[C.B0_AUTO_OFF]),
    )


# ── 0xB5 connectivity query packet ────────────────────────────────────────

def decode_connectivity_packet(data: list[int]) -> ConnectivityData:
    return ConnectivityData(
        connectivity_mode = ConnectivityMode(data[C.B5_CONN]),
        bt_connected      = data[C.B5_BT_CONNECTED] == 0x01,
    )


# ── 0x80 display settings packet ──────────────────────────────────────────

def decode_display_packet(data: list[int]) -> DisplayData:
    return DisplayData(
        dim_timeout      = TimeoutStep(data[C.B80_DIM_TIMEOUT]),
        oled_brightness  = data[C.B80_OLED_BRIGHT],
        home_screen_mode = HomeScreenMode(data[C.B80_HOME_SCREEN]),
    )


# ── 0x20 mic/EQ packet ─────────────────────────────────────────────────────

def decode_mic_eq_packet(data: list[int]) -> MicEqData:
    return MicEqData(
        volume_pct      = decode_volume(data[C.M20_VOL]),
        gain            = decode_gain_query(data[C.M20_GAIN]),
        eq_preset_index = data[C.M20_EQ_PRESET],
        eq_bands        = list(data[C.M20_EQ]),
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
# Maps opcode (data[1]) → typed event dataclass, or None for unknown/noise.

_EVT_CMD = {
    0x10: None,  # unsolicited firmware version noise on Col01 — filter out
}


def decode_event(data: list[int]) -> Any | None:
    if len(data) < 4:
        return None
    cmd = data[1]

    if cmd == 0x10:
        return None  # firmware push noise

    if cmd == 0x25:
        return VolumeEvent(percent=decode_volume(data[2]))

    if cmd == 0xB7:
        return BatteryEvent(
            headset_pct=decode_battery(data[2]),
            dock_pct=decode_battery(data[3]),
        )

    if cmd == 0xB5:
        return ConnectivityEvent(
            mode=ConnectivityMode(data[2]),
            bt_active=data[3] == 0x01,
            wireless=data[4] == 0x08,
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
