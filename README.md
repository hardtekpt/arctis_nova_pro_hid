# Arctis Nova Pro Wireless — Python HID API

Full programmatic control of the **SteelSeries Arctis Nova Pro Wireless** (and X variant) via direct USB HID. No SteelSeries GG required at runtime.

---

## Key ideas

- Talks directly to the USB receiver over HID — zero dependency on GG or any SteelSeries software at runtime.
- Two HID collections on interface 4: **Col01** (`0xFFC0`) for issuing commands and reading query responses; **Col02** (`0xFF00`) for unsolicited device events (button presses, dial movements, state changes).
- All packets are 64 bytes, report ID `0x06`. Every write must be followed by a `0x09` save command or settings revert on power cycle.
- Discovery methodology: run `listen.py` while interacting with the headset to capture events, then confirm write commands with `probe_write.py`.

## Features

- **Read all device state** via two query commands (`0xB0` status, `0x20` mic/EQ)
- **Write every confirmed setting**: headset volume, mic volume, sidetone, OLED brightness, ANC mode, transparency level, gain, mic LED, screen timeouts, home screen mode, auto-off, ChatMix enable, 2.4 GHz wireless mode
- **Live event stream** from Col02: volume wheel, mute button, ANC button, ChatMix dial, battery updates, connectivity changes, Bluetooth state, stream volumes, audio output routing, BT auto-mute
- **Discovery tools**: interactive `0xB0` diff probe and write-probe scripts for mapping unknown commands

---

## Quick start

```bash
pip install -r requirements.txt

# Listen to all device events + run startup queries
python scripts/listen.py

# Probe a write command (diffs all 64 bytes of 0xB0 before/after)
python scripts/probe_write.py --cmd 0xBD --param 0x02   # set ANC mode

# Discover which 0xB0 byte a GG setting change affects
python scripts/probe_b0_diff.py
```

---

## Device identifiers

| Field | Value |
|---|---|
| Vendor ID | `0x1038` (SteelSeries) |
| PID (bench device) | `0x12E0` (Arctis Nova Pro Wireless X) |
| Other known PIDs | `0x12CB`, `0x12CD`, `0x12E5`, `0x225D` |
| USB interface | `4` |
| Control collection | `0xFFC0` (Col01) — bidirectional |
| Events collection | `0xFF00` (Col02) — read-only |
| Packet size | 64 bytes |
| Outgoing report ID | `0x06` |
| Incoming report ID | `0x06` (query response) · `0x07` (event) |

---

## HID command cheatsheet

Legend: **E** = incoming event (Col02) · **Q** = queryable (which response field) · **W** = confirmed writable

### Audio

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0x25` | Headset volume | ✅ | `0x20`[3] | ✅ | 0–56 raw | Inverted: `raw = round((1−pct/100)×56)` · `0x38`=0% · `0x00`=100% |
| `0x37` | Mic volume | ✅ | `0x20`[17] | ✅ | 1–10 | |
| `0x27` | Mic gain | ✅ | `0x20`[4] | ✅ | write: 0–1 | **Write encoding inverted**: `0x00`=high, `0x01`=low · event/query: `0x01`=low, `0x02`=high |
| `0x39` | Sidetone | ✅ | `0x20`[18] | ✅ | 0–3 | `0`=off · `1`=low · `2`=medium · `3`=high |
| `0x45` | ChatMix dial | ✅ | `0x20`[20,21] | — | — | `[2]`=game (0–100) · `[3]`=chat (0–100) · only fires when ChatMix enabled |
| `0x49` | ChatMix enable | — | — | ✅ | 0–1 | `0x00`=disable · `0x01`=enable · must enable to receive `0x45` events |
| `0x47` | Stream volumes | ✅ | `0x20`[22,24,25] | ✅ | multi-byte | `[2]`=main (0–100) · `[3]`=0x00 · `[4]`=aux (0–100) · `[5]`=mic (0–100) |
| `0x43` | Audio output | ✅ | `0x20`[19] | ✅ | 1–2 | `0x01`=speakers · `0x02`=stream |

### Noise control

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0xBD` | ANC mode | ✅ | `0xB0`[10] | ✅ | 0–2 | `0`=off · `1`=transparency · `2`=ANC |
| `0xB9` | Transparency level | ✅ | `0xB0`[8] | ✅ | 1–10 | Only effective when ANC mode = transparency |

### Display & LEDs

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0x85` | OLED brightness | ✅ | `0xB0`[11] | ✅ | 1–10 | |
| `0x89` | Home screen mode | ✅ | — | ✅ | 0–1 | `0`=detailed · `1`=simple |
| `0xBF` | Mic LED brightness | ✅ | — | ✅ | 1–10 | |
| `0x83` | Dim screen timeout | ✅ | — | ✅ | 0–6 | `0`=off · `1`=1 min · `2`=5 min · `3`=10 min · `4`=15 min · `5`=30 min · `6`=60 min |

### Power & connectivity

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0xC1` | Auto-off timeout | ✅ | — | ✅ | 0–6 | `0`=off · `1`=1 min · `2`=5 min · `3`=10 min · `4`=15 min · `5`=30 min · `6`=60 min |
| `0xC3` | 2.4 GHz mode | ✅ | `0xB0`[13] | ✅ | 0–1 | `0`=performance/speed · `1`=extended range · silent write (no Col02 event from GG) |
| `0xB2` | BT default | ✅ | — | ✅ | 0–1 | `0x00`=off · `0x01`=on |
| `0xB3` | BT auto-mute | ✅ | — | ✅ | 0–2 | `0x00`=off · `0x01`=-12dB · `0x02`=on |
| `0xB5` | Connectivity event | ✅ | `0xB0`[4,5] | — | — | `[2]`=mode · `[3]`=BT state · `[4]`=wireless flag |
| `0xB7` | Battery levels | ✅ | `0xB0`[6,7] | — | — | `[2]`=headset raw · `[3]`=dock raw · `÷8×100`=% |
| `0xBB` | Mic mute | ✅ | `0xB0`[9] | — | — | `[2]`=`0x00` unmuted · `0x01` muted · hardware button only |

