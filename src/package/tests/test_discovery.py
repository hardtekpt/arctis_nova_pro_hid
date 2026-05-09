"""Tests for arctis_hid.discovery.discover() — no real HID device needed."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from arctis_hid.devices.nova_pro import constants as C
from arctis_hid.exceptions import DeviceNotFoundError


def _make_info(pid: int = 0x12E0, vid: int = C.VID, interface: int = C.INTERFACE,
               usage_page: int = C.USAGE_CONTROL, path: bytes = b"/fake/ctrl") -> dict:
    return {
        "vendor_id": vid,
        "product_id": pid,
        "interface_number": interface,
        "usage_page": usage_page,
        "path": path,
    }


def _ctrl_and_evt(pid: int = 0x12E0) -> list[dict]:
    return [
        _make_info(pid, usage_page=C.USAGE_CONTROL, path=b"/fake/ctrl"),
        _make_info(pid, usage_page=C.USAGE_EVENTS,  path=b"/fake/evt"),
    ]


# ── Found paths ────────────────────────────────────────────────────────────────


def test_discover_returns_open_headset():
    with patch("hid.enumerate", return_value=_ctrl_and_evt()), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport") as MockTransport:
        from arctis_hid.discovery import discover
        headset = discover()
        MockTransport.return_value.open.assert_called_once()


def test_discover_passes_ctrl_path_to_headset():
    with patch("hid.enumerate", return_value=_ctrl_and_evt()), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        from arctis_hid.devices.nova_pro.headset import ArctisNovaProWireless
        headset = discover()
        assert headset._ctrl_path == b"/fake/ctrl"


def test_discover_passes_evt_path_to_headset():
    with patch("hid.enumerate", return_value=_ctrl_and_evt()), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        headset = discover()
        assert headset._evt_path == b"/fake/evt"


def test_discover_ctrl_only_sets_evt_path_none():
    """If only the control interface is found, evt_path should be None."""
    infos = [_make_info(usage_page=C.USAGE_CONTROL, path=b"/fake/ctrl")]
    with patch("hid.enumerate", return_value=infos), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        headset = discover()
        assert headset._evt_path is None


# ── Not found paths ────────────────────────────────────────────────────────────


def test_discover_raises_if_no_device():
    with patch("hid.enumerate", return_value=[]):
        from arctis_hid.discovery import discover
        with pytest.raises(DeviceNotFoundError):
            discover()


def test_discover_raises_if_wrong_vid():
    infos = [_make_info(vid=0x1234, usage_page=C.USAGE_CONTROL)]
    with patch("hid.enumerate", return_value=infos):
        from arctis_hid.discovery import discover
        with pytest.raises(DeviceNotFoundError):
            discover()


def test_discover_raises_if_wrong_interface():
    infos = [_make_info(interface=3, usage_page=C.USAGE_CONTROL)]
    with patch("hid.enumerate", return_value=infos):
        from arctis_hid.discovery import discover
        with pytest.raises(DeviceNotFoundError):
            discover()


def test_discover_raises_if_wrong_pid():
    infos = [_make_info(pid=0xDEAD, usage_page=C.USAGE_CONTROL)]
    with patch("hid.enumerate", return_value=infos):
        from arctis_hid.discovery import discover
        with pytest.raises(DeviceNotFoundError):
            discover()


# ── PID filtering ──────────────────────────────────────────────────────────────


def test_discover_with_specific_pid_accepts_matching():
    with patch("hid.enumerate", return_value=_ctrl_and_evt(pid=0x12E0)), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        headset = discover(pid=0x12E0)
        assert headset._ctrl_path == b"/fake/ctrl"


def test_discover_with_specific_pid_rejects_other_pid():
    with patch("hid.enumerate", return_value=_ctrl_and_evt(pid=0x12CB)):
        from arctis_hid.discovery import discover
        with pytest.raises(DeviceNotFoundError):
            discover(pid=0x12E0)


@pytest.mark.parametrize("pid", list(C.PIDS))
def test_discover_accepts_all_supported_pids(pid: int):
    with patch("hid.enumerate", return_value=_ctrl_and_evt(pid=pid)), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        headset = discover()
        assert headset._ctrl_path == b"/fake/ctrl"


# ── Unrelated devices are ignored ─────────────────────────────────────────────


def test_discover_ignores_other_hid_devices():
    infos = [
        _make_info(vid=0x046D, pid=0xC33A, usage_page=0xFF00),   # a Logitech mouse
        *_ctrl_and_evt(),                                          # our headset
    ]
    with patch("hid.enumerate", return_value=infos), \
         patch("arctis_hid.devices.nova_pro.headset.HidTransport"):
        from arctis_hid.discovery import discover
        headset = discover()
        assert headset._ctrl_path == b"/fake/ctrl"
