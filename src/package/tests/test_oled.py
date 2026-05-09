"""Tests for OLED bitmap encoder (encode_frame) and ArctisNovaProOled draw_raw/clear/release."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from arctis_hid.devices.nova_pro import constants as C
from arctis_hid.devices.nova_pro.oled import BITMAP_SIZE, ArctisNovaProOled, encode_frame

try:
    from PIL import Image
    _PIL = True
except ImportError:
    _PIL = False

pytestmark = pytest.mark.skipif(not _PIL, reason="Pillow not installed (pip install 'arctis-hid[oled]')")


# ── Helpers ────────────────────────────────────────────────────────────────────


def white_image() -> "Image.Image":
    return Image.new("L", (C.OLED_WIDTH, C.OLED_HEIGHT), 255)


def black_image() -> "Image.Image":
    return Image.new("L", (C.OLED_WIDTH, C.OLED_HEIGHT), 0)


def single_pixel_image(px: int, py: int, brightness: int = 255) -> "Image.Image":
    img = black_image()
    img.putpixel((px, py), brightness)
    return img


def make_oled() -> tuple[ArctisNovaProOled, MagicMock]:
    transport = MagicMock()
    oled = ArctisNovaProOled(transport)
    return oled, transport


# ── encode_frame — output size ──────────────────────────────────────────────────


class TestEncodeFrameSize:
    def test_output_is_exactly_1024_bytes(self):
        result = encode_frame(white_image())
        assert len(result) == BITMAP_SIZE

    def test_non_128x64_input_is_resized(self):
        small = Image.new("L", (64, 32), 255)
        result = encode_frame(small)
        assert len(result) == BITMAP_SIZE


# ── encode_frame — all-white / all-black ───────────────────────────────────────


class TestEncodeFrameWhiteBlack:
    def test_all_white_image_produces_all_ones(self):
        result = encode_frame(white_image())
        assert result == bytes([0xFF] * BITMAP_SIZE)

    def test_all_black_image_produces_all_zeros(self):
        result = encode_frame(black_image())
        assert result == bytes([0x00] * BITMAP_SIZE)


# ── encode_frame — column-major bit packing ────────────────────────────────────


class TestEncodeFrameBitPacking:
    """Verify pixel(x,y) → byte[x*8 + y//8], bit y%8 (LSB-first)."""

    def test_pixel_0_0_sets_bit_0_of_byte_0(self):
        result = encode_frame(single_pixel_image(0, 0))
        assert result[0] & 0x01 == 0x01    # bit 0 of byte 0

    def test_pixel_0_7_sets_bit_7_of_byte_0(self):
        result = encode_frame(single_pixel_image(0, 7))
        assert result[0] & 0x80 == 0x80    # bit 7 of byte 0

    def test_pixel_1_0_sets_bit_0_of_byte_8(self):
        # column 1 starts at byte index 1*8=8
        result = encode_frame(single_pixel_image(1, 0))
        assert result[8] & 0x01 == 0x01

    def test_pixel_127_63_sets_bit_7_of_byte_1023(self):
        # column 127 → byte 127*8=1016..1023; y=63 → byte offset 63//8=7, bit 63%8=7
        result = encode_frame(single_pixel_image(127, 63))
        assert result[1023] & 0x80 == 0x80

    def test_pixel_0_3_sets_bit_3_of_byte_0(self):
        result = encode_frame(single_pixel_image(0, 3))
        assert result[0] & (1 << 3) != 0

    def test_single_pixel_does_not_bleed_to_adjacent_columns(self):
        result = encode_frame(single_pixel_image(5, 0))
        # column 5 byte range = 40–47; columns before and after must be zero
        assert all(b == 0 for b in result[0:40])
        assert all(b == 0 for b in result[48:])


# ── encode_frame — threshold ────────────────────────────────────────────────────


class TestEncodeFrameThreshold:
    def test_threshold_0_any_brightness_is_lit(self):
        img = single_pixel_image(0, 0, brightness=1)
        result = encode_frame(img, threshold=0)
        assert result[0] & 0x01 == 0x01

    def test_threshold_255_no_pixel_below_passes(self):
        img = single_pixel_image(0, 0, brightness=254)
        result = encode_frame(img, threshold=255)
        assert result[0] & 0x01 == 0x00

    def test_default_threshold_128_mid_grey_not_lit(self):
        img = single_pixel_image(0, 0, brightness=127)
        result = encode_frame(img)   # default threshold=128
        assert result[0] & 0x01 == 0x00

    def test_default_threshold_128_bright_pixel_is_lit(self):
        img = single_pixel_image(0, 0, brightness=128)
        result = encode_frame(img)
        assert result[0] & 0x01 == 0x01


# ── draw_raw contract ──────────────────────────────────────────────────────────


class TestDrawRaw:
    def test_calls_write_feature_report_twice(self):
        oled, transport = make_oled()
        oled.draw_raw(bytes(BITMAP_SIZE))
        assert transport.write_feature_report.call_count == 2

    def test_first_report_has_dst_x_0(self):
        oled, transport = make_oled()
        oled.draw_raw(bytes(BITMAP_SIZE))
        first_call_payload = transport.write_feature_report.call_args_list[0][0][1]
        # payload[0]=CMD_OLED_DRAW, payload[1]=dst_x
        assert first_call_payload[1] == 0       # left half starts at x=0

    def test_second_report_has_dst_x_64(self):
        oled, transport = make_oled()
        oled.draw_raw(bytes(BITMAP_SIZE))
        second_call_payload = transport.write_feature_report.call_args_list[1][0][1]
        assert second_call_payload[1] == 64     # right half starts at x=64

    def test_raises_for_bitmap_too_short(self):
        oled, _ = make_oled()
        with pytest.raises(ValueError):
            oled.draw_raw(bytes(BITMAP_SIZE - 1))

    def test_raises_for_bitmap_too_long(self):
        oled, _ = make_oled()
        with pytest.raises(ValueError):
            oled.draw_raw(bytes(BITMAP_SIZE + 1))

    def test_reports_use_cmd_oled_draw(self):
        oled, transport = make_oled()
        oled.draw_raw(bytes(BITMAP_SIZE))
        for c in transport.write_feature_report.call_args_list:
            payload = c[0][1]
            assert payload[0] == C.CMD_OLED_DRAW


# ── clear ──────────────────────────────────────────────────────────────────────


class TestClear:
    def test_clear_sends_all_zero_bitmap(self):
        oled, transport = make_oled()
        oled.clear()
        assert transport.write_feature_report.call_count == 2
        # All pixel data in both reports must be zero (after the 5-byte header in payload)
        for c in transport.write_feature_report.call_args_list:
            payload = c[0][1]
            pixel_data = payload[5:]
            assert all(b == 0 for b in pixel_data)


# ── release ────────────────────────────────────────────────────────────────────


class TestRelease:
    def test_release_uses_write_not_feature_report(self):
        oled, transport = make_oled()
        oled.release()
        transport.write.assert_called_once_with(C.CMD_OLED_RELEASE)
        transport.write_feature_report.assert_not_called()

    def test_release_sends_correct_command(self):
        oled, transport = make_oled()
        oled.release()
        transport.write.assert_called_with(C.CMD_OLED_RELEASE)


# ── width / height properties ──────────────────────────────────────────────────


class TestDimensions:
    def test_width_is_128(self):
        oled, _ = make_oled()
        assert oled.width == 128

    def test_height_is_64(self):
        oled, _ = make_oled()
        assert oled.height == 64
