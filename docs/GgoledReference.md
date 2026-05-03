# ggoled Reference — Key Takeaways

**ggoled** is an open-source Rust utility by JerwuQu that drives the 128×64 OLED screen on SteelSeries Arctis Nova Pro headsets without needing SteelSeries GG/Engine software. It served as the primary protocol reference for this project's OLED implementation (Phase 3).

Source: https://github.com/JerwuQu/ggoled

---

## Supported Devices

| Device | VID | PID |
|--------|-----|-----|
| Arctis Nova Pro Wired | `0x1038` | `0x12CB` |
| Arctis Nova Pro Wired (Xbox) | `0x1038` | `0x12CD` |
| Arctis Nova Pro Wireless | `0x1038` | `0x12E0` |
| Arctis Nova Pro Wireless (Xbox) | `0x1038` | `0x12E5` |
| Arctis Nova Pro Wireless (Xbox White) | `0x1038` | `0x225D` |

All share **USB interface 4**. On Windows two separate HID collections appear under the same interface; on Linux they may merge into a single `hidraw` node.

The two collections are distinguished by HID report descriptor byte `[1]`:
- `0xC0` → OLED / control collection (usage page `0xFFC0`)
- `0x00` → info / events collection (usage page `0xFF00`)

---

## OLED Protocol

### Display Specs

| Property | Value |
|----------|-------|
| Resolution | 128 × 64 pixels |
| Colour depth | 1-bit (monochrome) |
| Pixel encoding | Column-major, LSB-first (top pixel = bit 0) |
| Bytes per frame | 1024 (128 columns × 8 bytes each) |

### Frame Transmission

Each frame is split into **two 1024-byte HID feature reports** (left and right halves):

| Chunk | `dst_x` | Columns |
|-------|---------|---------|
| Left  | `0`     | 0–63    |
| Right | `64`    | 64–127  |

**Feature report layout** (1024 bytes total, sent via `send_feature_report()`):

```
[0]   = 0x06          report ID
[1]   = 0x93          command: draw
[2]   = dst_x         destination X (0 or 64)
[3]   = dst_y         destination Y (always 0)
[4]   = width         chunk width (64)
[5]   = height        chunk height padded to multiple of 8 (64)
[6…]  = bitmap data   column-major 1-bit pixel data
```

**IMPORTANT**: `send_feature_report()` is used, **not** `write()`. These are distinct HID transport methods — never mix them for OLED draw commands.

### Bitmap Encoding

Pixels are packed **column by column**, with bits ordered **LSB-first** (y=0 is bit 0):

```
For pixel at (x, y):
  byte index = x * 8 + (y // 8)
  bit  index = y % 8             (bit 0 = top, bit 7 = bottom)
```

Each column occupies exactly 8 bytes (64 pixels ÷ 8 bits/byte). A full 128-column frame is 1024 bytes.

### Related HID Commands

| Command | Transport | Purpose |
|---------|-----------|---------|
| `0x93`  | `send_feature_report()` (1024 bytes) | Draw bitmap chunk |
| `0x95`  | `write()` (64 bytes) | Release OLED back to GG/Sonar |
| `0x85`  | `write()` (64 bytes) | Set OLED brightness (1–10) |

### Reliability — Exponential-Backoff Retry

ggoled retries `send_feature_report()` on failure with quadratic back-off:

```
delay = attempt² milliseconds    (attempt = 1, 2, … 10)
delays: 1ms, 4ms, 9ms, 16ms, 25ms, 36ms, 49ms, 64ms, 81ms, 100ms
```
After 10 failures the error is propagated. This mirrors the Python implementation in `src/package/arctis_hid/devices/nova_pro/oled.py`.

---

## Event Parsing (from ggoled source)

ggoled confirms these event opcodes and byte positions:

| Report ID | Command | Meaning | Key bytes |
|-----------|---------|---------|-----------|
| `0x07` | `0x25` | Volume change | `[2]` raw; `pct = 0x38 - raw` |
| `0x07` | `0xB5` | Connectivity | `[2]`=mode, `[3]`=BT, `[4]`=wireless |
| `0x07` | `0xB7` | Battery event | `[2]`=headset, `[3]`=dock (raw 0–8) |
| `0x06` | `0x20` | Volume in 0x20 response | `[3]` raw (different index from event) |
| `0x06` | `0xB0` | Status response | `[6]`=headset_bat, `[7]`=dock_bat, `[5]`=BT, `[4]`=conn |

Volume decoding: `pct = 0x38 - raw` (raw range 0–56; `0x38`=0%, `0x00`=100%).
Battery decoding: `pct = raw / 8 * 100` (raw range 0–8).

---

## Bitmap Operations (from ggoled_lib/src/bitmap.rs)

ggoled's internal `Bitmap` struct uses a flat BitVec in **row-major** order for in-memory manipulation, then re-encodes to column-major when building the HID report:

- `crop(x, y, w, h)` — extract a rectangular sub-bitmap
- `blit(other, x, y, opaque)` — composit one bitmap onto another
- `invert()` — negate all pixels (used for text-on-black rendering)

The Python package (`encode_frame()` in `oled.py`) converts directly from PIL Image to column-major bytes in a single pass, skipping the intermediate row-major representation.

---

## Desktop Application Features (ggoled_app)

The ggoled desktop app demonstrated real-world OLED use cases relevant to this project:

- **Time display** — real-time clock rendered on the OLED
- **Now Playing** — Windows Media API integration for current track info
- **OLED Shifter** — periodically shifts content by a few pixels to reduce burn-in
- **Screensaver** — turns off OLED when the PC is idle (mitigates burn-in)
- **Custom fonts** — TTF/OTF font support via SDL3; bitmap fonts recommended to avoid anti-aliasing artefacts at 128×64

Burn-in is a genuine concern at 128×64 on these OLEDs; the Python package should be used with varying content or low brightness for extended sessions.

---

## CLI Usage Reference (ggoled_cli)

Equivalent operations for reference when comparing with the Python package:

```sh
ggoled brightness 1                            # set brightness low (1–10)
ggoled text "Hello, World!"                    # render text
ggoled img cool_image.png                      # static image
ggoled anim -r 10 -l 20 f1.png f2.png f3.png  # animation at 10 fps, 20 loops
ggoled anim animation.gif                      # GIF playback

# Extract video frames with ffmpeg, then animate
ffmpeg -i video.mp4 -r 20 -vf "scale=128:64:force_original_aspect_ratio=1" frames/%05d.png
ggoled anim -r 20 frames/*
```

Python equivalents live in `src/package/examples/oled_demo.py`.

---

## What the Python Package Inherits from ggoled

| Aspect | ggoled (Rust) | arctis-hid (Python) |
|--------|--------------|---------------------|
| OLED command `0x93` | `send_feature_report()` | `write_feature_report()` in `HidTransport` |
| Release command `0x95` | `write()` | `write()` in `HidTransport` |
| Bitmap encoding | `create_report()` in `lib.rs` | `encode_frame()` in `oled.py` |
| Retry logic | Quadratic back-off, 10 attempts | Same in `_send_report()` in `oled.py` |
| Split frame | 2 × 64-column chunks | Same in `_send_frame()` in `oled.py` |
| Device PIDs | Hardcoded set of 5 | `constants.PIDS` |
