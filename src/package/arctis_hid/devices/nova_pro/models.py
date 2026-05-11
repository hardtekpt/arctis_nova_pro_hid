from __future__ import annotations

from dataclasses import dataclass, field

from ...core.types import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    ConnectivityMode,
    GainLevel,
    HomeScreenMode,
    SidetoneLevel,
    TimeoutStep,
    WirelessMode,
)


# ── Query response models ──────────────────────────────────────────────────

@dataclass
class StatusData:
    headset_battery_pct: float
    dock_battery_pct:    float
    connectivity_mode:   ConnectivityMode
    bt_active:           bool
    mic_muted:           bool
    anc_mode:            AncMode
    mic_led_brightness:  int          # 1–10
    wireless_mode:       WirelessMode
    bt_default:          bool         # 0xB0[2]: True=on (BT auto-connect enabled)
    bt_auto_mute:        BtAutoMute   # 0xB0[3]: OFF / DB_MINUS_12 / FULL
    auto_off_timeout:    TimeoutStep  # 0xB0[12]: OFF=0 … SIXTY_MIN=6


@dataclass
class DisplayData:
    dim_timeout:       TimeoutStep    # 0x80[2]: OFF=0 … SIXTY_MIN=6
    oled_brightness:   int            # 0x80[3]: 1–10
    home_screen_mode:  HomeScreenMode # 0x80[5]: DETAILED=0  SIMPLE=1


@dataclass
class ConnectivityData:
    connectivity_mode: ConnectivityMode
    bt_connected:      bool   # True if a BT device is currently connected


@dataclass
class MicEqData:
    volume_pct:      float
    gain:            GainLevel
    eq_preset_index: int
    eq_bands:        list[int] = field(default_factory=list)  # 10 values 0–40; 20=flat
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
    mode:         ConnectivityMode
    bt_active:    bool   # True when mode is WIRELESS_AND_BT or BT_PAIRING
    bt_connected: bool   # True if a BT device is paired and connected (data[3]==0x01)
    wireless:     bool   # True=connected  False=lost


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
