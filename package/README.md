# arctis-hid

Python HID API for the **SteelSeries Arctis Nova Pro Wireless** (and variants).

Provides full programmatic control over every headset setting: volume, ANC, EQ bands, mic, ChatMix, Bluetooth, and more — all via USB HID without any SteelSeries software.

---

## Installation

```bash
pip install -e /path/to/project/package/
```

Or from the project root:

```bash
pip install -e package/
```

**Requirements:** Python 3.10+, `hidapi`

On **Windows** the headset must not be exclusively held by another process (e.g. SteelSeries GG) when opening.

---

## Quick start

### Command mode — query and write

```python
from arctis_hid import discover, AncMode, GainLevel, SidetoneLevel

with discover() as h:
    # Query
    status = h.get_status()
    print(f"Battery: {status.headset_battery_pct:.0f}%")
    print(f"ANC: {status.anc_mode.name}")

    mic = h.get_mic_eq()
    print(f"Volume: {mic.volume_pct:.1f}%")
    print(f"EQ bands: {mic.eq_bands}")

    # Write
    h.set_volume(75)
    h.set_anc_mode(AncMode.ANC)
    h.set_gain(GainLevel.HIGH)
    h.set_sidetone(SidetoneLevel.LOW)
```

### Event mode — listen for callbacks

```python
from arctis_hid import discover

with discover() as h:
    h.on("VolumeEvent",  lambda e: print(f"Volume → {e.percent:.1f}%"))
    h.on("MicMuteEvent", lambda e: print(f"Mic {'muted' if e.muted else 'unmuted'}"))
    h.on("BatteryEvent", lambda e: print(f"Battery → {e.headset_pct:.0f}%"))
    h.listen()   # blocks; press Ctrl-C to exit
```

For non-blocking use:

```python
h.start()   # background thread
# ... do other work ...
h.stop()
```

---

## API reference

### `discover(pid=None) → AbstractHeadset`

Find and open the first connected Arctis Nova Pro Wireless. Raises `DeviceNotFoundError` if nothing is found.

### Query methods

| Method | Returns | Description |
|--------|---------|-------------|
| `get_status()` | `StatusData` | Battery, connectivity, ANC mode, mic mute, OLED brightness, wireless mode |
| `get_mic_eq()` | `MicEqData` | Volume, gain, EQ bands, mic vol, sidetone, audio output, ChatMix, stream volumes |
| `get_firmware_version()` | `str` | Firmware version string |
| `get_serial_number()` | `str` | Device serial number |

### Write methods

| Method | Parameter | Description |
|--------|-----------|-------------|
| `set_volume(pct)` | `float` 0–100 | Headset volume |
| `set_mic_volume(level)` | `int` 1–10 | Mic input volume |
| `set_sidetone(level)` | `SidetoneLevel` | Mic sidetone: OFF / LOW / MEDIUM / HIGH |
| `set_anc_mode(mode)` | `AncMode` | OFF / TRANSPARENCY / ANC |
| `set_transparency_level(level)` | `int` 1–10 | Transparency strength (TRANSPARENCY mode only) |
| `set_oled_brightness(level)` | `int` 1–10 | OLED screen brightness |
| `set_gain(level)` | `GainLevel` | Mic gain: LOW / HIGH |
| `set_mic_led_brightness(level)` | `int` 1–10 | Mic mute LED brightness |
| `set_chatmix_enabled(enabled)` | `bool` | Enable ChatMix dial events |
| `set_wireless_mode(mode)` | `WirelessMode` | PERFORMANCE / EXTENDED_RANGE |
| `set_bt_default(enabled)` | `bool` | Bluetooth on by default |
| `set_bt_auto_mute(mode)` | `BtAutoMute` | OFF / DB_MINUS_12 / FULL |
| `set_audio_output(output)` | `AudioOutput` | SPEAKERS / STREAM |
| `set_stream_volumes(main, aux, mic)` | `int` 0–100 each | Stream output levels |
| `set_eq_preset(index)` | `int` 0–24 | EQ preset (4 = custom) |
| `set_eq_bands(bands)` | `list[int]` × 10 | Custom EQ: 10 values 0–40, 20 = flat. Selects custom preset automatically. |
| `set_dim_timeout(step)` | `TimeoutStep` | OLED dim delay: OFF/1/5/10/15/30/60 min |
| `set_home_screen_mode(mode)` | `HomeScreenMode` | DETAILED / SIMPLE |
| `set_auto_off_timeout(step)` | `TimeoutStep` | Auto power-off: OFF/1/5/10/15/30/60 min |

