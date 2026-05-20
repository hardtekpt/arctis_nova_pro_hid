from __future__ import annotations

from dataclasses import dataclass, field

from ...core.types import (
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


# ── Connectivity ───────────────────────────────────────────────────────────

@dataclass
class ConnectivityStatus:
    usb:           bool       # True = USB HID connection present
    headset_power: bool       # True = headset is on / in dock (0x08); False = off/removed (0x01)
    wireless:      bool       # True = 2.4 GHz link active (0x08); False = searching/absent
    bt:            BtStatus   # derived from mode_raw, bt_active, bt_connected


# ── Query response models ──────────────────────────────────────────────────

@dataclass
class StatusData:
    headset_battery_pct: float
    dock_battery_pct:    float
    transparency_level:  int             # 0xB0[8]: 1–10 (meaningful in TRANSPARENCY mode)
    mic_muted:           bool
    anc_mode:            AncMode
    mic_led_brightness:  int             # 1–10
    wireless_mode:       WirelessMode
    bt_default:          bool            # 0xB0[2]: True=on (BT auto-connect enabled)
    bt_auto_mute:        BtAutoMute      # 0xB0[3]: OFF / DB_MINUS_12 / FULL
    auto_off_timeout:    TimeoutStep     # 0xB0[12]: OFF=0 … SIXTY_MIN=6
    # Connectivity snapshot from this packet (also updates headset.connectivity)
    headset_power:       bool            # 0xB0[15]: True=headset on/in dock
    wireless:            bool            # 0xB0[14]: True=2.4 GHz link active
    bt:                  BtStatus        # derived from 0xB0[4,5]; CONNECTED not available here


@dataclass
class DisplayData:
    dim_timeout:       TimeoutStep    # 0x80[2]: OFF=0 … SIXTY_MIN=6
    oled_brightness:   int            # 0x80[3]: 1–10
    home_screen_mode:  HomeScreenMode # 0x80[5]: DETAILED=0  SIMPLE=1
    sonar_running:     bool           # 0x80[7]: True if GG Sonar is running


@dataclass
class VolumeLimiterData:
    limiter_on: bool   # 0x26[2]: True=on (0x01)  False=off (0x02)


@dataclass
class BatteryData:
    headset_pct:     float   # 0xB7[2]: raw ÷ 8 × 100 = %
    dock_pct:        float   # 0xB7[3]: raw ÷ 8 × 100 = %
    headset_powered: bool    # 0xB7[4]: True=headset on/in dock (also updates headset.connectivity)


@dataclass
class MicEqData:
    volume_pct:      float
    gain:            GainLevel
    eq_preset_index: int
    eq_bands:        list[int] = field(default_factory=list)  # 10 values 0–40; 20=flat
    usb_input:       int = 0           # 0x00=Input1, 0x01=Input2
    mic_volume:      int = 0           # 1–10
    sidetone:        SidetoneLevel = SidetoneLevel.OFF
    audio_output:    AudioOutput   = AudioOutput.SPEAKERS
    chatmix_game:    int = 100
    chatmix_chat:    int = 100
    stream_main_vol: int = 100
    stream_aux_vol:  int = 100
    stream_mic_vol:  int = 100


# ── Event dataclasses ─────────────────────────────────────────────────────
# Each maps to a single Col02 event opcode (or a filtered Col01 packet).
# Use the class name as the event_name key in EventDispatcher.

@dataclass
class VolumeEvent:
    percent: float


@dataclass
class BatteryEvent:
    headset_pct: float
    dock_pct:    float


@dataclass
class ConnectivityEvent:
    connectivity: ConnectivityStatus


@dataclass
class AncModeEvent:
    mode: AncMode


@dataclass
class MicMuteEvent:
    muted: bool


@dataclass
class ChatMixEvent:
    game: int   # 0–100
    chat: int   # 0–100


@dataclass
class GainEvent:
    level: GainLevel


@dataclass
class MicVolumeEvent:
    level: int   # 1–10


@dataclass
class SidetoneEvent:
    level: SidetoneLevel


@dataclass
class OledBrightnessEvent:
    level: int   # 1–10


@dataclass
class TransparencyEvent:
    level: int   # 1–10 (only valid when ANC=TRANSPARENCY)


@dataclass
class WirelessModeEvent:
    mode: WirelessMode


@dataclass
class UsbInputEvent:
    input_num: int   # 0=Input1, 1=Input2


@dataclass
class BtDefaultEvent:
    enabled: bool


@dataclass
class BtAutoMuteEvent:
    mode: BtAutoMute


@dataclass
class AudioOutputEvent:
    output: AudioOutput


@dataclass
class StreamVolumesEvent:
    main: int   # 0–100
    aux:  int   # 0–100
    mic:  int   # 0–100


@dataclass
class EqPresetEvent:
    index: int   # 0x04=custom  0x00–0x03 and 0x05–0x18=named presets


@dataclass
class EqBandEvent:
    band:  int   # 1–10 (1-indexed)
    level: int   # 0–40; 20=flat/0 dB — event-only, do NOT write via 0x31


@dataclass
class DimTimeoutEvent:
    step: TimeoutStep


@dataclass
class HomeScreenEvent:
    mode: HomeScreenMode


@dataclass
class MicLedEvent:
    level: int   # 1–10


@dataclass
class AutoOffEvent:
    step: TimeoutStep


@dataclass
class DeviceDisconnectedEvent:
    """Fired when the USB HID connection is lost (e.g. cable unplugged, USB input switched)."""


@dataclass
class DeviceReconnectedEvent:
    """Fired when the USB HID connection is restored after a disconnection."""