### Protocol

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0x09` | Save / persist | — | — | ✅ | — | **Always send after any write** — settings revert on power cycle without it |
| `0xB0` | Status query | — | — | Q | — | Returns battery, connectivity, ANC, mute, OLED brightness, 2.4 GHz mode |
| `0x20` | Mic/EQ query | — | — | Q | — | Returns gain, mic vol, sidetone, 10 EQ bands, ChatMix, stream volumes, headset vol |
| `0x10` | Firmware version | — | — | Q | — | ASCII string · also pushed unsolicited on Col01 at wireless reconnect |
| `0x12` | Serial number | — | — | Q | — | ASCII string |
| `0x95` | Return OLED to GG | — | — | ✅ | — | Restores OLED control to SteelSeries GG after custom draw |
| `0x93` | OLED draw | — | — | ✅ | — | Feature report (1024 bytes) · 128×64 bitmap · send left half then right half |

### Candidate / unverified

| Cmd | Name | E | Q | W | Param | Notes |
|-----|------|---|---|---|-------|-------|
| `0xA3` | Idle timeout | — | — | 🔬 | 0–90 | Minutes · 0=never · not yet confirmed on Nova Pro |
| `0x33` | Set EQ bands | — | — | 🔬 | — | Profile `0x00`=2.4 GHz · `0x01`=BT · 10 band values 0–40 |
| `0x32` | Query EQ bands | — | — | 🔬 | — | Returns profile ID + 10 band values |

---

## `0xB0` status response — field map

```
[0x06, 0xB0, 0x00, 0x00, conn, bt, hbat, dbat, trans, mute, anc, oled, 0x00, mode2g, 0x08, 0x08, ...]
  [0]   [1]   [2]   [3]   [4]  [5]  [6]   [7]   [8]   [9]  [10]  [11]  [12]  [13]   [14]  [15]
```

| Byte | Field | Values |
|------|-------|--------|
| [4] | Connectivity mode | `0x01`=2.4 GHz only · `0x04`=2.4 GHz + BT active |
| [5] | BT state | `0x00`=off · `0x01`=BT active |
| [6] | Headset battery raw | `÷ 8 × 100` = % |
| [7] | Dock battery raw | `÷ 8 × 100` = % |
| [8] | Transparency level | 1–10 (only valid when ANC = transparency) |
| [9] | Mic mute | `0x00`=unmuted · `0x01`=muted |
| [10] | ANC mode | `0x00`=off · `0x01`=transparency · `0x02`=ANC |
| [11] | OLED brightness | 1–10 |
| [13] | 2.4 GHz mode | `0x00`=performance · `0x01`=extended range |

## `0x20` mic/EQ response — field map

```
[0x06, 0x20, ?, vol_raw, gain, 0, 0, eq×10, mic_vol, sidetone, audio, game, chat, stream_main, 0, stream_aux, stream_mic, ...]
  [0]   [1]  [2]  [3]    [4]   [5][6] [7-16]   [17]      [18]    [19]  [20]  [21]    [22]      [23] [24]        [25]
```

| Byte | Field | Values |
|------|-------|--------|
| [3] | Headset volume raw | inverted: `pct = (0x38 − data[3]) / 56 × 100` |
| [4] | Gain | `0x01`=low · `0x02`=high |
| [7–16] | EQ bands × 10 | 0–40 each · `0x14`=20=flat/0 dB |
| [17] | Mic volume | 1–10 |
| [18] | Sidetone | `0`=off · `1`=low · `2`=medium · `3`=high |
| [19] | Audio output | `1`=speakers · `2`=stream |
| [20] | ChatMix game | 0–100 |
| [21] | ChatMix chat | 0–100 |
| [22] | Stream main volume | 0–100 |
| [23] | (padding) | `0x00` |
| [24] | Stream aux volume | 0–100 |
| [25] | Stream mic volume | 0–100 |

---

## Implementation notes

- Poll both handles at ~50 ms with `device.set_nonblocking(1)`.
- Filter `data[1] == 0x10` on Col01 to discard unsolicited firmware noise during wireless reconnect.
- `0x27` gain has an encoding asymmetry: write `0x00`=high/`0x01`=low; event and query use `0x01`=low/`0x02`=high.
- `0x45` ChatMix dial events only fire after sending `0x49` with param `0x01`.
- `0xC3` (2.4 GHz mode) does not fire a Col02 event when changed — it is a silent write. Read current value from `0xB0[13]`.
