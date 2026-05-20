"""Tests for arctis_hid.devices.nova_pro.codec — all encode/decode functions."""
from __future__ import annotations

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
    WirelessMode,
)
from arctis_hid.devices.nova_pro import constants as C
from arctis_hid.devices.nova_pro.codec import (
    _B0ConnRaw,
    _B5EventRaw,
    _B5QueryRaw,
    _B7EventRaw,
    _derive_bt_status,
    _derive_wireless,
    decode_ascii_response,
    decode_b0_conn,
    decode_b5_query,
    decode_battery,
    decode_battery_packet,
    decode_display_packet,
    decode_event,
    decode_gain_event,
    decode_gain_query,
    decode_mic_eq_packet,
    decode_status_packet,
    decode_vol_limiter_packet,
    decode_volume,
    encode_gain,
    encode_volume,
)

from .conftest import make_20_packet, make_26_packet, make_80_packet, make_b0_packet, make_b5_packet, make_b7_packet


# ── Volume encoding ────────────────────────────────────────────────────────────


class TestEncodeVolume:
    def test_100_pct_maps_to_zero(self):
        assert encode_volume(100) == 0x00

    def test_0_pct_maps_to_0x38(self):
        assert encode_volume(0) == 0x38

    def test_50_pct_encodes_to_half(self):
        assert encode_volume(50) == 28

    def test_clamp_below_zero(self):
        assert encode_volume(-10) == 0x38   # treated as 0%

    def test_clamp_above_100(self):
        assert encode_volume(110) == 0x00   # treated as 100%

    @pytest.mark.parametrize("pct", [0, 25, 50, 75, 100])
    def test_roundtrip_identity(self, pct: float):
        assert abs(decode_volume(encode_volume(pct)) - pct) < 1.0


class TestDecodeVolume:
    def test_raw_0x38_is_0_pct(self):
        assert decode_volume(0x38) == pytest.approx(0.0)

    def test_raw_0_is_100_pct(self):
        assert decode_volume(0x00) == pytest.approx(100.0)

    def test_raw_28_is_approx_50_pct(self):
        result = decode_volume(28)
        assert abs(result - 50.0) < 1.0

    def test_clamp_raw_above_0x38(self):
        # raw=0x40 > 0x38 would produce a negative percent — must clamp to 0.0
        assert decode_volume(0x40) == pytest.approx(0.0)

    def test_clamp_raw_255(self):
        assert decode_volume(0xFF) == pytest.approx(0.0)


# ── Battery decoding ───────────────────────────────────────────────────────────


class TestDecodeBattery:
    def test_full_charge(self):
        assert decode_battery(8) == pytest.approx(100.0)

    def test_empty(self):
        assert decode_battery(0) == pytest.approx(0.0)

    def test_mid_charge(self):
        assert decode_battery(4) == pytest.approx(50.0)

    def test_clamp_raw_9(self):
        # raw=9 would compute 112.5% without clamp
        assert decode_battery(9) == pytest.approx(100.0)

    def test_clamp_raw_255(self):
        assert decode_battery(255) == pytest.approx(100.0)


# ── Gain encoding/decoding ─────────────────────────────────────────────────────


class TestEncodeGain:
    def test_high_maps_to_0x02(self):
        assert encode_gain(GainLevel.HIGH) == 0x02

    def test_low_maps_to_0x01(self):
        assert encode_gain(GainLevel.LOW) == 0x01


class TestDecodeGainQuery:
    def test_raw_0x01_is_low(self):
        assert decode_gain_query(0x01) == GainLevel.LOW

    def test_raw_0x02_is_high(self):
        assert decode_gain_query(0x02) == GainLevel.HIGH

    def test_write_high_matches_query_encoding(self):
        # write and query both use 0x02 for HIGH — no asymmetry
        assert encode_gain(GainLevel.HIGH) == 0x02
        assert decode_gain_query(0x02) == GainLevel.HIGH


