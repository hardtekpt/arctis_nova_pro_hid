# Session Summary — Phase 1 HID Discovery (2026-05-01 / 2026-05-02)

## What this project is

A Python HID API for the **SteelSeries Arctis Nova Pro Wireless** headset.
Goal: full programmatic control over every headset setting via USB HID.

The approach is incremental: discover the HID command map first (Phase 1),
then build the API on top of confirmed knowledge (Phase 2+).

See `agents/MainIdea.md` for the original brief.

---

## Device

| Field | Value |
|---|---|
| VID | `0x1038` (SteelSeries) |
| PID confirmed on bench | `0x12E0` (Arctis Nova Pro Wireless X) |
| Other known PIDs | `0x12CB`, `0x12CD`, `0x12E5`, `0x225D` |
| USB interface | 4 |
| Control collection (Col01) | usage page `0xFFC0` — bidirectional, send queries + read responses |
| Events collection (Col02) | usage page `0xFF00` — read-only, unsolicited device events |
| Packet size | 64 bytes |
| Outgoing report ID | `0x06` |
| Incoming report ID | `0x06` (query responses on Col01) or `0x07` (events on Col02) |

---

## Repository layout

```
src/
  discover.py      # enumerate all HID devices, identify Nova Pro interface paths
  listen.py        # start-up queries + event loop; logs everything to logs/
docs/
  HidCommands.md   # the full protocol reference (keep this authoritative)
logs/              # 38 session logs from 2026-05-01/02 (163435 → 045953)
requirements.txt   # hidapi
agents/
  MainIdea.md      # project brief
  SessionSummary.md  # this file
```

Git branches: `master` → `development` → feature branches.
Rule: auto-merge feature → development; only merge to master when the
user explicitly says so.

---

## Phase 1 status: MOSTLY COMPLETE

### What is fully confirmed

#### Incoming events (device → host, unsolicited)

All arrive on Col02 (`0xFF00`) with report ID `0x07`.

| Command | Meaning | Key bytes | Notes |
|---------|---------|-----------|-------|
| `0x25` | Headset volume | `[2]`=raw (inverted: `pct=(0x38-raw)/56×100`) | 0x38=0%, 0x00=100% |
| `0xB5` | Connectivity change | `[2]`=mode, `[3]`=BT state, `[4]`=wireless | 0x01/0x04 mode; 0x08=wireless active |
| `0xB7` | Battery levels | `[2]`=headset raw, `[3]`=dock raw (÷8×100=%) | `[4]`=0x08 docked, 0x01 removed |
| `0x85` | OLED brightness | `[2]`=level (1–10) | |
| `0x39` | Sidetone | `[2]`=0 off, 1 low, 2 medium, 3 high | |
| `0xBD` | ANC mode | `[2]`=0 off, 1 transparency, 2 anc | |
| `0xBB` | Mic mute | `[2]`=0 unmuted, 1 muted | |
| `0x45` | ChatMix dial | `[2]`=game (0–100), `[3]`=chat (0–100) | center = both 100 |
| `0x27` | Gain level | `[2]`=1 low, 2 high | Full range confirmed: only these 2 values |
| `0x37` | Mic volume | `[2]`=level (1–10) | also an incoming event (not write-only) |
| `0x83` | Dim screen timeout | `[2]`=0 off,1=1min,2=5min,3=10min,4=15min,5=30min,6=60min | |
| `0x89` | Home screen mode | `[2]`=0 detailed, 1 simple | |
| `0xBF` | Mic LED brightness | `[2]`=level (1–10) | |
| `0xC1` | Auto off timeout | `[2]`=0 off,1=1min,2=5min,3=10min,4=15min,5=30min,6=60min | |
| `0xB9` | Transparency level | `[2]`=level (1–10) | Transparency mode only |

#### Query commands (host → device, Col01 `0xFFC0`)

Send `[0x06, cmdByte, 0x00×62]`. Response arrives on same handle.

| Command | Response content |
|---------|-----------------|
| `0xB0` | Status (battery, connectivity, ANC, mic mute) |
| `0x20` | Mic/EQ params (gain, mic vol, sidetone, EQ bands, ChatMix, headset vol) |
| `0x10` | Firmware version (ASCII string) |
| `0x12` | Serial number (ASCII string) |

