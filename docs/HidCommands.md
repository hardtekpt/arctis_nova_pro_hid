# Arctis Nova Pro Wireless — HID Command Reference

_Last verified: `2026-05-01` — derived from `baseStationEvents.ts`, `oled/service.ts`, Arctis-on-Linux, and Arctis Nova 7X protocol_

This document catalogues every HID packet format discovered for the Arctis Nova Pro Wireless base station (USB receiver). It is written so another agent or developer can re-implement compatible HID communication without reading the source files.

Command status legend:
- **✅ Confirmed** — observed on a Nova Pro (PID `0x12E0`) or derived from its firmware/app
- **🔬 Candidate** — documented on the Arctis Nova 7X (closest sibling); not yet verified on Nova Pro

---

## 1. Device Identification

| Field | Value |
|---|---|
| Vendor ID | `0x1038` (SteelSeries) |
| Interface number | `4` |
| Supported Product IDs | `0x12CB`, `0x12CD`, `0x12E0` ✓, `0x12E5`, `0x225D` |

All reads and writes target **interface 4**. Two HID collections exist on this interface (see Section 2).

---

## 2. Interface Layout

Interface 4 exposes two HID collections. Both must be opened for full operation.

| Collection | Usage Page | Direction | Purpose |
|---|---|---|---|
| `Col01` | `0xFFC0` | Bidirectional | Send commands; read query responses |
| `Col02` | `0xFF00` | Read | Incoming device events (buttons, dials, state) |

**Example paths (PID `0x12E0`, Windows):**

```
Col01  0xFFC0  \\?\HID#VID_1038&PID_12E0&MI_04&Col01#...#{4d1e55b2-...}
Col02  0xFF00  \\?\HID#VID_1038&PID_12E0&MI_04&Col02#...#{4d1e55b2-...}
```

**Packet format (all commands):**

```
[reportId, cmdByte, param0, param1, ..., 0x00, ...]   // zero-padded to 64 bytes
```

| Field | Value | Note |
|---|---|---|
| Report ID (outgoing) | `0x06` | First byte of every write |
| Report ID (incoming) | `0x06` or `0x07` | Byte 0 of every read |
| Packet size | 64 bytes | Fixed; unused bytes padded with `0x00` |

---

## 3. Incoming Events (Device → Host)

### 3.1 Volume — `0x25`

Fires when the user adjusts the hardware volume wheel on the headset.

```
[reportId, 0x25, rawVolume, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x06` or `0x07`) |
| 1 | Command `0x25` |
| 2 | Raw volume (inverted: `0x38 − data[2]` = actual level) |

**Decoding:**
```
rawLevel  = max(0, 0x38 − data[2])          // 0x38 = 56
percent   = round(clamp(rawLevel / 56 × 100, 0, 100))
```

**State field:** `headset_volume_percent` (0–100)

---

### 3.2 Connectivity Mode — `0xB5`

Fires on connection-state changes (wireless link established/lost, Bluetooth).

```
[reportId, 0xB5, _, btFlag, wirelessFlag, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xB5` |
| 2 | Unused |
| 3 | Bluetooth flag: `1` = Bluetooth active |
| 4 | Wireless flag: `8` = wireless (2.4 GHz) active |

**Decoding:**
```
wireless  = (data[4] === 8)
bluetooth = (data[3] === 1)
connected = wireless
if wireless → force anc_mode = "off"
```

**State fields:** `connected`, `wireless`, `bluetooth`, `anc_mode` (forced `"off"` when wireless)

> The wireless flag value `8` is the only observed valid value. Any other value is treated as "not connected via wireless".

---

### 3.3 Battery Levels — `0xB7`

Fires on battery-level updates for both the headset and the charging dock.

```
[reportId, 0xB7, headsetLevel, dockLevel, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xB7` |
| 2 | Headset battery level (0–8 raw) |
| 3 | Dock/base battery level (0–8 raw) |

**Decoding:**
```
BATTERY_MAX = 8
headset_battery_percent = round(clamp(data[2] / 8 × 100, 0, 100))
base_battery_percent    = round(clamp(data[3] / 8 × 100, 0, 100))
```

**State fields:** `headset_battery_percent`, `base_battery_percent` (both 0–100)

---

### 3.4 OLED Brightness — `0x85`

Fires when the user changes OLED display brightness via the headset controls.