class TestDecodeGainEvent:
    def test_raw_0x01_is_low(self):
        assert decode_gain_event(0x01) == GainLevel.LOW

    def test_raw_0x02_is_high(self):
        assert decode_gain_event(0x02) == GainLevel.HIGH


# ── ASCII response decoding ────────────────────────────────────────────────────


class TestDecodeAsciiResponse:
    def _pad(self, body: list[int]) -> list[int]:
        """Build a full 64-byte packet with report-ID header."""
        return [0x06, 0x10] + body + [0] * (62 - len(body))

    def test_firmware_version(self):
        data = self._pad([0x35, 0x2E, 0x31, 0x00])  # "5.1\0"
        assert decode_ascii_response(data) == "5.1"

    def test_stops_at_null_terminator(self):
        data = self._pad([0x41, 0x00, 0x42, 0x43])  # "A\0BC"
        assert decode_ascii_response(data) == "A"

    def test_all_zeros_returns_empty_string(self):
        data = self._pad([])
        assert decode_ascii_response(data) == ""


# ── 0xB0 status packet decoding ────────────────────────────────────────────────


class TestDecodeStatusPacket:
    def test_headset_battery_full(self):
        pkt = make_b0_packet(hbat=8)
        result = decode_status_packet(pkt)
        assert result.headset_battery_pct == pytest.approx(100.0)

    def test_dock_battery_half(self):
        pkt = make_b0_packet(dbat=4)
        result = decode_status_packet(pkt)
        assert result.dock_battery_pct == pytest.approx(50.0)

    def test_mic_muted_true(self):
        pkt = make_b0_packet(mute=0x01)
        result = decode_status_packet(pkt)
        assert result.mic_muted is True

    def test_mic_muted_false(self):
        pkt = make_b0_packet(mute=0x00)
        result = decode_status_packet(pkt)
        assert result.mic_muted is False

    def test_anc_mode_off(self):
        pkt = make_b0_packet(anc=0x00)
        assert decode_status_packet(pkt).anc_mode == AncMode.OFF

    def test_anc_mode_transparency(self):
        pkt = make_b0_packet(anc=0x01)
        assert decode_status_packet(pkt).anc_mode == AncMode.TRANSPARENCY

    def test_anc_mode_anc(self):
        pkt = make_b0_packet(anc=0x02)
        assert decode_status_packet(pkt).anc_mode == AncMode.ANC

    def test_mic_led_brightness(self):
        pkt = make_b0_packet(mic_led=7)
        assert decode_status_packet(pkt).mic_led_brightness == 7

    def test_wireless_mode_performance(self):
        pkt = make_b0_packet(mode2g=0x00)
        assert decode_status_packet(pkt).wireless_mode == WirelessMode.PERFORMANCE

    def test_wireless_mode_extended_range(self):
        pkt = make_b0_packet(mode2g=0x01)
        assert decode_status_packet(pkt).wireless_mode == WirelessMode.EXTENDED_RANGE

    def test_bt_default_off(self):
        pkt = make_b0_packet(bt_default=0x00)
        assert decode_status_packet(pkt).bt_default is False

    def test_bt_default_on(self):
        pkt = make_b0_packet(bt_default=0x01)
        assert decode_status_packet(pkt).bt_default is True

    def test_bt_auto_mute_off(self):
        pkt = make_b0_packet(bt_automute=0x00)
        assert decode_status_packet(pkt).bt_auto_mute == BtAutoMute.OFF

    def test_bt_auto_mute_minus_12_db(self):
        pkt = make_b0_packet(bt_automute=0x01)
        assert decode_status_packet(pkt).bt_auto_mute == BtAutoMute.DB_MINUS_12

    def test_bt_auto_mute_full(self):
        pkt = make_b0_packet(bt_automute=0x02)
        assert decode_status_packet(pkt).bt_auto_mute == BtAutoMute.FULL

    def test_auto_off_timeout_off(self):
        pkt = make_b0_packet(auto_off=0x00)
        assert decode_status_packet(pkt).auto_off_timeout == TimeoutStep.OFF

    def test_auto_off_timeout_sixty_min(self):
        pkt = make_b0_packet(auto_off=0x06)
        assert decode_status_packet(pkt).auto_off_timeout == TimeoutStep.SIXTY_MIN

    def test_auto_off_timeout_all_steps(self):
        expected = [
            TimeoutStep.OFF, TimeoutStep.ONE_MIN, TimeoutStep.FIVE_MIN,
            TimeoutStep.TEN_MIN, TimeoutStep.FIFTEEN_MIN,
            TimeoutStep.THIRTY_MIN, TimeoutStep.SIXTY_MIN,
        ]
        for raw, step in enumerate(expected):
            pkt = make_b0_packet(auto_off=raw)
            assert decode_status_packet(pkt).auto_off_timeout == step

    def test_transparency_level_passthrough(self):
        for level in (1, 5, 10):
            pkt = make_b0_packet(transp=level)
            assert decode_status_packet(pkt).transparency_level == level

    def test_headset_power_on(self):
        assert decode_status_packet(make_b0_packet(powered=0x08)).headset_power is True

    def test_headset_power_off(self):
        assert decode_status_packet(make_b0_packet(powered=0x01)).headset_power is False

    def test_wireless_active(self):
        assert decode_status_packet(make_b0_packet(wireless_link=0x08)).wireless is True

    def test_wireless_searching(self):
        assert decode_status_packet(make_b0_packet(wireless_link=0x04)).wireless is False

    def test_wireless_fallback_via_mode(self):
        # wireless_raw=0x00 → fall back to mode_raw=0x01 (WIRELESS_ONLY) → True
        pkt = make_b0_packet(wireless_link=0x00, conn=0x01)
        assert decode_status_packet(pkt).wireless is True

    def test_bt_off_in_status(self):
        pkt = make_b0_packet(conn=0x01, bt=0x00)
        assert decode_status_packet(pkt).bt == BtStatus.OFF

    def test_bt_on_in_status(self):
        pkt = make_b0_packet(conn=0x04, bt=0x01)
        assert decode_status_packet(pkt).bt == BtStatus.ON

    def test_bt_pairing_in_status(self):
        pkt = make_b0_packet(conn=0x02, bt=0x00)
        assert decode_status_packet(pkt).bt == BtStatus.PAIRING

    def test_bt_not_connected_in_status(self):
        # bt_connected not available in 0xB0 — CONNECTED never appears in StatusData.bt
        pkt = make_b0_packet(conn=0x04, bt=0x01)
        assert decode_status_packet(pkt).bt != BtStatus.CONNECTED


