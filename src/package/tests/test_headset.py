"""Tests for ArctisNovaProWireless set_*/get_* — verifies correct bytes over transport."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, call, patch

import pytest

from arctis_hid.core.types import (
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
from arctis_hid.exceptions import DeviceIOError
from arctis_hid.devices.nova_pro import constants as C
from arctis_hid.devices.nova_pro.models import (
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

from .conftest import make_20_packet, make_26_packet, make_80_packet, make_b0_packet, make_b5_packet, make_b7_packet


# ── Query methods ──────────────────────────────────────────────────────────────


class TestGetStatus:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b0_packet()
        mock_headset.get_status()
        mock_transport.query.assert_called_once_with(C.CMD_STATUS)

    def test_returns_status_data(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b0_packet(hbat=8, dbat=4, mute=0x01)
        result = mock_headset.get_status()
        assert isinstance(result, StatusData)
        assert result.headset_battery_pct == pytest.approx(100.0)
        assert result.dock_battery_pct == pytest.approx(50.0)
        assert result.mic_muted is True

    def test_updates_connectivity_state(self, mock_headset, mock_transport):
        # get_status() must update the internal connectivity state
        mock_transport.query.return_value = make_b0_packet(
            conn=0x04, bt=0x01, wireless_link=0x08, powered=0x08
        )
        mock_headset.get_status()
        conn = mock_headset.connectivity
        assert conn.wireless is True
        assert conn.headset_power is True
        assert conn.bt in (BtStatus.ON, BtStatus.CONNECTED)  # bt_connected unknown at this point


class TestGetMicEq:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_20_packet()
        mock_headset.get_mic_eq()
        mock_transport.query.assert_called_once_with(C.CMD_MIC_EQ)

    def test_returns_mic_eq_data(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_20_packet(vol=0x00, gain=0x02)
        result = mock_headset.get_mic_eq()
        assert isinstance(result, MicEqData)
        assert result.volume_pct == pytest.approx(100.0)
        assert result.gain == GainLevel.HIGH


class TestGetFirmwareVersion:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        packet = [0x06, 0x10, 0x35, 0x2E, 0x31, 0x00] + [0] * 58
        mock_transport.query.return_value = packet
        mock_headset.get_firmware_version()
        mock_transport.query.assert_called_once_with(C.CMD_FIRMWARE)

    def test_returns_ascii_string(self, mock_headset, mock_transport):
        packet = [0x06, 0x10, 0x35, 0x2E, 0x31, 0x00] + [0] * 58
        mock_transport.query.return_value = packet
        assert mock_headset.get_firmware_version() == "5.1"


class TestGetSerialNumber:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        packet = [0x06, 0x12, 0x41, 0x42, 0x43, 0x00] + [0] * 58
        mock_transport.query.return_value = packet
        mock_headset.get_serial_number()
        mock_transport.query.assert_called_once_with(C.CMD_SERIAL)

    def test_returns_ascii_string(self, mock_headset, mock_transport):
        packet = [0x06, 0x12, 0x41, 0x42, 0x43, 0x00] + [0] * 58
        mock_transport.query.return_value = packet
        assert mock_headset.get_serial_number() == "ABC"


class TestGetConnectivity:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet()
        mock_headset.get_connectivity()
        mock_transport.query.assert_called_once_with(C.CMD_CONNECTIVITY)

    def test_returns_connectivity_status(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet(conn=0x04, bt_connected=0x01)
        result = mock_headset.get_connectivity()
        assert isinstance(result, ConnectivityStatus)

    def test_bt_connected(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet(conn=0x04, bt_connected=0x01)
        result = mock_headset.get_connectivity()
        assert result.bt == BtStatus.CONNECTED

    def test_bt_on(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet(conn=0x04, bt_connected=0x02)
        result = mock_headset.get_connectivity()
        assert result.bt == BtStatus.ON

    def test_bt_pairing(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet(conn=0x02, bt_connected=0x02)
        result = mock_headset.get_connectivity()
        assert result.bt == BtStatus.PAIRING

    def test_bt_off(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet(conn=0x01, bt_connected=0x02)
        result = mock_headset.get_connectivity()
        assert result.bt == BtStatus.OFF

    def test_usb_is_true(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b5_packet()
        result = mock_headset.get_connectivity()
        assert result.usb is True


class TestGetDisplay:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_80_packet()
        mock_headset.get_display()
        mock_transport.query.assert_called_once_with(C.CMD_DISPLAY)

    def test_returns_display_data(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_80_packet(
            dim_timeout=3, oled_bright=7, home_screen=1, sonar=0x01
        )
        result = mock_headset.get_display()
        assert isinstance(result, DisplayData)
        assert result.dim_timeout == TimeoutStep.TEN_MIN
        assert result.oled_brightness == 7
        assert result.home_screen_mode == HomeScreenMode.SIMPLE
        assert result.sonar_running is True


class TestGetVolumeLimiter:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_26_packet()
        mock_headset.get_volume_limiter()
        mock_transport.query.assert_called_once_with(C.CMD_VOL_LIMITER)

    def test_limiter_on(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_26_packet(limiter=0x01)
        result = mock_headset.get_volume_limiter()
        assert isinstance(result, VolumeLimiterData)
        assert result.limiter_on is True

    def test_limiter_off(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_26_packet(limiter=0x02)
        result = mock_headset.get_volume_limiter()
        assert result.limiter_on is False


class TestGetBattery:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet()
        mock_headset.get_battery()
        mock_transport.query.assert_called_once_with(C.CMD_BATTERY)

    def test_returns_battery_data(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(hbat=8, dbat=4)
        result = mock_headset.get_battery()
        assert isinstance(result, BatteryData)
        assert result.headset_pct == pytest.approx(100.0)
        assert result.dock_pct == pytest.approx(50.0)

    def test_both_empty(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(hbat=0, dbat=0)
        result = mock_headset.get_battery()
        assert result.headset_pct == pytest.approx(0.0)
        assert result.dock_pct == pytest.approx(0.0)

    def test_headset_powered_true(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(powered=0x08)
        assert mock_headset.get_battery().headset_powered is True

    def test_headset_powered_false(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(powered=0x01)
        assert mock_headset.get_battery().headset_powered is False

    def test_updates_headset_power(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(powered=0x08)
        mock_headset.get_battery()
        assert mock_headset.connectivity.headset_power is True

    def test_headset_power_off(self, mock_headset, mock_transport):
        mock_transport.query.return_value = make_b7_packet(powered=0x01)
        mock_headset.get_battery()
        assert mock_headset.connectivity.headset_power is False


# ── Connectivity state management ─────────────────────────────────────────────


def _make_b5_event(mode: int = 0x01, bt_connected: int = 0x02, wireless: int = 0x08) -> list[int]:
    pkt = [0] * 64
    pkt[0] = 0x07
    pkt[1] = 0xB5
    pkt[2] = mode
    pkt[3] = bt_connected
    pkt[4] = wireless
    return pkt


def _make_b7_event(hbat: int = 8, dbat: int = 8, powered: int = 0x08) -> list[int]:
    pkt = [0] * 64
    pkt[0] = 0x07
    pkt[1] = 0xB7
    pkt[2] = hbat
    pkt[3] = dbat
    pkt[4] = powered
    return pkt


class TestConnectivityStateManagement:
    def test_initial_usb_is_true(self, mock_headset, mock_transport):
        assert mock_headset.connectivity.usb is True

    def test_b5_event_emits_connectivity_event(self, mock_headset, mock_transport):
        received = []
        mock_headset.on("ConnectivityEvent", received.append)
        mock_headset._process_packet("evt", _make_b5_event(0x04, 0x01, 0x08))
        assert len(received) == 1
        assert isinstance(received[0], ConnectivityEvent)
        assert isinstance(received[0].connectivity, ConnectivityStatus)

    def test_b5_event_bt_connected(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b5_event(mode=0x04, bt_connected=0x01, wireless=0x08))
        assert mock_headset.connectivity.bt == BtStatus.CONNECTED

    def test_b5_event_bt_on(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b5_event(mode=0x04, bt_connected=0x02, wireless=0x08))
        assert mock_headset.connectivity.bt == BtStatus.ON

    def test_b5_event_bt_pairing(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b5_event(mode=0x02, bt_connected=0x02, wireless=0x04))
        assert mock_headset.connectivity.bt == BtStatus.PAIRING

    def test_b5_event_wireless_true(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b5_event(wireless=0x08))
        assert mock_headset.connectivity.wireless is True

    def test_b5_event_wireless_false_searching(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b5_event(wireless=0x04))
        assert mock_headset.connectivity.wireless is False

    def test_b5_event_wireless_zero_ignored(self, mock_headset, mock_transport):
        # Set a known wireless state first
        mock_headset._cs_wireless_raw = 0x08
        # Then fire event with 0x00 — should NOT overwrite
        mock_headset._process_packet("evt", _make_b5_event(wireless=0x00))
        assert mock_headset.connectivity.wireless is True  # preserved

    # ── wireless fallback via mode_raw when wireless_raw == 0x00 ──────────────

    def test_wireless_fallback_mode_wireless_only(self, mock_headset, mock_transport):
        mock_headset._cs_wireless_raw = 0x00
        mock_headset._cs_mode_raw = 0x01  # WIRELESS_ONLY
        assert mock_headset.connectivity.wireless is True

    def test_wireless_fallback_mode_wireless_and_bt(self, mock_headset, mock_transport):
        mock_headset._cs_wireless_raw = 0x00
        mock_headset._cs_mode_raw = 0x04  # WIRELESS_AND_BT
        assert mock_headset.connectivity.wireless is True

    def test_wireless_fallback_mode_bt_pairing(self, mock_headset, mock_transport):
        mock_headset._cs_wireless_raw = 0x00
        mock_headset._cs_mode_raw = 0x02  # BT_PAIRING — wireless not active
        assert mock_headset.connectivity.wireless is False

    def test_wireless_raw_0x08_takes_precedence_over_mode(self, mock_headset, mock_transport):
        # Even in BT_PAIRING mode, if wireless_raw says active, it wins
        mock_headset._cs_wireless_raw = 0x08
        mock_headset._cs_mode_raw = 0x02
        assert mock_headset.connectivity.wireless is True

    def test_wireless_raw_0x04_takes_precedence_over_mode(self, mock_headset, mock_transport):
        # Even in WIRELESS_ONLY mode, if wireless_raw says searching, it wins
        mock_headset._cs_wireless_raw = 0x04
        mock_headset._cs_mode_raw = 0x01
        assert mock_headset.connectivity.wireless is False

    def test_b7_event_emits_battery_and_connectivity_events(self, mock_headset, mock_transport):
        battery_events = []
        conn_events = []
        mock_headset.on("BatteryEvent", battery_events.append)
        mock_headset.on("ConnectivityEvent", conn_events.append)
        mock_headset._process_packet("evt", _make_b7_event(hbat=8, dbat=4, powered=0x08))
        assert len(battery_events) == 1
        assert len(conn_events) == 1
        assert battery_events[0].headset_pct == pytest.approx(100.0)

    def test_b7_event_updates_headset_power(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b7_event(powered=0x08))
        assert mock_headset.connectivity.headset_power is True

    def test_b7_event_headset_power_off(self, mock_headset, mock_transport):
        mock_headset._process_packet("evt", _make_b7_event(powered=0x01))
        assert mock_headset.connectivity.headset_power is False

    def test_b7_event_no_headset_powered_field_in_battery_event(self, mock_headset, mock_transport):
        received = []
        mock_headset.on("BatteryEvent", received.append)
        mock_headset._process_packet("evt", _make_b7_event())
        assert not hasattr(received[0], "headset_powered")

    def test_usb_disconnects_sets_false(self, mock_headset, mock_transport):
        mock_transport.poll.side_effect = DeviceIOError("read error")
        stop = threading.Event()
        mock_headset._stop_event = stop
        with patch.object(mock_headset, "_reconnect_until_found", return_value=False):
            mock_headset._poll_loop(stop)
        assert mock_headset._cs_usb is False

    def test_usb_reconnects_sets_true(self, mock_headset, mock_transport):
        stop = threading.Event()
        poll_calls = 0

        def poll_side_effect(*args, **kwargs):
            nonlocal poll_calls
            poll_calls += 1
            if poll_calls == 1:
                raise DeviceIOError("disconnected")
            stop.set()
            return []

        mock_transport.poll.side_effect = poll_side_effect
        mock_headset._stop_event = stop

        with patch.object(mock_headset, "_reconnect_until_found", return_value=True):
            mock_headset._poll_loop(stop)

        assert mock_headset._cs_usb is True


# ── Write methods — correct command byte + payload + save ─────────────────────


class TestSetVolume:
    def test_100_pct(self, mock_headset, mock_transport):
        mock_headset.set_volume(100)
        mock_transport.write.assert_any_call(C.CMD_VOL, [0x00])

    def test_0_pct(self, mock_headset, mock_transport):
        mock_headset.set_volume(0)
        mock_transport.write.assert_any_call(C.CMD_VOL, [0x38])

    def test_50_pct(self, mock_headset, mock_transport):
        mock_headset.set_volume(50)
        mock_transport.write.assert_any_call(C.CMD_VOL, [28])

    def test_save_called_after_write(self, mock_headset, mock_transport):
        mock_headset.set_volume(75)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetMicVolume:
    def test_correct_command_and_payload(self, mock_headset, mock_transport):
        mock_headset.set_mic_volume(5)
        mock_transport.write.assert_any_call(C.CMD_MIC_VOL, [5])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_mic_volume(3)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetSidetone:
    def test_high(self, mock_headset, mock_transport):
        mock_headset.set_sidetone(SidetoneLevel.HIGH)
        mock_transport.write.assert_any_call(C.CMD_SIDETONE, [3])

    def test_off(self, mock_headset, mock_transport):
        mock_headset.set_sidetone(SidetoneLevel.OFF)
        mock_transport.write.assert_any_call(C.CMD_SIDETONE, [0])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_sidetone(SidetoneLevel.LOW)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetAncMode:
    def test_anc(self, mock_headset, mock_transport):
        mock_headset.set_anc_mode(AncMode.ANC)
        mock_transport.write.assert_any_call(C.CMD_ANC, [2])

    def test_off(self, mock_headset, mock_transport):
        mock_headset.set_anc_mode(AncMode.OFF)
        mock_transport.write.assert_any_call(C.CMD_ANC, [0])

    def test_transparency(self, mock_headset, mock_transport):
        mock_headset.set_anc_mode(AncMode.TRANSPARENCY)
        mock_transport.write.assert_any_call(C.CMD_ANC, [1])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_anc_mode(AncMode.OFF)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetTransparencyLevel:
    def test_correct_command(self, mock_headset, mock_transport):
        mock_headset.set_transparency_level(7)
        mock_transport.write.assert_any_call(C.CMD_TRANSP_LEVEL, [7])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_transparency_level(5)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetOledBrightness:
    def test_correct_command(self, mock_headset, mock_transport):
        mock_headset.set_oled_brightness(5)
        mock_transport.write.assert_any_call(C.CMD_OLED_BRIGHT, [5])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_oled_brightness(3)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetGain:
    def test_high_encodes_to_0x02(self, mock_headset, mock_transport):
        mock_headset.set_gain(GainLevel.HIGH)
        mock_transport.write.assert_any_call(C.CMD_GAIN, [0x02])

    def test_low_encodes_to_0x01(self, mock_headset, mock_transport):
        mock_headset.set_gain(GainLevel.LOW)
        mock_transport.write.assert_any_call(C.CMD_GAIN, [0x01])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_gain(GainLevel.HIGH)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetMicLedBrightness:
    def test_correct_command(self, mock_headset, mock_transport):
        mock_headset.set_mic_led_brightness(8)
        mock_transport.write.assert_any_call(C.CMD_MIC_LED, [8])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_mic_led_brightness(5)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetChatmixEnabled:
    def test_enable(self, mock_headset, mock_transport):
        mock_headset.set_chatmix_enabled(True)
        mock_transport.write.assert_any_call(C.CMD_CHATMIX_EN, [0x01])

    def test_disable(self, mock_headset, mock_transport):
        mock_headset.set_chatmix_enabled(False)
        mock_transport.write.assert_any_call(C.CMD_CHATMIX_EN, [0x00])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_chatmix_enabled(True)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetWirelessMode:
    def test_extended_range(self, mock_headset, mock_transport):
        mock_headset.set_wireless_mode(WirelessMode.EXTENDED_RANGE)
        mock_transport.write.assert_any_call(C.CMD_WIRELESS, [1])

    def test_performance(self, mock_headset, mock_transport):
        mock_headset.set_wireless_mode(WirelessMode.PERFORMANCE)
        mock_transport.write.assert_any_call(C.CMD_WIRELESS, [0])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_wireless_mode(WirelessMode.PERFORMANCE)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetUsbInput:
    def test_input_1(self, mock_headset, mock_transport):
        mock_headset.set_usb_input(UsbInput.INPUT_1)
        mock_transport.write.assert_any_call(C.CMD_USB_INPUT, [0])

    def test_input_2(self, mock_headset, mock_transport):
        mock_headset.set_usb_input(UsbInput.INPUT_2)
        mock_transport.write.assert_any_call(C.CMD_USB_INPUT, [1])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_usb_input(UsbInput.INPUT_1)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetBtDefault:
    def test_on(self, mock_headset, mock_transport):
        mock_headset.set_bt_default(True)
        mock_transport.write.assert_any_call(C.CMD_BT_DEFAULT, [0x01])

    def test_off(self, mock_headset, mock_transport):
        mock_headset.set_bt_default(False)
        mock_transport.write.assert_any_call(C.CMD_BT_DEFAULT, [0x00])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_bt_default(True)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetBtAutoMute:
    def test_db_minus_12(self, mock_headset, mock_transport):
        mock_headset.set_bt_auto_mute(BtAutoMute.DB_MINUS_12)
        mock_transport.write.assert_any_call(C.CMD_BT_AUTOMUTE, [1])

    def test_full(self, mock_headset, mock_transport):
        mock_headset.set_bt_auto_mute(BtAutoMute.FULL)
        mock_transport.write.assert_any_call(C.CMD_BT_AUTOMUTE, [2])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_bt_auto_mute(BtAutoMute.OFF)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetAudioOutput:
    def test_stream(self, mock_headset, mock_transport):
        mock_headset.set_audio_output(AudioOutput.STREAM)
        mock_transport.write.assert_any_call(C.CMD_AUDIO_OUT, [2])

    def test_speakers(self, mock_headset, mock_transport):
        mock_headset.set_audio_output(AudioOutput.SPEAKERS)
        mock_transport.write.assert_any_call(C.CMD_AUDIO_OUT, [1])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_audio_output(AudioOutput.SPEAKERS)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetStreamVolumes:
    def test_correct_payload(self, mock_headset, mock_transport):
        mock_headset.set_stream_volumes(80, 60, 40)
        mock_transport.write.assert_any_call(C.CMD_STREAM_VOLS, [80, 0x00, 60, 40])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_stream_volumes(100, 100, 100)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetEqPreset:
    def test_custom_preset(self, mock_headset, mock_transport):
        mock_headset.set_eq_preset(4)
        mock_transport.write.assert_any_call(C.CMD_EQ_PRESET, [4])

    def test_named_preset(self, mock_headset, mock_transport):
        mock_headset.set_eq_preset(0)
        mock_transport.write.assert_any_call(C.CMD_EQ_PRESET, [0])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_eq_preset(1)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetEqBands:
    def test_writes_preset_then_bands(self, mock_headset, mock_transport):
        bands = [20] * 10
        mock_headset.set_eq_bands(bands)
        calls = mock_transport.write.call_args_list
        cmd_bytes = [c[0][0] for c in calls]
        preset_idx = cmd_bytes.index(C.CMD_EQ_PRESET)
        bands_idx  = cmd_bytes.index(C.CMD_EQ_BANDS)
        assert preset_idx < bands_idx, "EQ preset must be set before EQ bands"

    def test_selects_custom_preset_0x04(self, mock_headset, mock_transport):
        mock_headset.set_eq_bands([20] * 10)
        mock_transport.write.assert_any_call(C.CMD_EQ_PRESET, [0x04])

    def test_sends_all_10_bands(self, mock_headset, mock_transport):
        bands = list(range(10, 20))
        mock_headset.set_eq_bands(bands)
        mock_transport.write.assert_any_call(C.CMD_EQ_BANDS, bands)

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_eq_bands([20] * 10)
        mock_transport.write.assert_called_with(C.CMD_SAVE)

    def test_raises_for_9_bands(self, mock_headset):
        with pytest.raises(ValueError):
            mock_headset.set_eq_bands([20] * 9)

    def test_raises_for_11_bands(self, mock_headset):
        with pytest.raises(ValueError):
            mock_headset.set_eq_bands([20] * 11)

    def test_raises_for_empty_bands(self, mock_headset):
        with pytest.raises(ValueError):
            mock_headset.set_eq_bands([])


class TestSetDimTimeout:
    def test_ten_min(self, mock_headset, mock_transport):
        mock_headset.set_dim_timeout(TimeoutStep.TEN_MIN)
        mock_transport.write.assert_any_call(C.CMD_DIM_TIMEOUT, [3])

    def test_off(self, mock_headset, mock_transport):
        mock_headset.set_dim_timeout(TimeoutStep.OFF)
        mock_transport.write.assert_any_call(C.CMD_DIM_TIMEOUT, [0])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_dim_timeout(TimeoutStep.OFF)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetHomeScreenMode:
    def test_simple(self, mock_headset, mock_transport):
        mock_headset.set_home_screen_mode(HomeScreenMode.SIMPLE)
        mock_transport.write.assert_any_call(C.CMD_HOME_SCREEN, [1])

    def test_detailed(self, mock_headset, mock_transport):
        mock_headset.set_home_screen_mode(HomeScreenMode.DETAILED)
        mock_transport.write.assert_any_call(C.CMD_HOME_SCREEN, [0])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_home_screen_mode(HomeScreenMode.DETAILED)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestSetAutoOffTimeout:
    def test_thirty_min(self, mock_headset, mock_transport):
        mock_headset.set_auto_off_timeout(TimeoutStep.THIRTY_MIN)
        mock_transport.write.assert_any_call(C.CMD_AUTO_OFF, [5])

    def test_sixty_min(self, mock_headset, mock_transport):
        mock_headset.set_auto_off_timeout(TimeoutStep.SIXTY_MIN)
        mock_transport.write.assert_any_call(C.CMD_AUTO_OFF, [6])

    def test_save_called(self, mock_headset, mock_transport):
        mock_headset.set_auto_off_timeout(TimeoutStep.OFF)
        mock_transport.write.assert_called_with(C.CMD_SAVE)


class TestFactoryReset:
    def test_sends_correct_opcode(self, mock_headset, mock_transport):
        mock_headset.factory_reset()
        mock_transport.write.assert_called_once_with(C.CMD_FACTORY_RESET)

    def test_no_save_sent(self, mock_headset, mock_transport):
        mock_headset.factory_reset()
        calls = mock_transport.write.call_args_list
        sent_cmds = [c[0][0] for c in calls]
        assert C.CMD_SAVE not in sent_cmds, "0x09 save must NOT be sent after factory reset"

    def test_exactly_one_write(self, mock_headset, mock_transport):
        mock_headset.factory_reset()
        assert mock_transport.write.call_count == 1


# ── Disconnect / reconnect behaviour ──────────────────────────────────────────


class TestPollLoopDisconnect:
    """Poll loop should emit DeviceDisconnectedEvent on OSError and stop cleanly."""

    def test_disconnect_event_emitted_on_io_error(self, mock_headset, mock_transport):
        received = []
        mock_headset.on("DeviceDisconnectedEvent", received.append)

        # poll raises immediately, then stop_event is set so reconnect loop exits
        mock_transport.poll.side_effect = DeviceIOError("read error")

        stop = threading.Event()
        mock_headset._stop_event = stop

        with patch.object(mock_headset, "_reconnect_until_found", return_value=False):
            mock_headset._poll_loop(stop)

        assert len(received) == 1
        assert isinstance(received[0], DeviceDisconnectedEvent)

    def test_poll_loop_exits_when_reconnect_returns_false(self, mock_headset, mock_transport):
        mock_transport.poll.side_effect = DeviceIOError("read error")
        stop = threading.Event()
        mock_headset._stop_event = stop

        with patch.object(mock_headset, "_reconnect_until_found", return_value=False):
            mock_headset._poll_loop(stop)  # must return, not hang


class TestReconnectUntilFound:
    """_reconnect_until_found retries until the device reappears or stop is set."""

    def test_returns_true_when_device_found(self, mock_headset, mock_transport):
        stop = threading.Event()
        with patch.object(mock_headset, "_find_device_paths", return_value=(b"/ctrl", b"/evt")):
            result = mock_headset._reconnect_until_found(stop)
        assert result is True

    def test_opens_transport_on_success(self, mock_headset, mock_transport):
        stop = threading.Event()
        with patch.object(mock_headset, "_find_device_paths", return_value=(b"/ctrl", b"/evt")):
            mock_headset._reconnect_until_found(stop)
        mock_transport.open.assert_called_once_with(b"/ctrl", b"/evt")

    def test_updates_stored_paths_on_success(self, mock_headset, mock_transport):
        stop = threading.Event()
        with patch.object(mock_headset, "_find_device_paths", return_value=(b"/new_ctrl", b"/new_evt")):
            mock_headset._reconnect_until_found(stop)
        assert mock_headset._ctrl_path == b"/new_ctrl"
        assert mock_headset._evt_path == b"/new_evt"

    def test_returns_false_when_stop_set_before_device_found(self, mock_headset, mock_transport):
        stop = threading.Event()
        stop.set()
        with patch.object(mock_headset, "_find_device_paths", side_effect=DeviceIOError("not found")):
            result = mock_headset._reconnect_until_found(stop)
        assert result is False

    def test_retries_after_find_failure(self, mock_headset, mock_transport):
        stop = threading.Event()
        call_count = 0

        def find_paths_side_effect():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise DeviceIOError("not found")
            stop.set()
            raise DeviceIOError("not found")

        with patch.object(mock_headset, "_find_device_paths", side_effect=find_paths_side_effect):
            result = mock_headset._reconnect_until_found(stop)

        assert call_count == 3
        assert result is False


class TestReconnectEventFlow:
    """Full disconnect→reconnect flow emits both events in order."""

    def test_reconnect_event_emitted_after_successful_reconnect(self, mock_headset, mock_transport):
        events = []
        mock_headset.on("DeviceDisconnectedEvent", events.append)
        mock_headset.on("DeviceReconnectedEvent", events.append)

        stop = threading.Event()
        poll_calls = 0

        def poll_side_effect(*args, **kwargs):
            nonlocal poll_calls
            poll_calls += 1
            if poll_calls == 1:
                raise DeviceIOError("disconnected")
            stop.set()
            return []

        mock_transport.poll.side_effect = poll_side_effect
        mock_headset._stop_event = stop

        with patch.object(mock_headset, "_reconnect_until_found", return_value=True):
            mock_headset._poll_loop(stop)

        assert len(events) == 2
        assert isinstance(events[0], DeviceDisconnectedEvent)
        assert isinstance(events[1], DeviceReconnectedEvent)