```
[reportId, 0x85, brightnessLevel, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0x85` |
| 2 | Brightness level (1–10) |

**Decoding:**
```
if data[2] >= 1 && data[2] <= 10 → oled_brightness = data[2]
else → discard event
```

**State field:** `oled_brightness` (1–10)

---

### 3.5 Sidetone Level — `0x39`

Fires when the sidetone (microphone self-monitoring) level is changed.

```
[reportId, 0x39, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0x39` |
| 2 | Sidetone level (raw numeric value) |

**Decoding:**
```
sidetone_level = data[2]
```

**State field:** `sidetone_level`

---

### 3.6 ANC Mode — `0xBD`

Fires when the user cycles through ANC / Transparency / Off modes on the headset.

```
[reportId, 0xBD, mode, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xBD` |
| 2 | Mode value: `0` = off, `1` = transparency, `2` = ANC |

**Decoding:**
```
0 → anc_mode = "off"
1 → anc_mode = "transparency"
2 → anc_mode = "anc"
other → discard event
```

**State field:** `anc_mode` (`"off"` | `"transparency"` | `"anc"`)

> **Note:** When command `0xB5` reports wireless mode, `anc_mode` is overridden to `"off"` regardless of this event.

---

### 3.7 Microphone Mute — `0xBB` ✅

Fires when the user presses the microphone mute button on the headset.

```
[reportId, 0xBB, muteState, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xBB` |
| 2 | Mute state: `1` = muted, `0` = unmuted |

**Decoding:**
```
mic_mute = (data[2] === 1)
```

**State field:** `mic_mute` (boolean)

---

### 3.8 ChatMix Dial — `0x45` ✅

Fires when the user rotates the ChatMix dial on the base station, adjusting the game/chat audio balance.

```
[reportId, 0x45, gameVol, chatVol, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x45` |
| 2 | Game volume (0–100 decimal, `0x00`–`0x64`) |
| 3 | Chat volume (0–100 decimal, `0x00`–`0x64`) |

**Decoding:**
```
chatmix_game = data[2]   // 0–100
chatmix_chat = data[3]   // 0–100
center position: both values = 100 (0x64)
```

**State fields:** `chatmix_game`, `chatmix_chat` (both 0–100)