# ── 0xB0 connectivity extraction ──────────────────────────────────────────────


class TestDecodeB0Conn:
    def test_mode_raw_wireless_only(self):
        pkt = make_b0_packet(conn=0x01)
        assert decode_b0_conn(pkt).mode_raw == 0x01

    def test_mode_raw_bt_pairing(self):
        pkt = make_b0_packet(conn=0x02)
        assert decode_b0_conn(pkt).mode_raw == 0x02

    def test_mode_raw_wireless_and_bt(self):
        pkt = make_b0_packet(conn=0x04)
        assert decode_b0_conn(pkt).mode_raw == 0x04

    def test_bt_active_true(self):
        pkt = make_b0_packet(bt=0x01)
        assert decode_b0_conn(pkt).bt_active is True

    def test_bt_active_false(self):
        pkt = make_b0_packet(bt=0x00)
        assert decode_b0_conn(pkt).bt_active is False

    def test_wireless_raw_active(self):
        pkt = make_b0_packet(wireless_link=0x08)
        assert decode_b0_conn(pkt).wireless_raw == 0x08

    def test_wireless_raw_searching(self):
        pkt = make_b0_packet(wireless_link=0x04)
        assert decode_b0_conn(pkt).wireless_raw == 0x04

    def test_wireless_raw_absent(self):
        pkt = make_b0_packet(wireless_link=0x02)
        assert decode_b0_conn(pkt).wireless_raw == 0x02

    def test_headset_power_on(self):
        pkt = make_b0_packet(powered=0x08)
        assert decode_b0_conn(pkt).headset_power is True

    def test_headset_power_off(self):
        pkt = make_b0_packet(powered=0x01)
        assert decode_b0_conn(pkt).headset_power is False

    def test_returns_b0connraw(self):
        pkt = make_b0_packet()
        assert isinstance(decode_b0_conn(pkt), _B0ConnRaw)


