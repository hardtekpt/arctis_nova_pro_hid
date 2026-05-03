class DeviceError(Exception):
    """Base exception for all arctis-hid errors."""


class DeviceNotFoundError(DeviceError):
    """Raised when no supported headset is found during discovery."""


class DeviceIOError(DeviceError):
    """Raised when a read or write to the HID device fails."""
