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

All events confirmed in session `2026-05-01` on PID `0x12E0`. All arrive on the `0xFF00` (Col02) handle with report ID `0x07`.

### 3.1 Volume — `0x25` ✅

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

### 3.2 Connectivity Mode — `0xB5` ✅

Fires on connection-state changes (wireless link established/lost, Bluetooth).

```
[reportId, 0xB5, _, btFlag, wirelessFlag, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xB5` |
| 2 | Always `0x01` in all observations; meaning TBD (possibly "base station present") |
| 3 | Bluetooth flag: `1` = Bluetooth active |
| 4 | Wireless flag: `8` = wireless (2.4 GHz) active; `4` observed when headset goes out of range |

**Decoding:**
```
wireless  = (data[4] === 8)
bluetooth = (data[3] === 1)
connected = wireless
if wireless → force anc_mode = "off"
```

**State fields:** `connected`, `wireless`, `bluetooth`, `anc_mode` (forced `"off"` when wireless)

> Observed values for data[4]: `0x08` (wireless active), `0x04` (wireless lost/out of range).

---

### 3.3 Battery Levels — `0xB7` ✅

Fires on battery-level updates for both the headset and the charging dock.

```
[reportId, 0xB7, headsetLevel, dockLevel, unknown, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xB7` |
| 2 | Headset battery level (0–8 raw) |
| 3 | Dock/base battery level (0–8 raw) |
| 4 | Observed as `0x08` consistently; meaning TBD |

**Decoding:**
```
BATTERY_MAX = 8
headset_battery_percent = round(clamp(data[2] / 8 × 100, 0, 100))
base_battery_percent    = round(clamp(data[3] / 8 × 100, 0, 100))
```

**State fields:** `headset_battery_percent`, `base_battery_percent` (both 0–100)

---

### 3.4 OLED Brightness — `0x85` ✅

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

### 3.5 Sidetone Level — `0x39` ✅

Fires when the sidetone (microphone self-monitoring) level is changed.

```
[reportId, 0x39, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0x39` |
| 2 | Sidetone step: `0`=off, `1`=low, `2`=medium, `3`=high |

**Decoding:**
```
sidetone_level = data[2]   // 0–3
```

**State field:** `sidetone_level` (0–3)

> Note: the `0x20` query response also contains a sidetone field at `data[3]`, but in a different (larger) raw scale. The relationship between the two representations needs further mapping.

---

### 3.6 ANC Mode — `0xBD` ✅

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

### 3.9 Gain Level — `0x27` ✅

Fires when the user changes the microphone gain setting on the headset.

```
[reportId, 0x27, gainLevel, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x27` |
| 2 | Gain level: `1` = low, `2` = high |

**Decoding:**
```
gain_level = data[2]   // observed: 1=low, 2=high; full range TBD
```

**State field:** `gain_level`

> Full range of data[2] values not yet determined. Only `1` (low) and `2` (high) observed in session `2026-05-01`. Additional values may exist.

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
| `sidetone_level` | `0x39` | `number \| null` (0–3) |
| `connected` | `0xB5` | `boolean \| null` |
| `wireless` | `0xB5` | `boolean \| null` |
| `bluetooth` | `0xB5` | `boolean \| null` |
| `oled_brightness` | `0x85` | `number \| null` (1–10) |
| `chatmix_game` | `0x45` | `number \| null` (0–100) |
| `chatmix_chat` | `0x45` | `number \| null` (0–100) |
| `gain_level` | `0x27` | `number \| null` (1=low, 2=high; range TBD) |

---

## 6. Query Commands ✅ / 🔬

### 6.1 Confirmed Query Commands (respond on `0xFFC0`)

All queries use: `[0x06, cmdByte, 0x00, ..., 0x00]` (64 bytes). Confirmed in session `2026-05-01`.

#### `0xB0` — Status ✅

Response: `[0x06, 0xB0, ?, ?, ?, ?, headset_bat, dock_bat, ?, ?, ?, ?, ?, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0xB0` | Command echo |
| 2–5 | `00 00 01 00` | Partially unknown; `[4]=0x01` may be charging state |
| 6 | `0x00`–`0x08` | Headset battery raw (÷ 8 × 100 = %) |
| 7 | `0x00`–`0x08` | Dock battery raw (÷ 8 × 100 = %) |
| 8–15 | variable | Meaning TBD |

> Fields [2-5] and [8+] not yet fully mapped. **Do not assume Nova 7X offsets apply here.**

#### `0x20` — Mic / EQ Params ✅

Response: `[0x06, 0x20, gain, sidetone_raw, unk, unk, unk, eq×10, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x20` | Command echo |
| 2 | `0x01` | Gain level (matches `0x27` event value) |
| 3 | raw value | Sidetone in a raw scale (observed `0x1A`=26); mapping to 0–3 steps TBD |
| 4 | `0x02` | Unknown |
| 5–6 | `0x00` | Padding/unknown |
| 7–16 | 10 bytes | EQ band values (0–40, `0x14`=20=center=0 dB) |
| 17+ | variable | Further settings TBD |

#### `0x10` — Firmware Version ✅

Response bytes `[2+]`: null-terminated ASCII string, e.g. `'0000.003.0820001.031.0000002.002.0010002.001.000'`.

Also pushed **unsolicited** on the `0xFFC0` handle when the headset re-establishes its wireless link.

#### `0x12` — Serial Number ✅

Response bytes `[2+]`: null-terminated ASCII string, e.g. `'6152048313222500747'`.

---

### 6.2 Unresponsive on Nova Pro

| Command | Origin | Observation |
|---|---|---|
| `0xA0` | Nova 7X | Query sent, **no response received** on Nova Pro (session `2026-05-01`) |

---

### 6.3 Candidate Write Commands 🔬

Not yet sent to device. Origin: Arctis Nova 7X protocol + HeadsetControl.

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0x37` | Set mic volume | `[2]` | 0–7 | |
| `0x39` | Set sidetone | `[2]` | 0–3 | 0=off 1=low 2=medium 3=high |
| `0x3A` | Volume limiter | `[2]` | 0/1 | 0=off, 1=on (hearing protection) |
| `0xA3` | Set idle timeout | `[2]` | 0–90 | Minutes; 0=never sleep |
| `0xAE` | LED brightness | `[2]` | 0–3 | Mute indicator LED |
| `0x09` | Save / persist | — | — | Call after config changes to write to flash |

### 6.4 Candidate EQ Commands 🔬

| Command | Description | Notes |
|---|---|---|
| `0x32` | Query EQ params | Response: profile ID + 10 band values |
| `0x33` | Set EQ params | Profile + 10 bands × 6 bytes each |
| `0xA6` | Query EQ preset name | Profile ID + ASCII name |
| `0xA7` | Set EQ preset name | Profile ID + mode + ASCII name |

> **EQ profile byte:** `0x00` = 2.4 GHz wireless profile, `0x01` = Bluetooth profile.
