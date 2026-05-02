# Arctis Nova Pro Wireless — HID Command Reference

_Last verified: `2026-05-01` — derived from `baseStationEvents.ts`, `oled/service.ts`, Arctis-on-Linux, Arctis Nova 7X protocol, and direct HID capture on PID `0x12E0`_

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
| 2 | Connection mode: `0x01` = 2.4 GHz only; `0x04` = 2.4 GHz + Bluetooth active |
| 3 | Bluetooth state: `0x00` = off, `0x01` = BT active, `0x02` = BT transitioning/paired |
| 4 | Wireless link: `0x08` = 2.4 GHz active, `0x04` = wireless lost / out of range |

**Decoding:**
```
wireless  = (data[4] === 8)
bluetooth = (data[3] === 1)
connected = wireless
if wireless → force anc_mode = "off"
```

**State fields:** `connected`, `wireless`, `bluetooth`, `anc_mode` (forced `"off"` when wireless)

> data[4] observed values: `0x08` (wireless active), `0x04` (wireless lost). data[2] observed: `0x01` (2.4 GHz only), `0x04` (2.4 GHz + BT active). data[3] observed: `0x00` (no BT), `0x01` (BT streaming), `0x02` (BT paired, not streaming).

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
| 4 | Dock presence: `0x08` = headset physically in dock; `0x01` = headset removed (battery reads 0%) |

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

> The `0x20` query response encodes sidetone at `data[18]` (same 0–3 scale). `data[3]` in `0x20` is unrelated to sidetone.

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

> Full range confirmed: exactly 2 discrete levels. Raw value `1` = low, `2` = high. No other values exist.

---

### 3.10 Mic Volume — `0x37` ✅

Fires when the user adjusts microphone volume.

```
[reportId, 0x37, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x37` |
| 2 | Mic volume level (1–10) |

**Decoding:**
```
mic_volume = data[2]   // 1 (min) – 10 (max)
```

**State field:** `mic_volume` (1–10)

> `0x37` was assumed to be a host→device write command only (Nova 7X origin). On the Nova Pro it is also an **incoming event**. Whether it is also writable on the Nova Pro is not yet confirmed.

---

### 3.11 Dim Screen Timeout — `0x83` ✅

Fires when the user changes the OLED dim-screen timeout.

```
[reportId, 0x83, timeout, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0x83` |
| 2 | Timeout step: `0`=off, `1`=1 min, `2`=5 min, `3`=10 min, `4`=15 min, `5`=30 min, `6`=60 min |

**State field:** `dim_screen_timeout`

---

### 3.12 Home Screen Mode — `0x89` ✅

Fires when the user toggles the OLED home screen display style.

```
[reportId, 0x89, mode, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0x89` |
| 2 | Mode: `0` = detailed, `1` = simple ✅ |

**State field:** `home_screen_mode`

---

### 3.13 Mic LED Brightness — `0xBF` ✅

Fires when the user adjusts the microphone mute-indicator LED brightness.

```
[reportId, 0xBF, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xBF` |
| 2 | Brightness level (1–10) |

**State field:** `mic_led_brightness` (1–10)

---

### 3.14 Auto Off Timeout — `0xC1` ✅

Fires when the user changes the automatic power-off timeout.

```
[reportId, 0xC1, timeout, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xC1` |
| 2 | Timeout step: `0`=off, `1`=1 min, `2`=5 min, `3`=10 min, `4`=15 min, `5`=30 min, `6`=60 min |

**State field:** `auto_off_timeout`

---

### 3.15 Transparency / ANC Level — `0xB9` ✅

Fires when the user adjusts the transparency or ANC intensity level on the base station.

