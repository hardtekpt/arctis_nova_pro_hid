# Arctis Nova Pro Wireless — HID Command Reference

_Last verified: `2026-05-03` — derived from `baseStationEvents.ts`, `oled/service.ts`, Arctis-on-Linux, Arctis Nova 7X protocol, direct HID capture on PID `0x12E0`, and [ggoled](https://github.com/JerwuQu/ggoled) source (OLED protocol)_

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

The base station exposes multiple HID interfaces. Only **Interface 4** is used for control and events.

### All interfaces (observed on PID `0x12E0`, Windows)

| Interface | Usage Page | Usage | Role |
|---|---|---|---|
| 3 | `0x000C` | `0x0001` | Consumer control (media keys) — not used |
| 4 | `0xFF00` | `0x0001` | **Col02** — read-only device events |
| 4 | `0xFFC0` | `0x0001` | **Col01** — bidirectional: send commands, read responses |

### Interface 4 collections

Both must be opened for full operation.

| Collection | Usage Page | Direction | Purpose |
|---|---|---|---|
| `Col01` | `0xFFC0` | Bidirectional | Send commands; read query responses |
| `Col02` | `0xFF00` | Read | Incoming device events (buttons, dials, state) |

**Observed HID paths (PID `0x12E0`, Windows — actual device instance IDs):**

```
Col01  0xFFC0  \\?\HID#VID_1038&PID_12E0&MI_04&Col01#8&26fe868d&0&0000#{4d1e55b2-f16f-11cf-88cb-001111000030}
Col02  0xFF00  \\?\HID#VID_1038&PID_12E0&MI_04&Col02#8&26fe868d&0&0001#{4d1e55b2-f16f-11cf-88cb-001111000030}
```

The instance ID (`8&26fe868d&0`) is hardware-specific and will differ between machines. Enumerate via `hid.enumerate()` filtering on VID `0x1038`, target PID, interface `4`, and usage page (`0xFFC0` or `0xFF00`).

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

### 3.15 Transparency Level — `0xB9` ✅

Fires when the user adjusts the transparency intensity level on the base station.

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

> Confirmed transparency-only (not ANC intensity). Range 1–10 confirmed with all 10 values observed in session `2026-05-01` (22:22:xxx).

---

### 3.16 2.4 GHz Mode — `0xC3` ✅

Fires when the user changes the 2.4 GHz wireless mode between performance and extended range in SteelSeries GG.

```
[reportId, 0xC3, mode, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0xC3` |
| 2 | Mode: `0x00` = performance/speed, `0x01` = extended range |

**Decoding:**
```
0x00 → wireless_mode = "performance"
0x01 → wireless_mode = "range"
```

**State field:** `wireless_2ghz_mode` (`"performance"` | `"range"`)

> Confirmed in session `2026-05-02` (14:02). Also reflected as `0xB0[13]`: `0x00`=performance, `0x01`=range. Write command uses same opcode and encoding (§6.3).

---

### 3.17 BT Auto-Mute — `0xB3` ✅

Fires when the user changes the Bluetooth auto-mute setting in SteelSeries GG.

```
[reportId, 0xB3, mode, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0xB3` |
| 2 | Mode: `0x00` = off, `0x01` = -12 dB, `0x02` = on |

**Decoding:**
```
0x00 → bt_auto_mute = "off"
0x01 → bt_auto_mute = "-12dB"
0x02 → bt_auto_mute = "on"
```

**State field:** `bt_auto_mute` (`"off"` | `"on"` | `"-12dB"`)

> Confirmed in session `2026-05-02` (14:10). Three distinct values confirmed: `0x00`=off, `0x01`=-12dB, `0x02`=on. Write command uses same opcode and encoding (§6.3).

---

### 3.18 Output Stream Volumes — `0x47` ✅

Fires when the user adjusts any of the three output stream channel volumes (main, aux, mic) in SteelSeries GG. All three values are present in every packet.

```
[reportId, 0x47, main, 0x00, aux, mic, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x47` |
| 2 | Main channel volume (0–100) |
| 3 | `0x00` (constant) |
| 4 | Aux channel volume (0–100) |
| 5 | Mic channel volume (0–100) |

**Decoding:**
```
stream_main = data[2]   // 0–100
stream_aux  = data[4]   // 0–100
stream_mic  = data[5]   // 0–100
```

**State fields:** `stream_main`, `stream_aux`, `stream_mic` (all 0–100)

> Confirmed in session `2026-05-02` (14:11). Each channel was swept independently (0→100→0). byte[3] was `0x00` throughout. Note: `0x47` was previously a candidate alias for ChatMix; it is a distinct event with a 3-channel volume layout. Write confirmed `2026-05-02`: `[0x06, 0x47, main, 0x00, aux, mic, 0x00×58]` — same byte layout as the event (§6.3).

---

### 3.19 Audio Output Selection — `0x43` ✅

Fires when the user switches the audio output routing between speaker and stream in SteelSeries GG.

```
[reportId, 0x43, output, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x43` |
| 2 | Output: `0x01` = speaker, `0x02` = stream |

**Decoding:**
```
0x01 → audio_output = "speaker"
0x02 → audio_output = "stream"
```

**State field:** `audio_output` (`"speaker"` | `"stream"`)

> Confirmed in session `2026-05-02` (14:11–14:12). Toggled six times alternating 01/02. Write command uses same opcode and encoding (§6.3).

---

### 3.20 Bluetooth Default — `0xB2` ✅

Fires when the user toggles the Bluetooth default (auto-connect) setting.

```
[reportId, 0xB2, state, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0xB2` |
| 2 | State: `0x00` = off, `0x01` = on |

**Decoding:**
```
0x00 → bt_default = "off"
0x01 → bt_default = "on"
```

**State field:** `bt_default` (`"off"` | `"on"`)

> Confirmed `2026-05-02`. Previously recorded as unresponsive (session `2026-05-02` write probe with no visible effect); that probe tested a write on Col01 and checked `0xB0[10]` only — the event fires on Col02. Write command uses same opcode and encoding.

---

### 3.21 EQ Preset Selection — `0x2E` ✅

Fires when the user selects an EQ preset (or cycles through the preset list) in SteelSeries GG.

```
[reportId, 0x2E, preset_index, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x2E` |
| 2 | Preset index (0–18 observed) |

**Decoding:**
```
eq_preset_index = data[2]   // 0–18 observed range
```

**Preset index map (confirmed):**

| Index | Meaning |
|---|---|
| `0x04` | Custom EQ (user-defined band levels) |
| `0x00–0x03`, `0x05–0x18` | Named presets (19 presets; exact names not yet captured) |

**State field:** `eq_preset_index` (`number | null`)

> Confirmed session `2026-05-02` (19:47). User scrolled through the full preset list in GG — values ranged 0x00–0x12 (0–18). The active preset at session start was index `0x04`.
> Write command confirmed: `[0x06, 0x2E, preset_index, 0x00×61]` selects a preset or custom EQ. Index `0x04` = custom EQ. Indices `0x00–0x03` and `0x05–0x18` select named presets. Exact preset name → index mapping not yet captured (needs Wireshark or GG UI correlation).

---

### 3.22 EQ Band Level Change — `0x31` ✅

Fires when the user drags an EQ band slider in the custom EQ editor in SteelSeries GG.

```
[reportId, 0x31, band, level, ...]
```

| Byte | Meaning |
|---|---|
| 0 | Report ID (`0x07`) |
| 1 | Command `0x31` |
| 2 | Band index (1–10; 1=lowest frequency, 10=highest frequency) |
| 3 | Band level (0–40; `0x14`=20=flat/0 dB) |

**Decoding:**
```
eq_band_index = data[2]     // 1–10
eq_band_level = data[3]     // 0–40; 0x14 (20) = flat / 0 dB
db_offset     = data[3] - 20   // negative=cut, positive=boost
```

**State fields:** `eq_bands[1..10]` (array of 10 values, each 0–40)

> Confirmed session `2026-05-02` (19:49). Band 1 (`0x01`) and Band 10 (`0x0A`) were each swept from 0 to 40 and back to flat (0x14=20). Range 0–40 confirmed. Flat value `0x14`=20 consistent with `0x20` query response `data[7–16]`. The band index in this event maps directly to the 10-band EQ array: band 1 = `0x20[7]`, band 10 = `0x20[16]`.
>
> **⚠ `0x31` is an incoming event only — do NOT use as a write command.** Writing `[0x06, 0x31, band, level]` does not set EQ band levels; it switches the device to the flat preset instead. Use `0x33` (§6.5) to write custom EQ band values.

---

## 4. Outgoing Commands (Host → Device)

### 4.1 Return to SteelSeries UI — `0x95` ✅

Restores OLED control to the SteelSeries GG / Sonar application. Called after a custom OLED notification expires or when the OLED service stops.

**Python:** `headset.oled.release()` — also called automatically when used as `with headset.oled:`.

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

**Python:** `headset.oled.draw_image(path_or_pil_image)` / `draw_text(str)` / `play_gif(path)` / `play_animation(frames, fps, loops)` / `draw_raw(bitmap_bytes)`. Implemented in `package/arctis_hid/devices/nova_pro/oled.py`. Requires `pip install 'arctis-hid[oled]'`.

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
| `oled_brightness` | `0x85` | `number \| null` (1–10) |
| `chatmix_game` | `0x45`, `0x20`[20] | `number \| null` (0–100) |
| `chatmix_chat` | `0x45`, `0x20`[21] | `number \| null` (0–100) |
| `transparency_level` | `0xB9`, `0xB0`[8] | `number \| null` (1–10) |
| `gain_level` | `0x27`, `0x20`[4] | `number \| null` (1=low, 2=high) |
| `mic_volume` | `0x37`, `0x20`[17] | `number \| null` (1–10) |
| `dim_screen_timeout` | `0x83` | `number \| null` (0–6; 0=off, 1=1 min … 6=60 min) |
| `home_screen_mode` | `0x89` | `number \| null` (0 or 1) |
| `mic_led_brightness` | `0xBF`, `0xB0`[11] | `number \| null` (1–10) |
| `auto_off_timeout` | `0xC1`, `0xB0`[12] | `number \| null` (0–6; 0=off, 1=1 min … 6=60 min) |
| `wireless_2ghz_mode` | `0xC3`, `0xB0`[13] | `"performance" \| "range" \| null` |
| `bt_auto_mute` | `0xB3`, `0xB0`[3] | `"off" \| "-12dB" \| "on" \| null` |
| `bt_default` | `0xB2` | `"off" \| "on" \| null` |
| `stream_main` | `0x47` | `number \| null` (0–100) |
| `stream_aux` | `0x47` | `number \| null` (0–100) |
| `stream_mic` | `0x47` | `number \| null` (0–100) |
| `audio_output` | `0x43`, `0x20`[19] | `"speaker" \| "stream" \| null` |
| `eq_preset_index` | `0x2E`, `0x20`[6] | `number \| null` (0–18; `0x04`=custom; name mapping TBD) |
| `eq_bands[1..10]` | `0x31`, `0x20`[7–16] | `number[] \| null` (each 0–40; 20=flat/0 dB) |

---

## 6. Query Commands ✅ / 🔬

### 6.1 Confirmed Query Commands (respond on `0xFFC0`)

All queries use: `[0x06, cmdByte, 0x00, ..., 0x00]` (64 bytes). Confirmed in session `2026-05-01`.

#### `0xB0` — Status ✅

Response: `[0x06, 0xB0, ?, ?, conn, bt, headset_bat, dock_bat, 0x08, mic_mute, anc, mic_led, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0xB0` | Command echo |
| 2 | `0x00` | Unknown (always `0x00` in all observed sessions) |
| 3 | `0x00`–`0x02` | **BT auto-mute** — same encoding as `0xB3` event: `0x00`=off, `0x01`=-12 dB, `0x02`=full. Confirmed 2026-05-09 ✅ |
| 4 | `0x01` / `0x04` | **Connectivity mode** — `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active (mirrors `0xB5` data[2]) ✅ |
| 5 | `0x00` / `0x01` | **BT state** — `0x00`=off, `0x01`=BT active (mirrors `0xB5` data[3]) ✅ |
| 6 | `0x00`–`0x08` | **Headset battery** raw (÷ 8 × 100 = %) ✅ |
| 7 | `0x00`–`0x08` | **Dock battery** raw (÷ 8 × 100 = %) ✅ |
| 8 | `0x01`–`0x0A` | **Transparency level** (1–10; only valid when ANC mode = transparency) ✅ |
| 9 | `0x00` / `0x01` | **Mic mute** — `0x00`=unmuted, `0x01`=muted ✅ |
| 10 | `0x00`–`0x02` | **ANC mode** — `0x00`=off, `0x01`=transparency, `0x02`=anc ✅ |
| 11 | `0x01`–`0x0A` | **Mic LED brightness** (1–10; `0x0A`=10=max) ✅ |
| 12 | `0x00`–`0x06` | **Auto off timeout** — same encoding as `0xC1` event: 0=off, 1=1 min, 2=5 min, 3=10 min, 4=15 min, 5=30 min, 6=60 min. Confirmed 2026-05-09. ✅ |
| 13 | `0x00` / `0x01` | **2.4 GHz mode** — `0x00`=performance/speed, `0x01`=extended range ✅ |
| 14–15 | `0x08 0x08` | Constant |

#### `0x20` — Mic / EQ Params ✅

Response: `[0x06, 0x20, ?, vol_raw, gain, 0, eq_preset, eq×10, mic_vol, sidetone, audio_out, game, chat, stream_main, 0, stream_aux, stream_mic, ...]`

| Byte | Value observed | Meaning |
|---|---|---|
| 0 | `0x06` | Report ID |
| 1 | `0x20` | Command echo |
| 2 | `0x01` | Unknown (constant across all sessions) |
| 3 | `0x00`–`0x38` | **Headset volume raw** — same encoding as `0x25` event: `0x38`=0%, `0x00`=100% ✅ |
| 4 | `0x01` / `0x02` | **Gain level** — `0x01`=low, `0x02`=high ✅ |
| 5 | `0x00` | Padding/unknown |
| 6 | `0x00`–`0x12` | **EQ preset index** — same encoding as `0x2E` event/write: `0x04`=custom EQ, `0x00–0x03` and `0x05–0x18`=named presets ✅ |
| 7–16 | 10 bytes | **EQ band values** (0–40, `0x14`=20=flat/0 dB) ✅ |
| 17 | `0x01`–`0x0A` | **Mic volume** (1–10) ✅ |
| 18 | `0x00`–`0x03` | **Sidetone level** (0=off, 1=low, 2=medium, 3=high) ✅ |
| 19 | `0x01` / `0x02` | **Audio output** — `0x01`=speakers, `0x02`=stream (mirrors `0x43` event data[2]) ✅ |
| 20 | `0x00`–`0x64` | **ChatMix game** (0–100) ✅ — mirrors `0x45` event data[2] |
| 21 | `0x00`–`0x64` | **ChatMix chat** (0–100) ✅ — mirrors `0x45` event data[3] |
| 22 | `0x00`–`0x64` | **Stream main volume** (0–100) ✅ — mirrors `0x47` event/write data[2] |
| 23 | `0x00` | Constant (padding) |
| 24 | `0x00`–`0x64` | **Stream aux volume** (0–100) ✅ — mirrors `0x47` event/write data[4] |
| 25 | `0x00`–`0x64` | **Stream mic volume** (0–100) ✅ — mirrors `0x47` event/write data[5] |

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

### 6.3 Confirmed Write Commands ✅

All confirmed working on Nova Pro (PID `0x12E0`, session `2026-05-01/02`).
Write packet: `[0x06, CMD, PARAM, 0x00×61]`. Always follow with `0x09` to persist.

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0x25` | Set headset volume | `[2]` | 0–56 | Same inverted encoding as the event: `raw = round((1 − pct/100) × 56)`; `0x38`=0%, `0x00`=100% ✅ |
| `0x37` | Set mic volume | `[2]` | 1–10 | Also an incoming event (§3.10) ✅ |
| `0x39` | Set sidetone | `[2]` | 0–3 | 0=off, 1=low, 2=medium, 3=high ✅ |
| `0x85` | Set OLED brightness | `[2]` | 1–10 | Also an incoming event (§3.4) ✅ |
| `0xBD` | Set ANC mode | `[2]` | 0–2 | `0x00`=off, `0x01`=transparency, `0x02`=ANC; also the incoming event byte (§3.6) ✅ |
| `0xB9` | Set transparency level | `[2]` | 1–10 | Effective only when ANC mode=transparency; also the incoming event byte (§3.15); verify via visual/event, `0xB0` has no transparency-level field ✅ |
| `0x83` | Set dim screen timeout | `[2]` | 0–6 | `0`=off, `1`=1 min, `2`=5 min, `3`=10 min, `4`=15 min, `5`=30 min, `6`=60 min; also the incoming event byte (§3.11) ✅ |
| `0x89` | Set home screen mode | `[2]` | 0–1 | `0x00`=detailed, `0x01`=simple; also the incoming event byte (§3.12) ✅ |
| `0xBF` | Set mic LED brightness | `[2]` | 1–10 | Also the incoming event byte (§3.13) ✅ |
| `0xC1` | Set auto off timeout | `[2]` | 0–6 | `0`=off, `1`=1 min, `2`=5 min, `3`=10 min, `4`=15 min, `5`=30 min, `6`=60 min; also the incoming event byte (§3.14) ✅ |
| `0x27` | Set gain level | `[2]` | 0–1 | **Write encoding differs from event encoding:** `0x00`=high, `0x01`=low. Incoming event (§3.9) uses `0x01`=low, `0x02`=high ✅ |
| `0x49` | ChatMix enable/disable | `[2]` | 0–1 | `0x00`=disable, `0x01`=enable; `0x45` dial events only fire when enabled (§4.3) ✅ |
| `0xC3` | Set 2.4 GHz mode | `[2]` | 0–1 | `0x00`=performance/speed, `0x01`=extended range; `0xB0[13]` reflects current value; also the incoming event byte (§3.16) ✅ |
| `0xB2` | Set Bluetooth default | `[2]` | 0–1 | `0x00`=off, `0x01`=on; also the incoming event byte (§3.20) ✅ |
| `0xB3` | Set BT auto-mute | `[2]` | 0–2 | `0x00`=off, `0x01`=-12dB, `0x02`=on; also the incoming event byte (§3.17) ✅ |
| `0x43` | Set audio output | `[2]` | 1–2 | `0x01`=speakers, `0x02`=stream; also the incoming event byte (§3.19) ✅ |
| `0x47` | Set output stream volumes | `[2]`=main, `[4]`=aux, `[5]`=mic | 0–100 each | Multi-byte write: `[0x06, 0x47, main, 0x00, aux, mic, 0x00×58]`; mirrors incoming event layout (§3.18) ✅ |
| `0x2E` | Select EQ preset / custom | `[2]` | 0–18 | `0x04`=custom EQ; `0x00–0x03` and `0x05–0x18` = named presets (19 total). Same encoding as event (§3.21) ✅ |
| `0x33` | Set custom EQ band levels | `[2–11]` = 10 band values | 0–40 each | `[0x06, 0x33, b1, b2, ..., b10, 0x00×52]`; 20=flat/0 dB; no profile prefix; switch to custom EQ first (`0x2E` `0x04`) ✅ |
| `0x09` | Save / persist | — | — | Call after any write to commit to flash ✅ |

### 6.4 Candidate Write Commands 🔬

Not yet verified on Nova Pro. Origin: Arctis Nova 7X protocol + HeadsetControl.

| Command | Description | Param byte | Range | Notes |
|---|---|---|---|---|
| `0xA3` | Set idle timeout | `[2]` | 0–90 | Minutes; 0=never sleep |

#### ANC / Transparency Write — ✅ Resolved (2026-05-02)

`0xBD` is confirmed as both the incoming event and the write command for ANC mode.
`0xB9` is confirmed as both the incoming event and the write command for transparency level.
Both are now listed in §6.3.

### 6.5 Candidate EQ Commands 🔬

| Command | Description | Notes |
|---|---|---|
| `0x32` | Query EQ params | Response format unknown; not yet tested on Nova Pro |
| `0xA6` | Query EQ preset name | Profile ID + ASCII name; not yet tested |
| `0xA7` | Set EQ preset name | Profile ID + mode + ASCII name; not yet tested |

> **`0x33` has been confirmed and moved to §6.3.**
>
> **`0x31` write side-effect documented:** writing any `0x31` packet causes the device to switch to the flat preset. Do not use `0x31` as a write command.