`0xA0` was tested — no response from this device.

`0x10` (firmware) is also pushed **unsolicited** on Col01 when the headset reconnects wirelessly.

#### `0xB0` response field map (64 bytes)

```
[0x06, 0xB0, 0x00, 0x00, conn, bt, hbat, dbat, 0x08, mute, anc, ?, ?, 0x00, 0x08, 0x08, ...]
  [0]   [1]   [2]   [3]   [4]  [5]  [6]   [7]   [8]   [9]  [10] [11] [12]
```

| Byte | Meaning | Values |
|------|---------|--------|
| [4] | Connectivity mode | `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active |
| [5] | BT state | `0x00`=off, `0x01`=BT active |
| [6] | Headset battery raw | ÷ 8 × 100 = % |
| [7] | Dock battery raw | ÷ 8 × 100 = % |
| [9] | Mic mute | `0x00`=unmuted, `0x01`=muted |
| [10] | ANC mode | `0x00`=off, `0x01`=transparency, `0x02`=anc |
| [11] | **OLED brightness** | 1–10; `0x0A`=10=max ✅ |

#### `0x20` response field map (64 bytes)

```
[0x06, 0x20, ?, vol, gain, 0, 0, eq×10, mic_vol, sidetone, ?, game, chat, ...]
  [0]   [1]  [2] [3]  [4] [5][6] [7-16]  [17]      [18]   [19] [20]  [21]
```

| Byte | Meaning | Values / decode |
|------|---------|-----------------|
| [2] | Unknown | constant `0x01` |
| [3] | Headset volume raw | same encoding as `0x25` event: `pct=(0x38-data[3])/56×100` |
| [4] | Gain level | `0x01`=low, `0x02`=high |
| [7–16] | EQ band values × 10 | 0–40, `0x14`=20=flat/0 dB |
| [17] | Mic volume | 1–10 |
| [18] | Sidetone level | 0=off, 1=low, 2=medium, 3=high |
| [20] | ChatMix game | 0–100 |
| [21] | ChatMix chat | 0–100 |

---

### What is still unknown / needs more work

1. **`0x20` data[2]** — constant `0x01` in all sessions. Meaning unknown. Likely a protocol version byte.
2. **`0xB0` data[12]** — changed from `0x05` to `0x06` across sessions; weak correlation with battery level. Meaning unclear.
3. **`0xB0` data[2–3]** and **`0xB0` data[8]** — constant `0x00` / `0x08`, no hypothesis.
4. **`0x20` data[5–6]**, **data[19]**, **data[22–25]** — padding or unknown, no change observed.
5. **Candidate write commands** — still unverified on Nova Pro:
   - `0x3A` — volume limiter (0/1)
   - `0xA3` — idle timeout (0–90 min)
   - `0xAE` — mute LED brightness (0–3)
   - EQ writes: `0x32`/`0x33`/`0xA6`/`0xA7`
   - `0x49` — ChatMix enable/disable
6. **USB Input selection** — no command observed yet.

---

## Phase 2 next steps

Phase 2 is writing the actual API. Before that, the remaining Phase 1 work is:

### Confirmed write commands (verified on Nova Pro)

```
0x37  mic volume        [0x06, 0x37, level, 0x00×61]   level=1-10  ✅
0x39  sidetone          [0x06, 0x39, level, 0x00×61]   level=0,1,2,3  ✅
0x85  OLED brightness   [0x06, 0x85, level, 0x00×61]   level=1-10  ✅
0xBD  ANC mode          [0x06, 0xBD, mode,  0x00×61]   mode=0(off),1(transparency),2(ANC)  ✅
0xB9  transparency lvl  [0x06, 0xB9, level, 0x00×61]   level=1-10 (transparency mode only)  ✅
0x09  save              [0x06, 0x09, 0x00×62]           call after any write  ✅
```

### Remaining write commands to verify

```
0x3A  vol limiter  [0x06, 0x3A, 0x00|0x01, 0x00×61]
0xA3  idle timeout [0x06, 0xA3, minutes, 0x00×61]   minutes=0-90
0xAE  LED bright   [0x06, 0xAE, level, 0x00×61]     level=0-3
0x49  ChatMix en   [0x06, 0x49, 0x01, 0x00×61]      0=disable, 1=enable
EQ:   0x33 set bands, 0x32 query bands
```

For each: send, query `0x20` or `0xB0`, verify the relevant field changed.

### Then build the API

The API should expose at minimum:
- `get_status()` → battery %, ANC mode, mic mute, connectivity, volume, ChatMix, gain, mic vol, sidetone
- `set_volume(pct)` — if writeable
- `set_mic_volume(level)` — 1–10
- `set_sidetone(level)` — 0–3
- `set_anc_mode(mode)` — off/transparency/anc
- `set_mic_mute(muted)` — bool
- `set_chatmix_enabled(enabled)` — via `0x49`
- `set_eq_bands(bands)` — 10 values

### Technology

Per `agents/MainIdea.md`: Python 3, lightweight backend API framework, simple CLI for testing.

---

## Key implementation notes

- **Query pattern**: write `[0x06, cmd, 0x00×62]` to Col01, read response on same handle. Use `device.set_nonblocking(1)` and poll at ~50 ms intervals.
- **`0x10` noise**: the device spontaneously pushes firmware packets on Col01 during wireless reconnect — filter these out or handle gracefully.
- **`0x09` save**: always send this after writes, otherwise settings may not persist across power cycles (unconfirmed on Nova Pro but standard Nova 7X behavior).
- **ChatMix enable**: `[0x06, 0x49, 0x01, 0x00×61]` enables ChatMix. The ChatMix dial only fires `0x45` events when enabled.
- **EQ bands**: 10 bytes at `0x20` response `[7–16]`. Each value: 0–40, `0x14`=20=0 dB. Write via `0x33` with profile byte `0x00` (2.4 GHz) or `0x01` (Bluetooth).
- **Volume encoding**: inverted scale. `0x38`=0%, `0x00`=100%. Formula: `raw = round((1 - pct/100) * 56)`. Max raw = `0x38` = 56.

---

## How to run the listener

```bash
pip install -r requirements.txt

