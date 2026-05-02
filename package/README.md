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

For OLED drawing (text, images, animations, GIFs):

```bash
pip install -e 'package/[oled]'
```

**Requirements:** Python 3.10+, `hidapi`. Pillow is optional — only needed for OLED drawing.

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

## OLED display control

Requires `pip install 'arctis-hid[oled]'` (Pillow).

Access the OLED controller via `headset.oled`. It releases control back to GG automatically when used as a context manager.

```python
from arctis_hid import discover

with discover() as h:
    h.set_oled_brightness(7)   # 1–10; uses the standard 0x85 write command

    with h.oled:               # restores GG screen on exit
        # Static image (PNG, JPEG, BMP, …)
        h.oled.draw_image("banner.png")

        # Text — default bitmap font, or pass a PIL ImageFont
        h.oled.draw_text("Hello, World!")
        h.oled.draw_text("Inverted", x=0, y=24, invert=True)

        # Scroll text left-to-right (one pass)
        h.oled.scroll_text("Now playing: Track 1", fps=25)

        # Frame-by-frame animation (PIL Images or file paths)
        h.oled.play_animation(["f1.png", "f2.png", "f3.png"], fps=10, loops=3)

        # GIF — uses embedded frame delays, or override with fps=
        h.oled.play_gif("spinner.gif")
        h.oled.play_gif("fast.gif", fps=20, loops=0)   # loops=0 → forever

        # Blank screen
        h.oled.clear()
```

### OLED methods

| Method | Description |
|--------|-------------|
| `draw_image(image, threshold=128)` | Draw a static image. Accepts a PIL Image or a file path. Resizes to 128×64. |
| `draw_text(text, font=None, x=0, y=0, invert=False)` | Render text onto the display. Pass a PIL ImageFont for custom fonts/sizes. |
| `scroll_text(text, font=None, fps=20.0, invert=False)` | Scroll text across the display from right to left (one full pass). |
| `play_animation(frames, fps=10.0, loops=1, threshold=128)` | Play a list of PIL Images or file paths as an animation. `loops=0` = forever. |
| `play_gif(path, fps=None, loops=1, threshold=128)` | Play a GIF. Uses embedded frame delays unless `fps` is specified. `loops=0` = forever. |
| `clear()` | Blank the display (all pixels off). |
| `release()` | Return OLED control to GG / Sonar. Called automatically on context exit. |
| `draw_raw(bitmap)` | Send a pre-encoded 1024-byte column-major 1-bit bitmap directly. No Pillow needed. |

### `encode_frame` — advanced use

For pre-processing pipelines:

```python
from arctis_hid import encode_frame
from PIL import Image

bitmaps = [encode_frame(Image.open(f)) for f in frame_files]

with discover() as h:
    for bm in bitmaps:
        h.oled.draw_raw(bm)
```

`encode_frame(img, threshold=128) → bytes` converts any PIL Image to the 1024-byte column-major 1-bit bitmap the device expects. Pixel layout: column-major, LSB = top (y=0), `pixel(x,y)` → `byte x*8 + y//8`, `bit y%8`.

---

## CLI demo

```bash
python package/examples/oled_demo.py brightness 5
python package/examples/oled_demo.py text "Hello, World!"
python package/examples/oled_demo.py img cool_image.png
python package/examples/oled_demo.py anim -r 10 -l 20 frame1.png frame2.png frame3.png
python package/examples/oled_demo.py gif animation.gif
python package/examples/oled_demo.py gif --fps 15 animation.gif
python package/examples/oled_demo.py scroll "Now playing: Something Cool"
python package/examples/oled_demo.py release
```

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
- **OLED draw not tested on hardware yet**: The `0x93` protocol was confirmed from [ggoled](https://github.com/JerwuQu/ggoled) source code. If you encounter display artifacts, the bitmap packing or report timing may need adjustment — please open an issue with a description of what you see.