# ── 0xB5 connectivity query extraction ────────────────────────────────────────


class TestDecodeB5Query:
    def test_mode_raw_wireless_only(self):
        pkt = make_b5_packet(conn=0x01, bt_connected=0x02)
        assert decode_b5_query(pkt).mode_raw == 0x01

    def test_mode_raw_bt_pairing(self):
        pkt = make_b5_packet(conn=0x02, bt_connected=0x02)
        assert decode_b5_query(pkt).mode_raw == 0x02

    def test_mode_raw_wireless_and_bt(self):
        pkt = make_b5_packet(conn=0x04, bt_connected=0x01)
        assert decode_b5_query(pkt).mode_raw == 0x04

    def test_bt_connected_true(self):
        pkt = make_b5_packet(bt_connected=0x01)
        assert decode_b5_query(pkt).bt_connected is True

    def test_bt_connected_false(self):
        pkt = make_b5_packet(bt_connected=0x02)
        assert decode_b5_query(pkt).bt_connected is False

    def test_returns_b5queryraw(self):
        pkt = make_b5_packet()
        assert isinstance(decode_b5_query(pkt), _B5QueryRaw)


# ── 0x26 volume limiter packet decoding ───────────────────────────────────


class TestDecodeVolLimiterPacket:
    def test_limiter_on(self):
        pkt = make_26_packet(limiter=0x01)
        assert decode_vol_limiter_packet(pkt).limiter_on is True

    def test_limiter_off(self):
        pkt = make_26_packet(limiter=0x02)
        assert decode_vol_limiter_packet(pkt).limiter_on is False


# ── 0xB7 battery query packet decoding ────────────────────────────────────


class TestDecodeBatteryPacket:
    def test_headset_battery_full(self):
        pkt = make_b7_packet(hbat=8)
        assert decode_battery_packet(pkt).headset_pct == pytest.approx(100.0)

    def test_headset_battery_half(self):
        pkt = make_b7_packet(hbat=4)
        assert decode_battery_packet(pkt).headset_pct == pytest.approx(50.0)

    def test_dock_battery_full(self):
        pkt = make_b7_packet(dbat=8)
        assert decode_battery_packet(pkt).dock_pct == pytest.approx(100.0)

    def test_dock_battery_half(self):
        pkt = make_b7_packet(dbat=4)
        assert decode_battery_packet(pkt).dock_pct == pytest.approx(50.0)

    def test_both_batteries(self):
        pkt = make_b7_packet(hbat=8, dbat=2)
        result = decode_battery_packet(pkt)
        assert result.headset_pct == pytest.approx(100.0)
        assert result.dock_pct == pytest.approx(25.0)

    def test_headset_powered_true(self):
        assert decode_battery_packet(make_b7_packet(powered=0x08)).headset_powered is True

    def test_headset_powered_false(self):
        assert decode_battery_packet(make_b7_packet(powered=0x01)).headset_powered is False


# ── 0x80 display settings packet decoding ─────────────────────────────────────


