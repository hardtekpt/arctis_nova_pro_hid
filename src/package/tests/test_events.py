"""Tests for decode_event — all 22+ opcodes and _process_packet integration."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from arctis_hid.core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    WirelessMode,
)
from arctis_hid.devices.nova_pro.codec import _B5EventRaw, _B7EventRaw, decode_event
from arctis_hid.devices.nova_pro.models import (
    AncModeEvent,
    AudioOutputEvent,
    AutoOffEvent,
    BtAutoMuteEvent,
    BtDefaultEvent,
    ChatMixEvent,
    DimTimeoutEvent,
    EqBandEvent,
    EqPresetEvent,
    GainEvent,
    HomeScreenEvent,
    MicLedEvent,
    MicMuteEvent,
    MicVolumeEvent,
    OledBrightnessEvent,
    SidetoneEvent,
    StreamVolumesEvent,
    TransparencyEvent,
    VolumeEvent,
    WirelessModeEvent,
)

from .conftest import make_event_packet


# ── Helper ─────────────────────────────────────────────────────────────────────


def evt(opcode: int, *payload: int):
    return decode_event(make_event_packet(opcode, *payload))


# ── Firmware noise filter ───────────────────────────────────────────────────────


def test_opcode_0x10_returns_none():
    assert evt(0x10, 0x35) is None


# ── Unknown opcode ──────────────────────────────────────────────────────────────


def test_unknown_opcode_returns_none():
    assert evt(0xFF, 0x00) is None


# ── Short packet ────────────────────────────────────────────────────────────────


def test_packet_too_short_returns_none():
    assert decode_event([0x07, 0x25]) is None   # only 2 bytes, need >=4


# ── VolumeEvent (0x25) ──────────────────────────────────────────────────────────


def test_volume_event_type():
    assert isinstance(evt(0x25, 0x1C), VolumeEvent)


def test_volume_event_50_pct():
    result = evt(0x25, 0x1C)   # raw=28 → ~50%
    assert abs(result.percent - 50.0) < 1.0


def test_volume_event_100_pct():
    result = evt(0x25, 0x00)
    assert result.percent == pytest.approx(100.0)


def test_volume_event_0_pct():
    result = evt(0x25, 0x38)
    assert result.percent == pytest.approx(0.0)


# ── BatteryEvent (0xB7) ─────────────────────────────────────────────────────────


def test_battery_event_type():
    assert isinstance(evt(0xB7, 8, 4), _B7EventRaw)


def test_battery_event_fields():
    result = evt(0xB7, 8, 4)
    assert result.headset_pct == pytest.approx(100.0)
    assert result.dock_pct == pytest.approx(50.0)


# ── ConnectivityEvent (0xB5) ────────────────────────────────────────────────────


def test_connectivity_event_type():
    assert isinstance(evt(0xB5, 0x04, 0x01, 0x08), _B5EventRaw)


def test_connectivity_event_bt_active_true():
    # mode_raw=0x04 (WIRELESS_AND_BT) → bt_active derived as True by headset
    result = evt(0xB5, 0x04, 0x01, 0x08)
    assert result.mode_raw == 0x04


def test_connectivity_event_bt_active_true_when_data3_is_0x02():
    # Regression: mode=0x04 with data[3]=0x02 (BT device not connected)
    # mode_raw=0x04 still signals BT active, regardless of bt_connected.
    result = evt(0xB5, 0x04, 0x02, 0x08)
    assert result.mode_raw == 0x04
    assert result.bt_connected is False


def test_connectivity_event_bt_active_false_when_wireless_only():
    # mode_raw=0x01 (WIRELESS_ONLY) → bt_active derived as False by headset
    result = evt(0xB5, 0x01, 0x00, 0x08)
    assert result.mode_raw == 0x01


def test_connectivity_event_bt_pairing_mode():
    # mode_raw=0x02 (BT_PAIRING) → BtStatus.PAIRING derived by headset
    result = evt(0xB5, 0x02, 0x00, 0x08)
    assert result.mode_raw == 0x02


def test_connectivity_event_bt_connected_true():
    result = evt(0xB5, 0x04, 0x01, 0x08)   # data[3]=0x01 → BT device connected
    assert result.bt_connected is True


def test_connectivity_event_bt_connected_false():
    result = evt(0xB5, 0x04, 0x02, 0x08)   # data[3]=0x02 → BT device not connected
    assert result.bt_connected is False


def test_connectivity_event_bt_connected_false_when_wireless_only():
    result = evt(0xB5, 0x01, 0x00, 0x08)   # data[3]=0x00 → no BT device
    assert result.bt_connected is False


def test_connectivity_event_wireless_true():
    result = evt(0xB5, 0x01, 0x00, 0x08)
    assert result.wireless_raw == 0x08  # 0x08 → wireless=True when applied by headset


def test_connectivity_event_wireless_false():
    result = evt(0xB5, 0x01, 0x00, 0x04)   # SEARCHING (0x04) → wireless=False
    assert result.wireless_raw == 0x04  # 0x04 → wireless=False when applied by headset


# ── OledBrightnessEvent (0x85) ──────────────────────────────────────────────────


def test_oled_brightness_event():
    result = evt(0x85, 7)
    assert isinstance(result, OledBrightnessEvent)
    assert result.level == 7


# ── SidetoneEvent (0x39) ────────────────────────────────────────────────────────


def test_sidetone_event_medium():
    result = evt(0x39, 2)
    assert isinstance(result, SidetoneEvent)
    assert result.level == SidetoneLevel.MEDIUM


def test_sidetone_event_off():
    result = evt(0x39, 0)
    assert result.level == SidetoneLevel.OFF


# ── AncModeEvent (0xBD) ─────────────────────────────────────────────────────────


def test_anc_mode_event_anc():
    result = evt(0xBD, 2)
    assert isinstance(result, AncModeEvent)
    assert result.mode == AncMode.ANC


def test_anc_mode_event_off():
    assert evt(0xBD, 0).mode == AncMode.OFF


def test_anc_mode_event_transparency():
    assert evt(0xBD, 1).mode == AncMode.TRANSPARENCY


# ── MicMuteEvent (0xBB) ─────────────────────────────────────────────────────────


def test_mic_mute_event_muted():
    result = evt(0xBB, 1)
    assert isinstance(result, MicMuteEvent)
    assert result.muted is True


def test_mic_mute_event_unmuted():
    assert evt(0xBB, 0).muted is False


# ── ChatMixEvent (0x45) ─────────────────────────────────────────────────────────


def test_chatmix_event():
    result = evt(0x45, 70, 30)
    assert isinstance(result, ChatMixEvent)
    assert result.game == 70
    assert result.chat == 30


# ── GainEvent (0x27) ────────────────────────────────────────────────────────────


def test_gain_event_low():
    result = evt(0x27, 1)
    assert isinstance(result, GainEvent)
    assert result.level == GainLevel.LOW


def test_gain_event_high():
    result = evt(0x27, 2)
    assert result.level == GainLevel.HIGH


# ── MicVolumeEvent (0x37) ───────────────────────────────────────────────────────


def test_mic_volume_event():
    result = evt(0x37, 5)
    assert isinstance(result, MicVolumeEvent)
    assert result.level == 5


# ── DimTimeoutEvent (0x83) ──────────────────────────────────────────────────────


def test_dim_timeout_event():
    result = evt(0x83, 3)
    assert isinstance(result, DimTimeoutEvent)
    assert result.step == TimeoutStep.TEN_MIN


# ── HomeScreenEvent (0x89) ──────────────────────────────────────────────────────


def test_home_screen_event_simple():
    result = evt(0x89, 1)
    assert isinstance(result, HomeScreenEvent)
    assert result.mode == HomeScreenMode.SIMPLE


def test_home_screen_event_detailed():
    assert evt(0x89, 0).mode == HomeScreenMode.DETAILED


# ── MicLedEvent (0xBF) ──────────────────────────────────────────────────────────


def test_mic_led_event():
    result = evt(0xBF, 6)
    assert isinstance(result, MicLedEvent)
    assert result.level == 6


# ── AutoOffEvent (0xC1) ─────────────────────────────────────────────────────────


def test_auto_off_event():
    result = evt(0xC1, 5)
    assert isinstance(result, AutoOffEvent)
    assert result.step == TimeoutStep.THIRTY_MIN


# ── TransparencyEvent (0xB9) ────────────────────────────────────────────────────


def test_transparency_event():
    result = evt(0xB9, 8)
    assert isinstance(result, TransparencyEvent)
    assert result.level == 8


# ── WirelessModeEvent (0xC3) ────────────────────────────────────────────────────


def test_wireless_mode_event_extended():
    result = evt(0xC3, 1)
    assert isinstance(result, WirelessModeEvent)
    assert result.mode == WirelessMode.EXTENDED_RANGE


def test_wireless_mode_event_performance():
    assert evt(0xC3, 0).mode == WirelessMode.PERFORMANCE


# ── BtDefaultEvent (0xB2) ───────────────────────────────────────────────────────


def test_bt_default_event_on():
    result = evt(0xB2, 1)
    assert isinstance(result, BtDefaultEvent)
    assert result.enabled is True


def test_bt_default_event_off():
    assert evt(0xB2, 0).enabled is False


# ── BtAutoMuteEvent (0xB3) ──────────────────────────────────────────────────────


def test_bt_auto_mute_event_full():
    result = evt(0xB3, 2)
    assert isinstance(result, BtAutoMuteEvent)
    assert result.mode == BtAutoMute.FULL


def test_bt_auto_mute_event_minus_12db():
    assert evt(0xB3, 1).mode == BtAutoMute.DB_MINUS_12


def test_bt_auto_mute_event_off():
    assert evt(0xB3, 0).mode == BtAutoMute.OFF


# ── StreamVolumesEvent (0x47) ───────────────────────────────────────────────────


def test_stream_volumes_event():
    # data layout: data[2]=main, data[3]=0x00 padding, data[4]=aux, data[5]=mic
    result = evt(0x47, 80, 0x00, 60, 40)
    assert isinstance(result, StreamVolumesEvent)
    assert result.main == 80
    assert result.aux == 60
    assert result.mic == 40


# ── AudioOutputEvent (0x43) ─────────────────────────────────────────────────────


def test_audio_output_event_stream():
    result = evt(0x43, 2)
    assert isinstance(result, AudioOutputEvent)
    assert result.output == AudioOutput.STREAM


def test_audio_output_event_speakers():
    assert evt(0x43, 1).output == AudioOutput.SPEAKERS


# ── EqPresetEvent (0x2E) ────────────────────────────────────────────────────────


def test_eq_preset_event_custom():
    result = evt(0x2E, 4)
    assert isinstance(result, EqPresetEvent)
    assert result.index == 4


def test_eq_preset_event_named():
    assert evt(0x2E, 0).index == 0


# ── EqBandEvent (0x31) ──────────────────────────────────────────────────────────


def test_eq_band_event():
    result = evt(0x31, 3, 25)
    assert isinstance(result, EqBandEvent)
    assert result.band == 3
    assert result.level == 25


# ── _process_packet integration ─────────────────────────────────────────────────


class TestProcessPacket:
    def setup_method(self):
        from arctis_hid.core.dispatcher import EventDispatcher
        from arctis_hid.devices.nova_pro.headset import ArctisNovaProWireless
        self.headset = ArctisNovaProWireless(b"/fake", b"/fake2")
        self.headset._transport = MagicMock()
        self.received = []
        self.headset.on("VolumeEvent", self.received.append)

    def test_process_packet_emits_decoded_event(self):
        pkt = make_event_packet(0x25, 0x00)   # 100% volume
        self.headset._process_packet("EVT", pkt)
        assert len(self.received) == 1
        assert isinstance(self.received[0], VolumeEvent)
        assert self.received[0].percent == pytest.approx(100.0)

    def test_process_packet_firmware_noise_not_emitted(self):
        pkt = make_event_packet(0x10, 0x35, 0x2E, 0x31)
        self.headset._process_packet("CTRL", pkt)
        assert self.received == []

    def test_process_packet_too_short_does_not_raise(self):
        self.headset._process_packet("EVT", [0x07])   # 1 byte — must not raise

    def test_process_packet_unknown_opcode_not_emitted(self):
        pkt = make_event_packet(0xFF, 0x00)
        self.headset._process_packet("EVT", pkt)
        assert self.received == []
