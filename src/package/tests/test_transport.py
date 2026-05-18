"""Tests for HidTransport OSError translation to DeviceIOError."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from arctis_hid.core.transport import HidTransport
from arctis_hid.exceptions import DeviceIOError


def _transport_with_mock_ctrl():
    t = HidTransport()
    t._ctrl = MagicMock()
    return t


class TestPollOsError:
    def test_ctrl_read_oserror_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.read.side_effect = OSError("read error")
        with pytest.raises(DeviceIOError):
            t.poll()

    def test_evt_read_oserror_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.read.return_value = []
        t._evt = MagicMock()
        t._evt.read.side_effect = OSError("read error")
        with pytest.raises(DeviceIOError):
            t.poll()

    def test_no_error_returns_results(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.read.return_value = [0x06, 0xB0] + [0] * 62
        results = t.poll()
        assert len(results) == 1
        assert results[0][0] == "CTRL"


class TestWriteOsError:
    def test_oserror_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.write.side_effect = OSError("write error")
        with pytest.raises(DeviceIOError):
            t.write(0xBD, [0x01])

    def test_negative_return_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.write.return_value = -1
        with pytest.raises(DeviceIOError):
            t.write(0xBD, [0x01])


class TestQueryOsError:
    def test_oserror_on_read_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.write.return_value = 64
        t._ctrl.read.side_effect = OSError("read error")
        with pytest.raises(DeviceIOError):
            t.query(0xB0)


class TestWriteFeatureReportOsError:
    def test_oserror_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.send_feature_report.side_effect = OSError("report error")
        with pytest.raises(DeviceIOError):
            t.write_feature_report(0x93, b"\x00" * 1024)

    def test_negative_return_raises_device_io_error(self):
        t = _transport_with_mock_ctrl()
        t._ctrl.send_feature_report.return_value = -1
        with pytest.raises(DeviceIOError):
            t.write_feature_report(0x93, b"\x00" * 1024)