class TestDecodeDisplayPacket:
    def test_dim_timeout_off(self):
        pkt = make_80_packet(dim_timeout=0)
        assert decode_display_packet(pkt).dim_timeout == TimeoutStep.OFF

    def test_dim_timeout_all_steps(self):
        expected = [
            TimeoutStep.OFF, TimeoutStep.ONE_MIN, TimeoutStep.FIVE_MIN,
            TimeoutStep.TEN_MIN, TimeoutStep.FIFTEEN_MIN,
            TimeoutStep.THIRTY_MIN, TimeoutStep.SIXTY_MIN,
        ]
        for raw, step in enumerate(expected):
            pkt = make_80_packet(dim_timeout=raw)
            assert decode_display_packet(pkt).dim_timeout == step

    def test_oled_brightness_passthrough(self):
        for level in (1, 5, 10):
            pkt = make_80_packet(oled_bright=level)
            assert decode_display_packet(pkt).oled_brightness == level

    def test_home_screen_detailed(self):
        pkt = make_80_packet(home_screen=0)
        assert decode_display_packet(pkt).home_screen_mode == HomeScreenMode.DETAILED

    def test_home_screen_simple(self):
        pkt = make_80_packet(home_screen=1)
        assert decode_display_packet(pkt).home_screen_mode == HomeScreenMode.SIMPLE

    def test_sonar_running_true(self):
        pkt = make_80_packet(sonar=0x01)
        assert decode_display_packet(pkt).sonar_running is True

    def test_sonar_running_false(self):
        pkt = make_80_packet(sonar=0x00)
        assert decode_display_packet(pkt).sonar_running is False


# ── BtStatus derivation ────────────────────────────────────────────────────────


class TestDeriveBtStatus:
    def test_bt_connected_wins(self):
        # bt_connected=True always → CONNECTED regardless of mode/bt_active
        assert _derive_bt_status(0x01, False, True) == BtStatus.CONNECTED
        assert _derive_bt_status(0x04, True,  True) == BtStatus.CONNECTED

    def test_pairing_mode(self):
        assert _derive_bt_status(0x02, False, False) == BtStatus.PAIRING

    def test_bt_on_via_mode_0x04(self):
        assert _derive_bt_status(0x04, False, False) == BtStatus.ON

    def test_bt_on_via_bt_active(self):
        # mode=WIRELESS_ONLY (0x01) but bt_active=True → ON
        assert _derive_bt_status(0x01, True, False) == BtStatus.ON

    def test_bt_off(self):
        assert _derive_bt_status(0x01, False, False) == BtStatus.OFF

    def test_pairing_takes_priority_over_bt_active(self):
        # mode=BT_PAIRING with bt_active=True → still PAIRING (not ON)
        assert _derive_bt_status(0x02, True, False) == BtStatus.PAIRING


# ── 0xB5 event decoding ────────────────────────────────────────────────────────


def _make_b5_event(*payload: int) -> list[int]:
    pkt = [0] * 64
    pkt[0] = 0x07
    pkt[1] = 0xB5
    for i, v in enumerate(payload):
        pkt[2 + i] = v
    return pkt


class TestDecodeB5Event:
    def test_returns_b5_event_raw(self):
        pkt = _make_b5_event(0x01, 0x00, 0x08)
        assert isinstance(decode_event(pkt), _B5EventRaw)

    def test_mode_raw_passthrough(self):
        pkt = _make_b5_event(0x04, 0x01, 0x08)
        evt = decode_event(pkt)
        assert evt.mode_raw == 0x04

    def test_bt_connected_true(self):
        pkt = _make_b5_event(0x04, 0x01, 0x08)
        assert decode_event(pkt).bt_connected is True

    def test_bt_connected_false(self):
        pkt = _make_b5_event(0x01, 0x02, 0x08)
        assert decode_event(pkt).bt_connected is False

    def test_wireless_raw_active(self):
        pkt = _make_b5_event(0x01, 0x00, 0x08)
        assert decode_event(pkt).wireless_raw == 0x08

    def test_wireless_raw_searching(self):
        pkt = _make_b5_event(0x01, 0x00, 0x04)
        assert decode_event(pkt).wireless_raw == 0x04

    def test_wireless_raw_zero_preserved(self):
        # 0x00 means "ignore" — the raw value is still passed through unchanged
        pkt = _make_b5_event(0x04, 0x01, 0x00)
        assert decode_event(pkt).wireless_raw == 0x00


