"""Tests for StatusData, MicEqData, and event dataclasses — API contract validation."""
from __future__ import annotations

import dataclasses

import pytest

from arctis_hid.core.types import (
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
from arctis_hid.devices.nova_pro.models import (
    AncModeEvent,
    AudioOutputEvent,
    AutoOffEvent,
    BatteryEvent,
    BtAutoMuteEvent,
    BtDefaultEvent,
    ChatMixEvent,
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


# ── StatusData ─────────────────────────────────────────────────────────────────


class TestStatusData:
    def _make(self, **kwargs) -> StatusData:
        defaults = dict(
            headset_battery_pct=100.0,
            dock_battery_pct=50.0,
            connectivity_mode=ConnectivityMode.WIRELESS_ONLY,
            bt_active=False,
            mic_muted=False,
            anc_mode=AncMode.OFF,
            mic_led_brightness=5,
            wireless_mode=WirelessMode.PERFORMANCE,
            bt_default=False,
            bt_auto_mute=BtAutoMute.OFF,
            auto_off_timeout=TimeoutStep.OFF,
        )
        return StatusData(**{**defaults, **kwargs})

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(StatusData)

    def test_headset_battery_pct_is_float(self):
        sd = self._make(headset_battery_pct=75.0)
        assert isinstance(sd.headset_battery_pct, float)

    def test_dock_battery_pct_is_float(self):
        sd = self._make(dock_battery_pct=25.0)
        assert isinstance(sd.dock_battery_pct, float)

    def test_bt_active_is_bool(self):
        assert isinstance(self._make(bt_active=True).bt_active, bool)

    def test_mic_muted_is_bool(self):
        assert isinstance(self._make(mic_muted=True).mic_muted, bool)

    def test_anc_mode_is_anc_mode(self):
        assert isinstance(self._make().anc_mode, AncMode)

    def test_wireless_mode_is_wireless_mode(self):
        assert isinstance(self._make().wireless_mode, WirelessMode)

    def test_field_values_stored_correctly(self):
        sd = self._make(headset_battery_pct=80.0, mic_muted=True, anc_mode=AncMode.ANC)
        assert sd.headset_battery_pct == 80.0
        assert sd.mic_muted is True
        assert sd.anc_mode == AncMode.ANC


# ── MicEqData ──────────────────────────────────────────────────────────────────


class TestMicEqData:
    def _make(self, **kwargs) -> MicEqData:
        defaults = dict(volume_pct=50.0, gain=GainLevel.LOW, eq_preset_index=0)
        return MicEqData(**{**defaults, **kwargs})

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(MicEqData)

    def test_eq_bands_default_is_empty_list(self):
        result = self._make()
        assert result.eq_bands == []

    def test_eq_bands_default_is_independent_per_instance(self):
        a = self._make()
        b = self._make()
        a.eq_bands.append(99)
        assert b.eq_bands == []    # default_factory means they're different lists

    def test_sidetone_default_is_off(self):
        assert self._make().sidetone == SidetoneLevel.OFF

    def test_audio_output_default_is_speakers(self):
        assert self._make().audio_output == AudioOutput.SPEAKERS

    def test_chatmix_defaults_to_100(self):
        result = self._make()
        assert result.chatmix_game == 100
        assert result.chatmix_chat == 100

    def test_stream_volumes_default_to_100(self):
        result = self._make()
        assert result.stream_main_vol == 100
        assert result.stream_aux_vol == 100
        assert result.stream_mic_vol == 100

    def test_volume_pct_stored(self):
        assert self._make(volume_pct=75.0).volume_pct == 75.0

    def test_gain_stored(self):
        assert self._make(gain=GainLevel.HIGH).gain == GainLevel.HIGH


# ── DisplayData ────────────────────────────────────────────────────────────────


class TestDisplayData:
    def _make(self, **kwargs) -> DisplayData:
        defaults = dict(
            dim_timeout=TimeoutStep.OFF,
            oled_brightness=5,
            home_screen_mode=HomeScreenMode.DETAILED,
        )
        return DisplayData(**{**defaults, **kwargs})

    def test_is_dataclass(self):
        assert dataclasses.is_dataclass(DisplayData)

    def test_dim_timeout_is_timeout_step(self):
        assert isinstance(self._make().dim_timeout, TimeoutStep)

    def test_oled_brightness_stored(self):
        assert self._make(oled_brightness=8).oled_brightness == 8

    def test_home_screen_mode_is_home_screen_mode(self):
        assert isinstance(self._make().home_screen_mode, HomeScreenMode)

    def test_field_values_stored_correctly(self):
        dd = self._make(
            dim_timeout=TimeoutStep.THIRTY_MIN,
            oled_brightness=3,
            home_screen_mode=HomeScreenMode.SIMPLE,
        )
        assert dd.dim_timeout == TimeoutStep.THIRTY_MIN
        assert dd.oled_brightness == 3
        assert dd.home_screen_mode == HomeScreenMode.SIMPLE


# ── Event dataclasses — field types and values ─────────────────────────────────


class TestEventDataclasses:
    def test_volume_event(self):
        e = VolumeEvent(percent=75.0)
        assert e.percent == 75.0
        assert isinstance(e.percent, float)

    def test_battery_event(self):
        e = BatteryEvent(headset_pct=100.0, dock_pct=50.0)
        assert e.headset_pct == 100.0
        assert e.dock_pct == 50.0

    def test_connectivity_event(self):
        e = ConnectivityEvent(mode=ConnectivityMode.WIRELESS_AND_BT, bt_active=True, bt_connected=True, wireless=True)
        assert e.mode == ConnectivityMode.WIRELESS_AND_BT
        assert e.bt_active is True
        assert e.bt_connected is True
        assert e.wireless is True

    def test_anc_mode_event(self):
        e = AncModeEvent(mode=AncMode.ANC)
        assert e.mode == AncMode.ANC

    def test_mic_mute_event(self):
        assert MicMuteEvent(muted=True).muted is True
        assert MicMuteEvent(muted=False).muted is False

    def test_chatmix_event(self):
        e = ChatMixEvent(game=70, chat=30)
        assert e.game == 70
        assert e.chat == 30

    def test_gain_event(self):
        assert GainEvent(level=GainLevel.HIGH).level == GainLevel.HIGH

    def test_mic_volume_event(self):
        assert MicVolumeEvent(level=7).level == 7

    def test_sidetone_event(self):
        assert SidetoneEvent(level=SidetoneLevel.MEDIUM).level == SidetoneLevel.MEDIUM

    def test_oled_brightness_event(self):
        assert OledBrightnessEvent(level=8).level == 8

    def test_transparency_event(self):
        assert TransparencyEvent(level=5).level == 5

    def test_wireless_mode_event(self):
        assert WirelessModeEvent(mode=WirelessMode.EXTENDED_RANGE).mode == WirelessMode.EXTENDED_RANGE

    def test_bt_default_event(self):
        assert BtDefaultEvent(enabled=True).enabled is True

    def test_bt_auto_mute_event(self):
        assert BtAutoMuteEvent(mode=BtAutoMute.FULL).mode == BtAutoMute.FULL

    def test_audio_output_event(self):
        assert AudioOutputEvent(output=AudioOutput.STREAM).output == AudioOutput.STREAM

    def test_stream_volumes_event(self):
        e = StreamVolumesEvent(main=80, aux=60, mic=40)
        assert e.main == 80
        assert e.aux == 60
        assert e.mic == 40

    def test_eq_preset_event(self):
        assert EqPresetEvent(index=4).index == 4

    def test_eq_band_event(self):
        e = EqBandEvent(band=3, level=25)
        assert e.band == 3
        assert e.level == 25

    def test_dim_timeout_event(self):
        assert DimTimeoutEvent(step=TimeoutStep.TEN_MIN).step == TimeoutStep.TEN_MIN

    def test_home_screen_event(self):
        assert HomeScreenEvent(mode=HomeScreenMode.SIMPLE).mode == HomeScreenMode.SIMPLE

    def test_mic_led_event(self):
        assert MicLedEvent(level=6).level == 6

    def test_auto_off_event(self):
        assert AutoOffEvent(step=TimeoutStep.SIXTY_MIN).step == TimeoutStep.SIXTY_MIN


# ── All event dataclasses are regular (mutable) dataclasses ───────────────────


_ALL_EVENT_CLASSES = [
    VolumeEvent, BatteryEvent, ConnectivityEvent, AncModeEvent, MicMuteEvent,
    ChatMixEvent, GainEvent, MicVolumeEvent, SidetoneEvent, OledBrightnessEvent,
    TransparencyEvent, WirelessModeEvent, BtDefaultEvent, BtAutoMuteEvent,
    AudioOutputEvent, StreamVolumesEvent, EqPresetEvent, EqBandEvent,
    DimTimeoutEvent, HomeScreenEvent, MicLedEvent, AutoOffEvent,
]


@pytest.mark.parametrize("cls", _ALL_EVENT_CLASSES, ids=lambda c: c.__name__)
def test_event_class_is_dataclass(cls):
    assert dataclasses.is_dataclass(cls)


# ── Enum completeness ─────────────────────────────────────────────────────────


class TestEnums:
    def test_anc_mode_values(self):
        assert AncMode.OFF == 0
        assert AncMode.TRANSPARENCY == 1
        assert AncMode.ANC == 2

    def test_gain_level_values(self):
        assert GainLevel.LOW == 0
        assert GainLevel.HIGH == 1

    def test_sidetone_level_values(self):
        assert SidetoneLevel.OFF == 0
        assert SidetoneLevel.LOW == 1
        assert SidetoneLevel.MEDIUM == 2
        assert SidetoneLevel.HIGH == 3

    def test_audio_output_values(self):
        assert AudioOutput.SPEAKERS == 1
        assert AudioOutput.STREAM == 2

    def test_wireless_mode_values(self):
        assert WirelessMode.PERFORMANCE == 0
        assert WirelessMode.EXTENDED_RANGE == 1

    def test_bt_auto_mute_values(self):
        assert BtAutoMute.OFF == 0
        assert BtAutoMute.DB_MINUS_12 == 1
        assert BtAutoMute.FULL == 2

    def test_timeout_step_values(self):
        assert TimeoutStep.OFF == 0
        assert TimeoutStep.ONE_MIN == 1
        assert TimeoutStep.FIVE_MIN == 2
        assert TimeoutStep.TEN_MIN == 3
        assert TimeoutStep.FIFTEEN_MIN == 4
        assert TimeoutStep.THIRTY_MIN == 5
        assert TimeoutStep.SIXTY_MIN == 6

    def test_home_screen_mode_values(self):
        assert HomeScreenMode.DETAILED == 0
        assert HomeScreenMode.SIMPLE == 1

    def test_connectivity_mode_values(self):
        assert ConnectivityMode.WIRELESS_ONLY == 0x01
        assert ConnectivityMode.BT_PAIRING == 0x02
        assert ConnectivityMode.WIRELESS_AND_BT == 0x04
