from __future__ import annotations

import hid

from .devices.base import AbstractHeadset
from .devices.nova_pro import constants as C
from .devices.nova_pro.headset import ArctisNovaProWireless
from .exceptions import DeviceNotFoundError


def discover(pid: int | None = None) -> AbstractHeadset:
    """Find the first connected Arctis Nova Pro Wireless and return an open headset instance.

    Args:
        pid: Optionally restrict to a specific product ID. If None, any
             supported Nova Pro PID is accepted.

    Returns:
        An open :class:`ArctisNovaProWireless` instance ready for use.

    Raises:
        DeviceNotFoundError: If no matching device is found.
    """
    target_pids = {pid} if pid is not None else C.PIDS

    ctrl_path: bytes | None = None
    evt_path:  bytes | None = None

    for info in hid.enumerate():
        if info["vendor_id"] != C.VID:
            continue
        if info["product_id"] not in target_pids:
            continue
        if info["interface_number"] != C.INTERFACE:
            continue

        usage = info.get("usage_page", 0)
        path  = info["path"]

        if usage == C.USAGE_CONTROL and ctrl_path is None:
            ctrl_path = path
        elif usage == C.USAGE_EVENTS and evt_path is None:
            evt_path = path

    if ctrl_path is None:
        raise DeviceNotFoundError(
            "No supported Arctis Nova Pro Wireless found. "
            "Ensure the headset is connected and the base station is plugged in."
        )

    headset = ArctisNovaProWireless(ctrl_path, evt_path)
    headset.open()
    return headset
