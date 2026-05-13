# arctis-hid — Package API Documentation

Complete reference for all public classes, functions, enums, and events in the `arctis-hid` package.

**Install:**
```bash
pip install -e src/package/
pip install -e 'src/package/[oled]'   # adds Pillow for OLED drawing
```

**Import root:** `arctis_hid`

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Entry Point — `discover()`](#entry-point--discover)
3. [Class — `ArctisNovaProWireless`](#class--arctisnova prowireless)
   - [Lifecycle](#lifecycle)
   - [Query Methods](#query-methods)
   - [Write Methods](#write-methods)
   - [Event Mode](#event-mode)
   - [OLED Property](#oled-property)
4. [Class — `ArctisNovaProOled`](#class--arctisnovapro oled)
5. [Function — `encode_frame()`](#function--encode_frame)
6. [Data Models](#data-models)
   - [`StatusData`](#statusdata)
   - [`MicEqData`](#miceqdata)
   - [`ConnectivityData`](#connectivitydata)
   - [`DisplayData`](#displaydata)
   - [`VolumeLimiterData`](#volumelimiterdata)
   - [`BatteryData`](#batterydata)
7. [Events](#events)
8. [Enums](#enums)
9. [Exceptions](#exceptions)
10. [Abstract Base Classes](#abstract-base-classes)
11. [Internal Classes](#internal-classes)

---

## Quick Start

```python
from arctis_hid import discover, AncMode, GainLevel

# Command mode
with discover() as h:
    status = h.get_status()
    print(f"Battery: {status.headset_battery_pct:.0f}%")
    h.set_volume(75)
    h.set_anc_mode(AncMode.ANC)

# Event mode
with discover() as h:
    h.on("VolumeEvent", lambda e: print(f"Volume: {e.percent:.0f}%"))
    h.on("BatteryEvent", lambda e: print(f"Battery: {e.headset_pct:.0f}%"))
    h.listen()   # blocks; Ctrl-C to exit

# OLED (requires Pillow)
with discover() as h:
    h.oled.draw_text("Hello!")
    h.oled.draw_image("banner.png")
    h.oled.play_gif("spinner.gif", loops=3)

# OLED hold loop — keep content visible despite firmware animations
with discover() as h:
    h.oled.draw_text("Always on", hold=True)   # redraws every 100 ms
    time.sleep(60)                              # content survives volume knob changes
    h.oled.unhold()
    # oled.release() called automatically on context exit
```

---

## Entry Point — `discover()`

```python
arctis_hid.discover(pid: int | None = None) -> AbstractHeadset
```

Enumerate connected HID devices, locate the first matching Arctis Nova Pro Wireless base station, open both HID collections (control + events), and return a ready-to-use headset instance.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `pid` | `int \| None` | `None` | Restrict search to a specific USB product ID. If `None`, any supported Nova Pro PID is accepted (`0x12CB`, `0x12CD`, `0x12E0`, `0x12E5`, `0x225D`). |

**Returns:** An open `ArctisNovaProWireless` instance.

**Raises:**
- `DeviceNotFoundError` — No matching device was found or the base station is not connected.

**Notes:**
- Always use as a context manager (`with discover() as h:`) so `close()` is guaranteed.
- The returned object is already opened; do not call `open()` again.

---

## Class — `ArctisNovaProWireless`

```python
arctis_hid.ArctisNovaProWireless
```

Full HID API for the SteelSeries Arctis Nova Pro Wireless (and Wireless X variants). Implements `AbstractHeadset`.

**Constructor** (not called directly — use `discover()` instead):
```python
ArctisNovaProWireless(ctrl_path: bytes, evt_path: bytes | None = None)
```

---

### Lifecycle

#### `open() → None`
Open the HID handles. Called automatically by `discover()`.

#### `close() → None`
Stop the event loop (if running) and close all HID handles. Called automatically when used as a context manager.

---

### Query Methods

All query methods send a command to the control collection and parse the synchronous response.

#### `get_status() → StatusData`
Query the headset for current status: battery levels, ANC mode, mic mute state, OLED brightness, wireless mode, and connectivity.

```python
s = h.get_status()
print(s.headset_battery_pct)   # 87.5
print(s.anc_mode)              # AncMode.ANC
```

#### `get_mic_eq() → MicEqData`
Query mic and EQ parameters: headset volume, gain, EQ preset, all 10 EQ band levels, mic volume, sidetone, audio output, ChatMix levels, and stream volumes.

```python
eq = h.get_mic_eq()
print(eq.volume_pct)    # 75.0
print(eq.eq_bands)      # [20, 20, 20, 22, 24, 24, 22, 20, 20, 18]
```

#### `get_firmware_version() → str`
Return the firmware version string (ASCII, from command `0x10`).

#### `get_serial_number() → str`
Return the device serial number (ASCII, from command `0x12`).

#### `get_connectivity() → ConnectivityData`
Query the connectivity mode and BT connection state directly (from command `0xB5`).

```python
c = h.get_connectivity()
print(c.connectivity_mode)   # ConnectivityMode.WIRELESS_AND_BT
print(c.bt_connected)        # True
```

#### `get_display() → DisplayData`
Query the base-station display settings: dim screen timeout, OLED brightness, home screen mode, and whether GG Sonar is running (from command `0x80`).

#### `get_volume_limiter() → VolumeLimiterData`
Query the volume limiter state (from command `0x26`).

#### `get_battery() → BatteryData`
Query the battery levels: headset and dock (from command `0xB7`).

```python
d = h.get_display()
print(d.oled_brightness)    # 7
print(d.dim_timeout)        # TimeoutStep.THIRTY_MIN
print(d.home_screen_mode)   # HomeScreenMode.DETAILED
print(d.sonar_running)      # False

b = h.get_battery()
print(b.headset_pct)        # 85.0
print(b.dock_pct)           # 100.0
```

---

### Write Methods

All write methods automatically send the `0x09` save command after the write to persist settings across power cycles.

#### `set_volume(pct: float) → None`
Set headset output volume. `pct`: 0–100. Encoded as inverted raw value: `raw = round((1 - pct/100) × 56)`.

#### `set_mic_volume(level: int) → None`
Set microphone input volume. `level`: 1–10.

#### `set_sidetone(level: SidetoneLevel) → None`
Set sidetone (mic monitoring) level.

#### `set_anc_mode(mode: AncMode) → None`
Set Active Noise Cancellation mode.

#### `set_transparency_level(level: int) → None`
Set the transparency (ambient sound) level. `level`: 1–10. Only has an audible effect when `AncMode.TRANSPARENCY` is active.

#### `set_oled_brightness(level: int) → None`
Set OLED display brightness. `level`: 1–10.

#### `set_gain(level: GainLevel) → None`
Set microphone gain.

#### `set_mic_led_brightness(level: int) → None`
Set the brightness of the mic mute LED indicator. `level`: 1–10.

#### `set_chatmix_enabled(enabled: bool) → None`
Enable or disable the ChatMix dial feature. `ChatMixEvent` events only fire when enabled.

#### `set_wireless_mode(mode: WirelessMode) → None`
Set the 2.4 GHz wireless mode (performance vs. extended range). No `Col02` event fires for this command — verify the change via `get_status()`.

#### `set_usb_input(input: UsbInput) → None`
Select the active USB input. No `Col02` event fires for this command and no query reflects the current value — verify visually.

#### `set_bt_default(enabled: bool) → None`
Set whether Bluetooth is enabled by default on power-on.

#### `set_bt_auto_mute(mode: BtAutoMute) → None`
Set the Bluetooth auto-mute level when a call comes in.

#### `set_audio_output(output: AudioOutput) → None`
Select the active audio output path (speakers or stream).

#### `set_stream_volumes(main: int, aux: int, mic: int) → None`
Set the three stream output volumes simultaneously. Each value: 0–100.

```python
h.set_stream_volumes(main=80, aux=40, mic=60)
```

#### `set_eq_preset(index: int) → None`
Select an EQ preset by index. Use `0x04` for custom EQ; `0x00`–`0x03` and `0x05`–`0x18` are named factory presets.

#### `set_eq_bands(bands: list[int]) → None`
Set all 10 custom EQ band levels.

`bands`: list of exactly 10 integers, each 0–40; `20` = flat / 0 dB.
Automatically selects the custom EQ preset (`0x04`) before writing the bands.

```python
h.set_eq_bands([20, 20, 22, 24, 26, 24, 22, 20, 20, 18])  # mild V-curve
```

**Raises:** `ValueError` if `bands` does not have exactly 10 elements.

#### `set_dim_timeout(step: TimeoutStep) → None`
Set the OLED screen dim timeout.

#### `set_home_screen_mode(mode: HomeScreenMode) → None`
Set the headset home screen layout (detailed or simple).

#### `set_auto_off_timeout(step: TimeoutStep) → None`
Set the auto power-off timeout.

#### `factory_reset() → None`
Reset the headset to factory defaults (command `0xFD`).

> **⚠ DESTRUCTIVE — irreversible.** All settings (EQ presets, ANC mode, volume, timeouts, BT config, OLED settings, etc.) are wiped. The device disconnects and reboots immediately. This command does **not** send a `0x09` save afterwards.

```python
with discover() as h:
    h.factory_reset()   # device will disconnect; context manager exit is a no-op
```

---

### Event Mode

Register callbacks that fire when the headset sends unsolicited events (button presses, dial changes, wireless state changes).

#### `on(event: str, callback: Callable) → None`
Register a callback for a named event. The event name is the event class name (e.g. `"VolumeEvent"`).

```python
h.on("VolumeEvent", lambda e: print(f"Volume: {e.percent:.0f}%"))
h.on("BatteryEvent", lambda e: print(f"Headset: {e.headset_pct:.0f}%"))
h.on("MicMuteEvent", lambda e: print("Muted" if e.muted else "Unmuted"))
```

#### `off(event: str, callback: Callable) → None`
Unregister a previously registered callback.

#### `listen(timeout: float | None = None) → None`
Block the calling thread and dispatch events until `stop()` is called or `timeout` seconds elapse. Calls `start()` internally.

```python
h.listen()           # block forever
h.listen(timeout=30) # listen for 30 seconds then return
```

#### `start() → None`
Start the event dispatch loop in a background daemon thread. Returns immediately. Use this when you need the main thread free for other work.

#### `stop() → None`
Signal the background event loop to stop and wait up to 2 seconds for the thread to exit.

---

### OLED Property

#### `oled → ArctisNovaProOled`
Return the OLED controller for this headset. The controller is created lazily on first access.

```python
with discover() as h:
    oled = h.oled
    oled.draw_text("Hello!")
```

---

## Class — `ArctisNovaProOled`

```python
arctis_hid.ArctisNovaProOled
```

OLED controller for the Arctis Nova Pro Wireless base station screen (128×64 pixels, 1-bit monochrome).

**Requires Pillow** for all drawing methods except `draw_raw()` and `clear()`:
```bash
pip install 'arctis-hid[oled]'
```

Protocol: two 1024-byte `0x93` HID feature reports per frame (left/right 64-column halves). Bitmap is column-major, 1-bit, LSB-first. Confirmed from [ggoled](docs/GgoledReference.md).

**Constructor** (accessed via `headset.oled`, not directly):
```python
ArctisNovaProOled(transport: HidTransport)
```

---

### Properties

#### `width → int`
Display width in pixels (`128`).

#### `height → int`
Display height in pixels (`64`).

---

### Core Methods

#### `draw_raw(bitmap: bytes, *, hold: bool = False, hold_interval: float = 0.1) → None`
Send a pre-encoded bitmap directly to the display.

`bitmap` must be exactly **1024 bytes** in column-major 1-bit format (use `encode_frame()` to produce it from a PIL Image).

Pass `hold=True` to start the continuous hold loop after drawing (see [`hold()`](#holdbitmap-bytes--none--interval-float--01--none) below).

#### `clear() → None`
Blank the display (all pixels off). If the hold loop is active it continues, now reissuing the blank frame. Call `release()` to fully return control to GG/Sonar.

#### `release() → None`
Stop any active hold loop, then return OLED control to SteelSeries GG / Sonar. Called automatically when the parent headset closes.

---

### Hold Loop

The hold loop continuously reissues the last drawn frame at a fixed interval. It runs in a background daemon thread and overwrites any firmware-driven animation (e.g. the volume-change overlay from the base station) on the next tick, keeping your custom content visible.

#### `hold(bitmap: bytes | None = None, *, interval: float = 0.1) → None`
Start (or restart) the continuous redraw loop.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `bitmap` | `bytes \| None` | `None` | Frame to hold; `None` reuses the last drawn frame |
| `interval` | `float` | `0.1` | Seconds between redraws (100 ms default) |

If `bitmap` is `None` and no frame has been drawn yet, raises `ValueError`.
Calling `hold()` while already holding restarts the loop with the new interval. The held content updates automatically whenever a new draw call is made — no need to restart.

```python
with discover() as h:
    h.oled.draw_text("Volume: 75%")
    h.oled.hold()             # keep reissuing every 100 ms
    time.sleep(30)
    h.oled.unhold()
```

#### `unhold() → None`
Stop the hold loop. The screen stays as-is; the loop simply stops reissuing frames.

#### `holding → bool`
`True` while the hold loop is actively reissuing frames.

---

### Drawing Methods (require Pillow)

#### `draw_image(image: Image | str | Path, threshold: int = 128, *, hold: bool = False, hold_interval: float = 0.1) → None`
Draw a static image. Accepts a PIL `Image` object or a file path (PNG, JPG, GIF, etc.).

The image is resized to 128×64 using Lanczos resampling and converted to 1-bit using the `threshold` value (pixels ≥ threshold become white).

Pass `hold=True` to start the hold loop immediately after drawing.

```python
h.oled.draw_image("banner.png")
h.oled.draw_image("banner.png", threshold=100)        # darker threshold
h.oled.draw_image("banner.png", hold=True)            # resist firmware animations
h.oled.draw_image("banner.png", hold=True, hold_interval=0.05)  # 50 ms redraw
```

#### `draw_text(text: str, font=None, x: int = 0, y: int = 0, invert: bool = False, *, hold: bool = False, hold_interval: float = 0.1) → None`
Render a text string onto the display.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `text` | `str` | — | Text to render |
| `font` | `ImageFont` \| `None` | `None` | PIL font object; `None` uses a built-in 16px default |
| `x` | `int` | `0` | Left pixel offset |
| `y` | `int` | `0` | Top pixel offset |
| `invert` | `bool` | `False` | `True` = white text on black background |
| `hold` | `bool` | `False` | Start the hold loop after drawing |
| `hold_interval` | `float` | `0.1` | Seconds between redraws when hold is active |

```python
from PIL import ImageFont
font = ImageFont.truetype("arial.ttf", 14)
h.oled.draw_text("Hello!", font=font, x=10, y=20, invert=True)
h.oled.draw_text("Always on", hold=True)   # firmware animations won't overwrite this
```

#### `scroll_text(text: str, font=None, fps: float = 20.0, invert: bool = False) → None`
Scroll text from right to left across the display (one full pass). Blocks until the animation completes.

#### `play_animation(frames: list, fps: float = 10.0, loops: int = 1, threshold: int = 128) → None`
Play a sequence of PIL Images or file paths as an animation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `frames` | `list` | — | List of PIL Images or file paths |
| `fps` | `float` | `10.0` | Playback speed |
| `loops` | `int` | `1` | Number of times to repeat; `0` = loop forever |
| `threshold` | `int` | `128` | Binarisation threshold |

```python
h.oled.play_animation(["f1.png", "f2.png", "f3.png"], fps=15, loops=3)
```

#### `play_gif(path: str | Path, fps: float | None = None, loops: int = 1, threshold: int = 128) → None`
Play a GIF animation.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str \| Path` | — | Path to the GIF file |
| `fps` | `float \| None` | `None` | Override frame rate; `None` uses the GIF's embedded per-frame delays |
| `loops` | `int` | `1` | Number of times to repeat; `0` = loop forever |
| `threshold` | `int` | `128` | Binarisation threshold |

```python
h.oled.play_gif("spinner.gif", loops=0)        # loop forever
h.oled.play_gif("spinner.gif", fps=30, loops=5) # force 30 fps, 5 loops
```

---

## Function — `encode_frame()`

```python
arctis_hid.encode_frame(img: Image, threshold: int = 128) -> bytes
```

Convert a PIL Image to the 128×64 column-major 1-bit bitmap expected by the headset.

**Parameters:**
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `img` | `PIL.Image.Image` | — | Source image (any mode; resized to 128×64 internally) |
| `threshold` | `int` | `128` | Greyscale threshold: pixels ≥ threshold become white (1), others black (0) |

**Returns:** `bytes` of length 1024.

**Pixel layout:**
```
byte index = x * 8 + (y // 8)
bit  index = y % 8              # bit 0 = y=0 = top row
```

**Example:**
```python
from PIL import Image
from arctis_hid import encode_frame, discover

img = Image.open("logo.png")
bitmap = encode_frame(img, threshold=100)

with discover() as h:
    h.oled.draw_raw(bitmap)
```

---

## Data Models

### `StatusData`

Returned by `get_status()`. Snapshot of headset status.

```python
@dataclass
class StatusData:
    headset_battery_pct: float          # 0.0–100.0
    dock_battery_pct:    float          # 0.0–100.0
    connectivity_mode:   ConnectivityMode  # WIRELESS_ONLY, BT_PAIRING, or WIRELESS_AND_BT
    bt_active:           bool           # True if Bluetooth stream is active
    mic_muted:           bool
    anc_mode:            AncMode
    mic_led_brightness:  int            # 1–10  (0xB0[11])
    wireless_mode:       WirelessMode
    bt_default:          bool              # 0xB0[2]: True=on (BT auto-connect enabled)
    bt_auto_mute:        BtAutoMute        # 0xB0[3]: OFF / DB_MINUS_12 / FULL
    auto_off_timeout:    TimeoutStep       # 0xB0[12]: OFF=0 … SIXTY_MIN=6
    wireless_link_state: WirelessLinkState # 0xB0[14]: ABSENT / SEARCHING / ACTIVE
    headset_powered:     bool              # 0xB0[15]: True=on, False=off/removed
```

---

### `MicEqData`

Returned by `get_mic_eq()`. Snapshot of audio and EQ parameters.

```python
@dataclass
class MicEqData:
    volume_pct:      float          # 0.0–100.0
    gain:            GainLevel
    eq_preset_index: int            # 0x04=custom; 0x00-0x03, 0x05-0x18=named presets
    eq_bands:        list[int]      # 10 values, each 0–40; 20=flat/0 dB
    usb_input:       int            # 0=Input1, 1=Input2
    mic_volume:      int            # 1–10
    sidetone:        SidetoneLevel
    audio_output:    AudioOutput
    chatmix_game:    int            # 0–100
    chatmix_chat:    int            # 0–100
    stream_main_vol: int            # 0–100
    stream_aux_vol:  int            # 0–100
    stream_mic_vol:  int            # 0–100
```

---

### `ConnectivityData`

Returned by `get_connectivity()`. Snapshot of connectivity state from command `0xB5`.

```python
@dataclass
class ConnectivityData:
    connectivity_mode: ConnectivityMode  # 0xB5[3]: WIRELESS_ONLY, BT_PAIRING, or WIRELESS_AND_BT
    bt_connected:      bool              # 0xB5[4]: True if a BT device is connected
```

---

### `DisplayData`

Returned by `get_display()`. Snapshot of base-station display settings.

```python
@dataclass
class DisplayData:
    dim_timeout:       TimeoutStep    # 0x80[2]: OFF=0 … SIXTY_MIN=6
    oled_brightness:   int            # 0x80[3]: 1–10
    home_screen_mode:  HomeScreenMode # 0x80[5]: DETAILED=0  SIMPLE=1
    sonar_running:     bool           # 0x80[7]: True if GG Sonar is running
```

---

### `VolumeLimiterData`

Returned by `get_volume_limiter()`. Volume limiter state from command `0x26`.

```python
@dataclass
class VolumeLimiterData:
    limiter_on: bool   # 0x26[2]: True=on (0x01)  False=off (0x02)
```

**Note:** The encoding is inverted — `0x01` means the limiter is **on**, `0x02` means **off**.

---

### `BatteryData`

Returned by `get_battery()`. Battery levels for headset and dock from command `0xB7`.

```python
@dataclass
class BatteryData:
    headset_pct: float   # 0xB7[2]: raw ÷ 8 × 100 = %
    dock_pct:    float   # 0xB7[3]: raw ÷ 8 × 100 = %
    headset_powered: bool   # 0xB7[4]: True=on, False=off/removed
```

---

## Events

Events are dispatched from the `Col02` (`0xFF00`) HID collection when the user physically interacts with the headset. Register handlers with `headset.on("EventClassName", callback)`.

Each event is a dataclass. The callback receives a single instance.

| Class | Trigger | Fields |
|-------|---------|--------|
| `VolumeEvent` | Volume wheel turned | `percent: float` (0–100) |
| `BatteryEvent` | Battery level update | `headset_pct: float`, `dock_pct: float`, `headset_powered: bool` |
| `HeadsetPoweredEvent` | Headset powered on/removed | `powered: bool` |
| `ConnectivityEvent` | Wireless connection changed | `mode: ConnectivityMode`, `bt_active: bool` (True when mode is `WIRELESS_AND_BT` or `BT_PAIRING`), `bt_connected: bool` (True when a BT device is paired and connected, data[3]==0x01), `wireless: bool` (True only when link is ACTIVE), `wireless_link_state: WirelessLinkState` (SEARCHING=0x04 or ACTIVE=0x08) |
| `AncModeEvent` | ANC button pressed | `mode: AncMode` |
| `MicMuteEvent` | Mic mute button pressed | `muted: bool` |
| `ChatMixEvent` | ChatMix dial turned | `game: int` (0–100), `chat: int` (0–100) |
| `GainEvent` | Gain switch toggled | `level: GainLevel` |
| `MicVolumeEvent` | Mic volume adjusted | `level: int` (1–10) |
| `SidetoneEvent` | Sidetone changed | `level: SidetoneLevel` |
| `OledBrightnessEvent` | OLED brightness changed | `level: int` (1–10) |
| `TransparencyEvent` | Transparency level changed | `level: int` (1–10) |
| `WirelessModeEvent` | 2.4 GHz mode changed | `mode: WirelessMode` |
| `UsbInputEvent` | USB input changed | `input: UsbInput` |
| `BtDefaultEvent` | Bluetooth default changed | `enabled: bool` |
| `BtAutoMuteEvent` | BT auto-mute changed | `mode: BtAutoMute` |
| `AudioOutputEvent` | Audio output changed | `output: AudioOutput` |
| `StreamVolumesEvent` | Stream volumes changed | `main: int`, `aux: int`, `mic: int` |
| `EqPresetEvent` | EQ preset changed | `index: int` |
| `EqBandEvent` | Single EQ band adjusted | `band: int` (1–10), `level: int` (0–40) |
| `DimTimeoutEvent` | Dim timeout changed | `step: TimeoutStep` |
| `HomeScreenEvent` | Home screen mode changed | `mode: HomeScreenMode` |
| `MicLedEvent` | Mic LED brightness changed | `level: int` (1–10) |
| `AutoOffEvent` | Auto-off timeout changed | `step: TimeoutStep` |

**Notes:**
- `ChatMixEvent` only fires when ChatMix is enabled (`set_chatmix_enabled(True)`).
- `EqBandEvent` is **read-only** (event only) — there is no write command for individual bands. Use `set_eq_bands()` to write all 10 at once.
- `WirelessModeEvent` does **not** fire when changed from GG — it is a silent write. Read the current value via `get_status().wireless_mode`.
- `UsbInputEvent` does **not** fire when changed from the host — it is a silent write. There is no query to reflect the current value — verify visually.

---

## Enums

All enums are `IntEnum` subclasses and can be compared directly with their integer values.

### `AncMode`
```python
class AncMode(IntEnum):
    OFF          = 0
    TRANSPARENCY = 1
    ANC          = 2
```

### `ConnectivityMode`
Which radio links are active (returned by `StatusData.connectivity_mode` and `ConnectivityEvent.mode`).
```python
class ConnectivityMode(IntEnum):
    WIRELESS_ONLY   = 0x01   # 2.4 GHz wireless link only
    BT_PAIRING      = 0x02   # Bluetooth pairing mode active
    WIRELESS_AND_BT = 0x04   # 2.4 GHz wireless + Bluetooth active
```

### `GainLevel`
Microphone input gain.
```python
class GainLevel(IntEnum):
    LOW  = 0
    HIGH = 1
```
Wire encoding: `0x01`=LOW, `0x02`=HIGH (same for write, event, and query).

### `SidetoneLevel`
Mic monitoring volume in headset.
```python
class SidetoneLevel(IntEnum):
    OFF    = 0
    LOW    = 1
    MEDIUM = 2
    HIGH   = 3
```

### `AudioOutput`
```python
class AudioOutput(IntEnum):
    SPEAKERS = 1
    STREAM   = 2
```

### `HomeScreenMode`
```python
class HomeScreenMode(IntEnum):
    DETAILED = 0
    SIMPLE   = 1
```

### `WirelessLinkState`
State of the 2.4 GHz wireless link, decoded from `0xB0[14]` (query snapshot) and `0xB5` event `[4]` (live update).
```python
class WirelessLinkState(IntEnum):
    ABSENT   = 0x02   # headset completely absent or powered off (B0[14] only)
    SEARCHING = 0x04  # base station searching / pairing in progress
    ACTIVE   = 0x08   # 2.4 GHz wireless link established
```

### `WirelessMode`
```python
class WirelessMode(IntEnum):
    PERFORMANCE    = 0   # lower latency
    EXTENDED_RANGE = 1   # longer range, slightly higher latency
```

### `UsbInput`
USB input selector for the headset.
```python
class UsbInput(IntEnum):
    INPUT_1 = 0
    INPUT_2 = 1
```

### `BtAutoMute`
Bluetooth auto-mute level when a call arrives.
```python
class BtAutoMute(IntEnum):
    OFF         = 0
    DB_MINUS_12 = 1
    FULL        = 2
```

### `TimeoutStep`
Shared by `set_dim_timeout()` and `set_auto_off_timeout()`.
```python
class TimeoutStep(IntEnum):
    OFF         = 0
    ONE_MIN     = 1
    FIVE_MIN    = 2
    TEN_MIN     = 3
    FIFTEEN_MIN = 4
    THIRTY_MIN  = 5
    SIXTY_MIN   = 6
```

---

## Exceptions

```
DeviceError                         # base class
├── DeviceNotFoundError             # raised by discover() when no device found
└── DeviceIOError                   # raised on HID read/write failure
```

### `DeviceError`
Base class for all `arctis-hid` exceptions.

### `DeviceNotFoundError`
Raised by `discover()` when no supported headset is detected. Check that the base station is connected via USB and the headset is powered on.

### `DeviceIOError`
Raised when a HID `read()`, `write()`, or `send_feature_report()` call fails. Typically indicates the device was disconnected mid-session.

---

## Abstract Base Classes

These are the extension points for supporting additional devices.

### `AbstractHeadset`

```python
arctis_hid.AbstractHeadset   # from arctis_hid.devices.base
```

ABC that all headset implementations must implement. Defines the full public contract:
- **Lifecycle:** `open()`, `close()`
- **Queries:** `get_status()`, `get_mic_eq()`, `get_firmware_version()`, `get_serial_number()`
- **Event mode:** `on()`, `off()`, `listen()`, `start()`, `stop()`
- **OLED:** `oled` property (returns `AbstractOled | None`)
- **Context manager:** `__enter__` / `__exit__` (calls `open()` / `close()`)

### `AbstractOled`

```python
arctis_hid.AbstractOled   # from arctis_hid.devices.base
```

ABC for OLED screen implementations:
- **Properties:** `width`, `height`
- **Core:** `draw_raw(frame: bytes)`, `clear()`, `release()`
- **Context manager:** `__enter__` / `__exit__` (calls `release()`)

---

## Internal Classes

These are not part of the public API but are documented here for contributors and extension authors.

### `HidTransport`  (`arctis_hid.core.transport`)

Low-level HID I/O abstraction managing two device handles.

| Method | Description |
|--------|-------------|
| `open(ctrl_path, evt_path)` | Open both HID handles |
| `close()` | Close all handles |
| `write(cmd, payload)` | Send a 64-byte interrupt OUT packet to the control collection |
| `query(cmd, timeout_ms)` | Send a query and return the first matching response |
| `poll(timeout_ms)` | Non-blocking read of both handles; returns `[(source, data)]` |
| `write_feature_report(report_id, data)` | Send a large HID feature report (OLED draw) |

### `EventDispatcher`  (`arctis_hid.core.dispatcher`)

Simple synchronous callback dispatcher keyed by event class name.

| Method | Description |
|--------|-------------|
| `on(event_name, cb)` | Register callback |
| `off(event_name, cb)` | Unregister callback |
| `emit(event_name, event)` | Fire all callbacks for the given name |
| `emit_typed(event)` | Fire callbacks using `type(event).__name__` as the key |
