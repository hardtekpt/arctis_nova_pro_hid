"""arctis-hid — Python HID API for SteelSeries Arctis Nova Pro Wireless."""

from .discovery import discover
from .exceptions import DeviceError, DeviceIOError, DeviceNotFoundError

# Enums
from .core.types import (
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

# Query response models
from .devices.nova_pro.models import (
    BatteryData,
    ConnectivityStatus,
    DisplayData,
    MicEqData,
    StatusData,
    VolumeLimiterData,
)

# Event dataclasses
from .devices.nova_pro.models import (
    AncModeEvent,
    AudioOutputEvent,
    AutoOffEvent,
    BatteryEvent,
    BtAutoMuteEvent,
    BtDefaultEvent,
    ChatMixEvent,
    ConnectivityEvent,
    DeviceDisconnectedEvent,
    DeviceReconnectedEvent,
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
    UsbInputEvent,
    VolumeEvent,
    WirelessModeEvent,
)

# Base classes (for type hints and extension)
from .devices.base import AbstractHeadset, AbstractOled
from .devices.nova_pro.headset import ArctisNovaProWireless

# OLED — requires Pillow (pip install 'arctis-hid[oled]')
from .devices.nova_pro.oled import ArctisNovaProOled, encode_frame

__all__ = [
    "discover",
    # exceptions
    "DeviceError",
    "DeviceIOError",
    "DeviceNotFoundError",
    # enums
    "AncMode",
    "AudioOutput",
    "BtAutoMute",
    "BtStatus",
    "GainLevel",
    "HomeScreenMode",
    "SidetoneLevel",
    "TimeoutStep",
    "UsbInput",
    "WirelessMode",
    # query models
    "StatusData",
    "MicEqData",
    "DisplayData",
    "ConnectivityStatus",
    "VolumeLimiterData",
    "BatteryData",
    # events
    "DeviceDisconnectedEvent",
    "DeviceReconnectedEvent",
    "VolumeEvent",
    "BatteryEvent",
    "ConnectivityEvent",
    "AncModeEvent",
    "MicMuteEvent",
    "ChatMixEvent",
    "GainEvent",
    "MicVolumeEvent",
    "SidetoneEvent",
    "OledBrightnessEvent",
    "TransparencyEvent",
    "UsbInputEvent",
    "WirelessModeEvent",
    "BtDefaultEvent",
    "BtAutoMuteEvent",
    "AudioOutputEvent",
    "StreamVolumesEvent",
    "EqPresetEvent",
    "EqBandEvent",
    "DimTimeoutEvent",
    "HomeScreenEvent",
    "MicLedEvent",
    "AutoOffEvent",
    # base classes
    "AbstractHeadset",
    "AbstractOled",
    "ArctisNovaProWireless",
    # OLED
    "ArctisNovaProOled",
    "encode_frame",
]