### Event callbacks

Register with `headset.on("EventClassName", callback)`. Use the class name as the key:

| Event class | Key fields | Trigger |
|-------------|------------|---------|
| `VolumeEvent` | `percent: float` | Volume dial turned |
| `BatteryEvent` | `headset_pct`, `dock_pct` | Battery level change |
| `MicMuteEvent` | `muted: bool` | Mic mute button pressed |
| `AncModeEvent` | `mode: AncMode` | ANC button pressed |
| `ConnectivityEvent` | `mode`, `bt_active`, `wireless` | Connection state change |
| `ChatMixEvent` | `game`, `chat` | ChatMix dial turned (requires `set_chatmix_enabled(True)`) |
| `GainEvent` | `level: GainLevel` | Gain changed |
| `MicVolumeEvent` | `level: int` | Mic volume changed |
| `SidetoneEvent` | `level: SidetoneLevel` | Sidetone changed |
| `OledBrightnessEvent` | `level: int` | OLED brightness changed |
| `TransparencyEvent` | `level: int` | Transparency level changed |
| `WirelessModeEvent` | `mode: WirelessMode` | Wireless mode changed |
| `BtDefaultEvent` | `enabled: bool` | BT default changed |
| `BtAutoMuteEvent` | `mode: BtAutoMute` | BT auto-mute changed |
| `AudioOutputEvent` | `output: AudioOutput` | Audio output changed |
| `StreamVolumesEvent` | `main`, `aux`, `mic` | Stream volumes changed |
| `EqPresetEvent` | `index: int` | EQ preset selected |
| `EqBandEvent` | `band`, `level` | EQ band adjusted (hardware dial — read-only) |
| `DimTimeoutEvent` | `step: TimeoutStep` | Dim timeout changed |
| `HomeScreenEvent` | `mode: HomeScreenMode` | Home screen mode changed |
| `MicLedEvent` | `level: int` | Mic LED brightness changed |
| `AutoOffEvent` | `step: TimeoutStep` | Auto-off timeout changed |

---

## Enum reference

```python
from arctis_hid import AncMode, GainLevel, SidetoneLevel, AudioOutput
from arctis_hid import HomeScreenMode, WirelessMode, BtAutoMute, TimeoutStep

AncMode.OFF / .TRANSPARENCY / .ANC
GainLevel.LOW / .HIGH
SidetoneLevel.OFF / .LOW / .MEDIUM / .HIGH
AudioOutput.SPEAKERS / .STREAM
HomeScreenMode.DETAILED / .SIMPLE
WirelessMode.PERFORMANCE / .EXTENDED_RANGE
BtAutoMute.OFF / .DB_MINUS_12 / .FULL
TimeoutStep.OFF / .ONE_MIN / .FIVE_MIN / .TEN_MIN / .FIFTEEN_MIN / .THIRTY_MIN / .SIXTY_MIN
```

---

## Supported devices

| Model | PID |
|-------|-----|
| Arctis Nova Pro Wireless X | `0x12E0` (tested) |
| Arctis Nova Pro Wireless | `0x12CB`, `0x12CD`, `0x12E5`, `0x225D` (untested) |

---

## Notes

- **EQ workflow**: `set_eq_bands()` automatically selects the custom EQ preset first. If you want to switch to a named preset, call `set_eq_preset(index)` separately.
- **ChatMix**: Call `set_chatmix_enabled(True)` before `ChatMixEvent` callbacks will fire.
- **Wireless mode**: `set_wireless_mode()` is silent — no event fires. Confirm via `get_status().wireless_mode`.
- **OLED screen drawing**: Planned for Phase 3 (see `DEVELOPER.md`).