```
[reportId, 0xB9, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID |
| 1 | Command `0xB9` |
| 2 | Level (1–10) |

**Decoding:**
```
transparency_level = data[2]   // 1 (min) – 10 (max)
```

**State field:** `transparency_level` (1–10)

> Observed in session `2026-05-01` (22:22:xxx): events fired immediately after ANC mode changes while the user adjusted the intensity dial. Range 1–10 confirmed with all 10 values observed.

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
| `headset_battery_percent` | `0xB7`, `0xB0`[6] | `number \| null` (0–100) |
| `base_battery_percent` | `0xB7`, `0xB0`[7] | `number \| null` (0–100) |
| `base_station_connected` | device presence | `boolean \| null` |
| `headset_volume_percent` | `0x25`, `0x20`[3] | `number \| null` (0–100) |
| `anc_mode` | `0xBD`, `0xB5`, `0xB0`[10] | `"off" \| "transparency" \| "anc" \| null` |
| `mic_mute` | `0xBB`, `0xB0`[9] | `boolean \| null` |
| `sidetone_level` | `0x39`, `0x20`[18] | `number \| null` (0–3) |
| `connected` | `0xB5` | `boolean \| null` |
| `wireless` | `0xB5` | `boolean \| null` |
| `bluetooth` | `0xB5` | `boolean \| null` |
| `oled_brightness` | `0x85`, `0xB0`[11] | `number \| null` (1–10) |
| `chatmix_game` | `0x45`, `0x20`[20] | `number \| null` (0–100) |
| `chatmix_chat` | `0x45`, `0x20`[21] | `number \| null` (0–100) |
| `transparency_level` | `0xB9` | `number \| null` (1–10) |
| `gain_level` | `0x27`, `0x20`[4] | `number \| null` (1=low, 2=high) |
| `mic_volume` | `0x37`, `0x20`[17] | `number \| null` (1–10) |
| `dim_screen_timeout` | `0x83` | `number \| null` (0–6; 0=off, 1=1 min … 6=60 min) |
| `home_screen_mode` | `0x89` | `number \| null` (0 or 1) |
| `mic_led_brightness` | `0xBF` | `number \| null` (1–10) |
| `auto_off_timeout` | `0xC1` | `number \| null` (0–6; 0=off, 1=1 min … 6=60 min) |

---

## 6. Query Commands ✅ / 🔬

### 6.1 Confirmed Query Commands (respond on `0xFFC0`)

All queries use: `[0x06, cmdByte, 0x00, ..., 0x00]` (64 bytes). Confirmed in session `2026-05-01`.

#### `0xB0` — Status ✅

Response: `[0x06, 0xB0, ?, ?, conn, bt, headset_bat, dock_bat, 0x08, mic_mute, anc, ?, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0xB0` | Command echo |
| 2–3 | `0x00` | Unknown |
| 4 | `0x01` / `0x04` | **Connectivity mode** — `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active (mirrors `0xB5` data[2]) ✅ |
| 5 | `0x00` / `0x01` | **BT state** — `0x00`=off, `0x01`=BT active (mirrors `0xB5` data[3]) ✅ |
| 6 | `0x00`–`0x08` | **Headset battery** raw (÷ 8 × 100 = %) ✅ |
| 7 | `0x00`–`0x08` | **Dock battery** raw (÷ 8 × 100 = %) ✅ |
| 8 | `0x08` | Constant |
| 9 | `0x00` / `0x01` | **Mic mute** — `0x00`=unmuted, `0x01`=muted ✅ |
| 10 | `0x00`–`0x02` | **ANC mode** — `0x00`=off, `0x01`=transparency, `0x02`=anc ✅ |
| 11 | `0x01`–`0x0A` | **OLED brightness** (1–10; `0x0A`=10=max) ✅ |
| 12–15 | `06 00 08 08` | TBD |

#### `0x20` — Mic / EQ Params ✅

Response: `[0x06, 0x20, ?, vol_raw, gain, 0, 0, eq×10, mic_vol, sidetone, ?, game, chat, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x20` | Command echo |
| 2 | `0x01` | Unknown (constant across all sessions) |
| 3 | `0x00`–`0x38` | **Headset volume raw** — same encoding as `0x25` event: `0x38`=0%, `0x00`=100% ✅ |
| 4 | `0x01` / `0x02` | **Gain level** — `0x01`=low, `0x02`=high ✅ |
| 5–6 | `0x00` | Padding/unknown |
| 7–16 | 10 bytes | **EQ band values** (0–40, `0x14`=20=flat/0 dB) ✅ |
| 17 | `0x01`–`0x0A` | **Mic volume** (1–10) ✅ |
| 18 | `0x00`–`0x03` | **Sidetone level** (0=off, 1=low, 2=medium, 3=high) ✅ |
| 19 | `0x02` | Unknown |
| 20 | `0x00`–`0x64` | **ChatMix game** (0–100) ✅ — mirrors `0x45` event data[2] |
| 21 | `0x00`–`0x64` | **ChatMix chat** (0–100) ✅ — mirrors `0x45` event data[3] |
| 22–25 | `0x64`, `0x00`, `0x64`, `0x64` | TBD |

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
| `0xB2` | Adjacent candidate | Write sent (`send(0xB2, 0x00)`), **no visible effect or response** (session `2026-05-02`) |

---

### 6.3 Confirmed Write Commands ✅

All confirmed working on Nova Pro (PID `0x12E0`, session `2026-05-01/02`).
Write packet: `[0x06, CMD, PARAM, 0x00×61]`. Always follow with `0x09` to persist.

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0x37` | Set mic volume | `[2]` | 1–10 | Also an incoming event (§3.10) ✅ |
| `0x39` | Set sidetone | `[2]` | 0–3 | 0=off, 1=low, 2=medium, 3=high ✅ |
| `0x85` | Set OLED brightness | `[2]` | 1–10 | Also an incoming event (§3.4) ✅ |
| `0x09` | Save / persist | — | — | Call after any write to commit to flash ✅ |

### 6.4 Candidate Write Commands 🔬

Not yet verified on Nova Pro. Origin: Arctis Nova 7X protocol + HeadsetControl.

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0x3A` | Volume limiter | `[2]` | 0/1 | 0=off, 1=on (hearing protection) |
| `0xA3` | Set idle timeout | `[2]` | 0–90 | Minutes; 0=never sleep |
| `0xAE` | LED brightness | `[2]` | 0–3 | Mute indicator LED |

### 6.5 Candidate EQ Commands 🔬

| Command | Description | Notes |
|---|---|---|
| `0x32` | Query EQ params | Response: profile ID + 10 band values |
| `0x33` | Set EQ params | Profile + 10 bands × 6 bytes each |
| `0xA6` | Query EQ preset name | Profile ID + ASCII name |
| `0xA7` | Set EQ preset name | Profile ID + mode + ASCII name |

> **EQ profile byte:** `0x00` = 2.4 GHz wireless profile, `0x01` = Bluetooth profile.