# ── 0xB7 event decoding ────────────────────────────────────────────────────────


def _make_b7_event(hbat: int = 8, dbat: int = 8, powered: int = 0x08) -> list[int]:
    pkt = [0] * 64
    pkt[0] = 0x07
    pkt[1] = 0xB7
    pkt[2] = hbat
    pkt[3] = dbat
    pkt[4] = powered
    return pkt


class TestDecodeB7Event:
    def test_returns_b7_event_raw(self):
        pkt = _make_b7_event()
        assert isinstance(decode_event(pkt), _B7EventRaw)

    def test_headset_pct_full(self):
        pkt = _make_b7_event(hbat=8)
        assert decode_event(pkt).headset_pct == pytest.approx(100.0)

    def test_headset_pct_half(self):
        pkt = _make_b7_event(hbat=4)
        assert decode_event(pkt).headset_pct == pytest.approx(50.0)

    def test_dock_pct_full(self):
        pkt = _make_b7_event(dbat=8)
        assert decode_event(pkt).dock_pct == pytest.approx(100.0)

    def test_headset_power_on(self):
        pkt = _make_b7_event(powered=0x08)
        assert decode_event(pkt).headset_power is True

    def test_headset_power_off(self):
        pkt = _make_b7_event(powered=0x01)
        assert decode_event(pkt).headset_power is False


# ── 0x20 mic/EQ packet decoding ────────────────────────────────────────────────


class TestDecodeMicEqPacket:
    def test_volume_0_pct(self):
        pkt = make_20_packet(vol=0x38)
        assert decode_mic_eq_packet(pkt).volume_pct == pytest.approx(0.0)

    def test_volume_100_pct(self):
        pkt = make_20_packet(vol=0x00)
        assert decode_mic_eq_packet(pkt).volume_pct == pytest.approx(100.0)

    def test_gain_low(self):
        pkt = make_20_packet(gain=0x01)
        assert decode_mic_eq_packet(pkt).gain == GainLevel.LOW

    def test_gain_high(self):
        pkt = make_20_packet(gain=0x02)
        assert decode_mic_eq_packet(pkt).gain == GainLevel.HIGH

    def test_eq_preset_index_passthrough(self):
        pkt = make_20_packet(eq_preset=0x04)
        assert decode_mic_eq_packet(pkt).eq_preset_index == 0x04

    def test_eq_bands_length_and_values(self):
        bands = list(range(10, 20))
        pkt = make_20_packet(eq_bands=bands)
        result = decode_mic_eq_packet(pkt)
        assert len(result.eq_bands) == 10
        assert result.eq_bands == bands

    def test_mic_volume_passthrough(self):
        pkt = make_20_packet(mic_vol=7)
        assert decode_mic_eq_packet(pkt).mic_volume == 7

    def test_sidetone_medium(self):
        pkt = make_20_packet(sidetone=2)
        assert decode_mic_eq_packet(pkt).sidetone == SidetoneLevel.MEDIUM

    def test_audio_output_stream(self):
        pkt = make_20_packet(audio=0x02)
        assert decode_mic_eq_packet(pkt).audio_output == AudioOutput.STREAM

    def test_chatmix_game_and_chat(self):
        pkt = make_20_packet(game=70, chat=30)
        result = decode_mic_eq_packet(pkt)
        assert result.chatmix_game == 70
        assert result.chatmix_chat == 30

    def test_stream_volumes(self):
        pkt = make_20_packet(smain=80, saux=60, smic=40)
        result = decode_mic_eq_packet(pkt)
        assert result.stream_main_vol == 80
        assert result.stream_aux_vol == 60
        assert result.stream_mic_vol == 40