# queries at startup + event loop
python src/listen.py

# listen only (no writes)
python src/listen.py --no-query
```

Interact with the headset. All packets are decoded and logged to `logs/hid_session_<timestamp>.log`.

---

## Git state at end of session

Branch: `development`  
Last merges:
- `feature/phase1-anc-write-confirm` — ANC/transparency write confirmed ✅
- `feature/phase1-anc-write-probe` — probe_write.py + HidCommands §6.4 candidates
- `feature/phase1-write-confirm-0xb9` — main discoveries batch
- `feature/phase1-bt-state-decode` — 0xB0[5] decoded as on/off in output
- `feature/phase1-0xb9-rename` — 0xB9 clarified as transparency-only

Cumulative changes since `feature/phase1-query-field-mapping-r4`:
- `0xBD` write confirmed: ANC mode (0=off, 1=transparency, 2=ANC), persists ✅
- `0xB9` write confirmed: Transparency level (1–10), transparency mode only, persists ✅
- `0x37` mic volume write confirmed working ✅
- `0x85` OLED brightness write confirmed working; `0xB0[11]` tracks current value ✅
- `src/probe_write.py` added — single write probe + before/after 0xB0 diff tool ✅
- `0xB9` — Transparency Level (1–10), transparency mode only ✅
- `0xB0[11]` — confirmed OLED brightness (1–10) ✅
- `0xB0[5]` — BT state decoded as `on`/`off` in listener output ✅
- `0x89` label order confirmed: 0=detailed, 1=simple ✅
- Gain full range confirmed: exactly 2 discrete levels (1=low, 2=high) ✅
- Write commands 0x37/0x39/0x85/0x09 all confirmed working ✅
- `0xB2` added to unresponsive list
- `docs/TestChecklist.md` created
- `docs/ArctisNovaPro-InterfaceSummary.md` added (by user)