> Source: [Arctis-on-Linux](https://github.com/dfanara/Arctis-on-Linux), confirmed for PID `0x12E0`.

---

## 4. Outgoing Commands (Host → Device)

### 4.1 Return to SteelSeries UI — `0x95` ✅

Restores OLED control to the SteelSeries GG / Sonar application. Called after a custom OLED notification expires or when the OLED service stops.

**Transport:** `device.write(payload)`

**Payload (64 bytes):**

```
[0x06, 0x95, 0x00, 0x00, ..., 0x00]
 └─ reportId  └─ command  └─ 62 bytes of 0x00 padding
```

| Byte | Value | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x95` | Command: return control |
| 2–63 | `0x00` | Padding |

Total size: **64 bytes**.

---

### 4.2 OLED Screen Draw — `0x93` ✅

Draws a bitmap frame on the 128×64 OLED display. The screen is split into two 64-pixel-wide vertical halves, each sent as a separate feature report.

**Transport:** `device.sendFeatureReport(report)` — called twice per frame (left half, right half).

**Report structure (1024 bytes per report):**

```
[0x06, 0x93, splitX, 0x00, chunkW, paddedH, <bitmap data ...>]
```

| Byte | Value | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x93` | Command: draw |
| 2 | `0` or `64` | X offset of this chunk (`splitX`) |
| 3 | `0x00` | Y offset (always 0) |
| 4 | `64` | Chunk width in pixels |
| 5 | `64` | Padded height (height rounded up to next multiple of 8 — for 64 px screen: `64`) |
| 6–1023 | packed bits | 1-bit-per-pixel bitmap data |

**Bitmap packing algorithm:**

```
For each pixel (x, y) in the chunk where bitmap[y × screenWidth + splitX + x] !== 0:
  idx = x × paddedHeight + y
  report[(idx >> 3) + 6] |= 1 << (idx & 7)
```

Pixels are packed column-major (x is the outer loop, y is the inner loop), LSB first within each byte.

**Screen specification:**

| Constant | Value |
|---|---|
| `SCREEN_WIDTH` | 128 px |
| `SCREEN_HEIGHT` | 64 px |
| `SCREEN_REPORT_SPLIT_WIDTH` | 64 px |
| `SCREEN_REPORT_SIZE` | 1024 bytes |
| Reports per frame | 2 (left chunk at `splitX=0`, right chunk at `splitX=64`) |

**Animation:** After the first frame, the OLED service sends two more identical frames at +180 ms and +360 ms to compensate for any dropped writes.

---

### 4.3 ChatMix Enable/Disable — `0x49` ✅

Enables or disables the ChatMix feature on the base station.

**Transport:** `device.write(payload)`

**Payload (64 bytes):**

```
[0x06, 0x49, state, 0x00, ..., 0x00]
```

| Byte | Value | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x49` | Command: ChatMix control |
| 2 | `0x01` / `0x00` | `1` = enable, `0` = disable |
| 3–63 | `0x00` | Padding |

> Source: [Arctis-on-Linux](https://github.com/dfanara/Arctis-on-Linux), confirmed for PID `0x12E0`.

---

## 5. State Fields Summary

| Field | Source command | Type |
|---|---|---|
| `headset_battery_percent` | `0xB7` | `number \| null` (0–100) |
| `base_battery_percent` | `0xB7` | `number \| null` (0–100) |
| `base_station_connected` | device presence | `boolean \| null` |
| `headset_volume_percent` | `0x25` | `number \| null` (0–100) |
| `anc_mode` | `0xBD`, `0xB5` | `"off" \| "transparency" \| "anc" \| null` |
| `mic_mute` | `0xBB` | `boolean \| null` |
| `sidetone_level` | `0x39` | `number \| null` |
| `connected` | `0xB5` | `boolean \| null` |
| `wireless` | `0xB5` | `boolean \| null` |
| `bluetooth` | `0xB5` | `boolean \| null` |
| `oled_brightness` | `0x85` | `number \| null` (1–10) |
| `chatmix_game` | `0x45` | `number \| null` (0–100) |
| `chatmix_chat` | `0x45` | `number \| null` (0–100) |

---

## 6. Candidate Commands 🔬

Commands listed here originate from the **Arctis Nova 7X** protocol (closest documented sibling in the Nova line) and/or HeadsetControl. They have **not yet been confirmed** on the Nova Pro Wireless. Use `src/listen.py` to probe these and update this section with observed responses.

### 6.1 Query Commands (Host → Device, then read response on `0xFFC0`)

All queries use the standard 64-byte format: `[0x06, cmdByte, 0x00, ..., 0x00]`.

| Command | Description | Expected response bytes |
|---|---|---|
| `0xB0` | Full status | `[2]` sleep, `[3]` battery%, `[4]` charging, `[5]` game_vol, `[6]` chat_vol, `[10]` mute |
| `0xA0` | Config | `[2]` idle_timeout (0–90 min), `[3]` LED brightness (0–3) |
| `0x20` | Mic params | `[2]` volume (0–7), `[3]` sidetone (0–3), `[4]` volume_limiter (0/1) |
| `0x10` | Firmware version | `[2+]` ASCII string |
| `0x12` | Serial number | `[2+]` ASCII string |

### 6.2 Write Commands (Host → Device, `0xFFC0`)

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0x37` | Set mic volume | `[2]` | 0–7 | |
| `0x39` | Set sidetone | `[2]` | 0–3 | 0=off, 1=low, 2=medium, 3=high |
| `0x3A` | Volume limiter | `[2]` | 0/1 | 0=off, 1=on (hearing protection) |
| `0xA3` | Set idle timeout | `[2]` | 0–90 | Minutes; 0 = never sleep |
| `0xAE` | LED brightness | `[2]` | 0–3 | Mute indicator LED |
| `0x09` | Save / persist | — | — | Call after config changes to write to flash |

### 6.3 EQ Commands (Host → Device, `0xFFC0`)

| Command | Description | Notes |
|---|---|---|
| `0x32` | Query EQ params | Response: profile ID + 10 band values |
| `0x33` | Set EQ params | Profile + 10 bands × 6 bytes each |
| `0xA6` | Query EQ preset name | Profile ID + ASCII name |
| `0xA7` | Set EQ preset name | Profile ID + mode + ASCII name |
| `0x27` | Apply EQ (live preview) | No params; activates the current EQ immediately |

> **EQ profile byte:** `0x00` = 2.4 GHz wireless profile, `0x01` = Bluetooth profile.
