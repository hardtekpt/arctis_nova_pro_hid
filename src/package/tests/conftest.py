"""Shared fixtures and packet-builder helpers for the arctis-hid test suite."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from arctis_hid.devices.nova_pro import constants as C
from arctis_hid.devices.nova_pro.headset import ArctisNovaProWireless


# ── Packet builders ────────────────────────────────────────────────────────────


def make_b0_packet(
    conn: int = 0x01,
    bt: int = 0x00,
    hbat: int = 8,
    dbat: int = 8,
    transp: int = 5,
    mute: int = 0x00,
    anc: int = 0x00,
    mic_led: int = 5,
    mode2g: int = 0x00,
    bt_default: int = 0x00,
    bt_automute: int = 0x00,
    auto_off: int = 0x00,
) -> list[int]:
    """Build a fake 0xB0 status response packet (64 bytes)."""
    pkt = [0] * 64
    pkt[0] = C.REPORT_ID
    pkt[1] = C.CMD_STATUS
    pkt[C.B0_BT_DEFAULT]  = bt_default
    pkt[C.B0_BT_AUTOMUTE] = bt_automute
    pkt[C.B0_CONN]        = conn
    pkt[C.B0_BT]          = bt
    pkt[C.B0_HBAT]        = hbat
    pkt[C.B0_DBAT]        = dbat
    pkt[8]                = transp      # transparency level byte (not in C constants)
    pkt[C.B0_MUTE]        = mute
    pkt[C.B0_ANC]         = anc
    pkt[C.B0_MIC_LED]     = mic_led
    pkt[C.B0_AUTO_OFF]    = auto_off
    pkt[C.B0_MODE2G]      = mode2g
    return pkt


def make_20_packet(
    vol: int = 0x38,
    gain: int = 0x01,
    eq_preset: int = 0x00,
    eq_bands: list[int] | None = None,
    mic_vol: int = 5,
    sidetone: int = 0,
    audio: int = 0x01,
    game: int = 100,
    chat: int = 100,
    smain: int = 100,
    saux: int = 100,
    smic: int = 100,
) -> list[int]:
    """Build a fake 0x20 mic/EQ response packet (64 bytes)."""
    pkt = [0] * 64
    pkt[0] = C.REPORT_ID
    pkt[1] = C.CMD_MIC_EQ
    pkt[2] = 0x01                       # constant protocol byte
    pkt[C.M20_VOL]       = vol
    pkt[C.M20_GAIN]      = gain
    pkt[C.M20_EQ_PRESET] = eq_preset
    bands = eq_bands if eq_bands is not None else [20] * 10
    for i, v in enumerate(bands):
        pkt[7 + i] = v                  # M20_EQ = slice(7, 17)
    pkt[C.M20_MICVOL]   = mic_vol
    pkt[C.M20_SIDETONE] = sidetone
    pkt[C.M20_AUDIO]    = audio
    pkt[C.M20_GAME]     = game
    pkt[C.M20_CHAT]     = chat
    pkt[C.M20_SMAIN]    = smain
    pkt[23]             = 0x00          # padding byte between smain and saux
    pkt[C.M20_SAUX]     = saux
    pkt[C.M20_SMIC]     = smic
    return pkt


def make_event_packet(opcode: int, *payload: int) -> list[int]:
    """Build a fake Col02 event packet (64 bytes).

    data[0] = 0x07 (event report ID), data[1] = opcode, data[2:] = payload.
    """
    pkt = [0] * 64
    pkt[0] = 0x07
    pkt[1] = opcode
    for i, val in enumerate(payload):
        pkt[2 + i] = val
    return pkt


# ── Headset fixture ────────────────────────────────────────────────────────────


@pytest.fixture
def mock_transport() -> MagicMock:
    """A MagicMock that stands in for HidTransport."""
    t = MagicMock()
    t.query.return_value = [0] * 64
    t.poll.return_value = []
    return t


@pytest.fixture
def mock_headset(mock_transport: MagicMock) -> ArctisNovaProWireless:
    """ArctisNovaProWireless with its transport replaced by a MagicMock.

    open() is NOT called — no real HID device is needed.
    """
    headset = ArctisNovaProWireless(b"/dev/fake_ctrl", b"/dev/fake_evt")
    headset._transport = mock_transport
    return headset
