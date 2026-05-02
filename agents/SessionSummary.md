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
scripts/
  discover.py       # enumerate all HID devices, identify Nova Pro interface paths
  listen.py         # start-up queries + event loop; logs everything to logs/
  probe_write.py    # single write probe: sends one packet, diffs 0xB0 before/after
  write_packet.py   # scratch pad used during Phase 1 write testing
api/
  __init__.py       # Phase 2 API implementation (in progress)
docs/
  HidCommands.md    # the full protocol reference (keep this authoritative)
  TestChecklist.md  # per-command test rows with pass/fail status
logs/               # session logs from 2026-05-01/02
requirements.txt    # hidapi
agents/
  MainIdea.md       # project brief
  SessionSummary.md # this file
```

Git branches: `master` → `development` → feature branches.
Rule: auto-merge feature → development; only merge to master when the
user explicitly says so.

---

## Phase 1 status: COMPLETE (EQ and idle timeout still pending)

All practical headset controls are now mapped and verified on PID `0x12E0`.
The two remaining items (`0xA3` idle timeout, EQ write commands) are not
blocking Phase 2 — the API can be built now.

### Key lessons from Phase 1

1. **Event opcode = write opcode.** For every confirmed write command, the
   command byte is the same as the incoming event byte. Sending `[0x06, CMD,
   param, 0x00×61]` to Col01 works whenever Col02 fires that same CMD. This
   pattern held without exception.

2. **`0x27` gain is the one encoding asymmetry.** The write uses `0x00`=high,
   `0x01`=low, while the incoming event and `0x20` query response use `0x01`=low,
   `0x02`=high. Every other command uses the same encoding for both read and write.

3. **`0x3A` volume limiter does not exist on this device.** Nova 7X protocol
   references include it; the Nova Pro Wireless does not have a volume limiter feature.

4. **`0xAE` was a wrong candidate.** Mic LED brightness is `0xBF`, not `0xAE`.
   The Nova 7X reference was incorrect for this device.

5. **`0x09` save is confirmed on Nova Pro.** Settings written without `0x09` do
   not survive a power cycle. Always send save after writes.

6. **`probe_write.py` workflow.** For any unconfirmed write candidate: run
   `python src/probe_write.py --cmd 0xXX --param 0xYY`, observe `[BEFORE]` /
   `[AFTER]` for `0xB0[10]` change (for ANC-type state) or visual/event
   confirmation. This was used to discover `0xBD` in one probe.

---

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
| `0x27` | Gain level | `[2]`=1 low, 2 high | Only 2 discrete values |
| `0x37` | Mic volume | `[2]`=level (1–10) | bidirectional: also a write command |
| `0x83` | Dim screen timeout | `[2]`=0 off, 1–6 (1/5/10/15/30/60 min) | |
| `0x89` | Home screen mode | `[2]`=0 detailed, 1 simple | |
| `0xBF` | Mic LED brightness | `[2]`=level (1–10) | |
| `0xC1` | Auto off timeout | `[2]`=0 off, 1–6 (1/5/10/15/30/60 min) | |
| `0xB9` | Transparency level | `[2]`=level (1–10) | Transparency mode only |
| `0xC3` | 2.4 GHz mode | `[2]`=0 performance/speed, 1 extended range | Also `0xB0[13]` |
| `0xB2` | BT default | `[2]`=0 off, 1 on | Also a write command |
| `0xB3` | BT auto-mute | `[2]`=0 off, 1 -12dB, 2 on | Also a write command |
| `0x47` | Output stream volumes | `[2]`=main (0–100), `[4]`=aux (0–100), `[5]`=mic (0–100) | `[3]`=0x00 constant |
| `0x43` | Audio output selection | `[2]`=1 speaker, 2 stream | Also a write command |

#### Query commands (host → device, Col01 `0xFFC0`)

Send `[0x06, cmdByte, 0x00×62]`. Response arrives on same handle.

| Command | Response content |
|---------|-----------------|
| `0xB0` | Status (battery, connectivity, ANC, mic mute, OLED brightness) |
| `0x20` | Mic/EQ params (gain, mic vol, sidetone, EQ bands, ChatMix, headset vol) |
| `0x10` | Firmware version (ASCII string) |
| `0x12` | Serial number (ASCII string) |

`0xA0` was tested — no response from this device.

`0x10` (firmware) is also pushed **unsolicited** on Col01 when the headset reconnects wirelessly.

#### `0xB0` response field map (64 bytes)

```
[0x06, 0xB0, 0x00, 0x00, conn, bt, hbat, dbat, 0x08, mute, anc, oled, ?, ...]
  [0]   [1]   [2]   [3]   [4]  [5]  [6]   [7]   [8]   [9]  [10]  [11] [12]
```

| Byte | Meaning | Values |
|------|---------|--------|
| [4] | Connectivity mode | `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active |
| [5] | BT state | `0x00`=off, `0x01`=BT active |
| [6] | Headset battery raw | ÷ 8 × 100 = % |
| [7] | Dock battery raw | ÷ 8 × 100 = % |
| [9] | Mic mute | `0x00`=unmuted, `0x01`=muted |
| [10] | ANC mode | `0x00`=off, `0x01`=transparency, `0x02`=anc |
| [11] | OLED brightness | 1–10; `0x0A`=10=max |
| [13] | 2.4 GHz mode | `0x00`=performance/speed, `0x01`=extended range |

#### `0x20` response field map (64 bytes)

```
[0x06, 0x20, ?, vol, gain, 0, 0, eq×10, mic_vol, sidetone, ?, game, chat, ...]
  [0]   [1]  [2] [3]  [4] [5][6] [7-16]  [17]      [18]   [19] [20]  [21]
```

| Byte | Meaning | Values / decode |
|------|---------|-----------------|
| [2] | Unknown | constant `0x01` — likely protocol version |
| [3] | Headset volume raw | same encoding as `0x25` event: `pct=(0x38-data[3])/56×100` |
| [4] | Gain level | `0x01`=low, `0x02`=high |
| [7–16] | EQ band values × 10 | 0–40, `0x14`=20=flat/0 dB |
| [17] | Mic volume | 1–10 |
| [18] | Sidetone level | 0=off, 1=low, 2=medium, 3=high |
| [20] | ChatMix game | 0–100 |
| [21] | ChatMix chat | 0–100 |

#### Write commands (host → device, Col01 `0xFFC0`)

Packet: `[0x06, CMD, PARAM, 0x00×61]` (64 bytes). Always follow with `0x09`.

| Command | Description | Param | Notes |
|---------|-------------|-------|-------|
| `0x25` | Set headset volume | 0–56 raw | Same inverted encoding as event: `raw = round((1−pct/100)×56)`; `0x38`=0%, `0x00`=100% |
| `0x37` | Set mic volume | 1–10 | |
| `0x39` | Set sidetone | 0–3 | 0=off, 1=low, 2=medium, 3=high |
| `0x85` | Set OLED brightness | 1–10 | `0xB0[11]` reflects current value |
| `0xBD` | Set ANC mode | 0–2 | 0=off, 1=transparency, 2=ANC |
| `0xB9` | Set transparency level | 1–10 | Effective in transparency mode only |
| `0x83` | Set dim screen timeout | 0–6 | 0=off, 1–6 = 1/5/10/15/30/60 min |
| `0x89` | Set home screen mode | 0–1 | 0=detailed, 1=simple |
| `0xBF` | Set mic LED brightness | 1–10 | |
| `0xC1` | Set auto off timeout | 0–6 | 0=off, 1–6 = 1/5/10/15/30/60 min |
| `0x27` | Set gain level | 0–1 | **0=high, 1=low** (inverted vs event: 1=low, 2=high) |
| `0x49` | ChatMix enable | 0–1 | 0=disable, 1=enable; `0x45` events only fire when enabled |
| `0xC3` | Set 2.4 GHz mode | 0–1 | 0=performance/speed, 1=extended range; `0xB0[13]` reflects value |
| `0xB2` | Set BT default | 0–1 | 0=off, 1=on |
| `0xB3` | Set BT auto-mute | 0–2 | 0=off, 1=-12dB, 2=on |
| `0x43` | Set audio output | 1–2 | 1=speakers, 2=stream |
| `0x09` | Save / persist | — | Send after every write to commit to flash |

---

### What is still unknown / needs more work

1. **`0x20` data[2]** — constant `0x01` in all sessions. Likely a protocol version byte; safe to ignore.
2. **`0xB0` data[12]** — changed from `0x05` to `0x06` across sessions; weak correlation with battery level. No actionable hypothesis.
3. **`0xB0` data[2–3]** and **`0xB0` data[8]** — constant `0x00` / `0x08`; no hypothesis.
4. **`0x20` data[5–6]**, **data[19]**, **data[22–25]** — appear to be padding; no change observed.
5. **Unverified write commands:**
   - `0xA3` — idle timeout (0–90 min) — not blocking Phase 2
   - EQ: `0x33` set bands, `0x32` query bands, `0xA6`/`0xA7` preset names
6. **USB Input selection** — no command or event observed yet.
7. **Headset volume write** — `0x25` fires as an event but no write command for volume has been found. Volume may be hardware-only.

---

## Phase 2 next steps

Phase 1 is complete enough to build the API. EQ and idle timeout can be added
post-launch once verified.

### API surface (all capabilities now confirmed writable)

| Method | Command | Notes |
|--------|---------|-------|
| `get_status()` | `0xB0` + `0x20` | battery %, ANC, mute, connectivity, vol, gain, mic vol, sidetone, ChatMix, OLED brightness |
| `set_volume(pct)` | `0x25` | inverted raw encoding: `raw = round((1−pct/100)×56)` |
| `set_mic_volume(1–10)` | `0x37` | |
| `set_sidetone(0–3)` | `0x39` | 0=off, 1=low, 2=medium, 3=high |
| `set_oled_brightness(1–10)` | `0x85` | |
| `set_anc_mode(0–2)` | `0xBD` | 0=off, 1=transparency, 2=ANC |
| `set_transparency_level(1–10)` | `0xB9` | call only when ANC mode=transparency |
| `set_gain(0–1)` | `0x27` | **0=high, 1=low** |
| `set_chatmix_enabled(bool)` | `0x49` | |
| `set_dim_screen_timeout(0–6)` | `0x83` | |
| `set_home_screen_mode(0–1)` | `0x89` | |
| `set_mic_led_brightness(1–10)` | `0xBF` | |
| `set_auto_off_timeout(0–6)` | `0xC1` | |
| `set_eq_bands(10 values)` | `0x33` | pending EQ verification |
| `save()` | `0x09` | always call after writes |

### Technology

Per `agents/MainIdea.md`: Python 3, lightweight backend API framework, simple CLI for testing.

---

## Key implementation notes

- **Query pattern**: write `[0x06, cmd, 0x00×62]` to Col01, read response on same handle. Use `device.set_nonblocking(1)` and poll at ~50 ms intervals.
- **`0x10` noise**: the device spontaneously pushes firmware packets on Col01 during wireless reconnect — filter these out or handle gracefully.
- **`0x09` save**: confirmed on Nova Pro — always send after writes, otherwise settings revert on power cycle.
- **Gain encoding asymmetry**: write `0x27` with `0x00`=high, `0x01`=low. The `0x20` query response and incoming `0x27` event use `0x01`=low, `0x02`=high. The API should abstract this internally.
- **ChatMix**: `0x45` dial events only fire when ChatMix is enabled (`0x49` param `0x01`). Enable at startup if you want live dial tracking.
- **EQ bands**: 10 bytes at `0x20` response `[7–16]`. Each value: 0–40, `0x14`=20=0 dB. Write via `0x33` with profile byte `0x00` (2.4 GHz) or `0x01` (Bluetooth).
- **Volume encoding**: inverted scale. `0x38`=0%, `0x00`=100%. Formula: `raw = round((1 - pct/100) * 56)`. Max raw = `0x38` = 56.
- **Volume write**: `0x25` confirmed writable. Same inverted encoding as the event: `raw = round((1 − pct/100) × 56)`; `0x38`=0%, `0x00`=100%.

---

## How to run the tools

```bash
pip install -r requirements.txt

# queries at startup + event loop
python scripts/listen.py

# listen only (no writes)
python scripts/listen.py --no-query

# single write probe (for testing candidates)
python scripts/probe_write.py --cmd 0xBD --param 0x01
```

Interact with the headset. All packets are decoded and logged to `logs/hid_session_<timestamp>.log`.

---

## Git state at end of session

Branch: `development`  
Last merges:
- `feature/phase1-write-corrections` — remove 0x3A/0xAE, confirm 0x49 ChatMix
- `feature/phase1-write-verify-batch2` — confirm 0x83/0x89/0xBF/0xC1/0x27; fix gain encoding
- `feature/phase1-write-verify-batch` — confirm mic vol, OLED, transparency persistence
- `feature/phase1-anc-write-confirm` — 0xBD and 0xB9 write confirmed
- `feature/phase1-anc-write-probe` — probe_write.py added

Cumulative confirmed since start of Phase 1:
- All 15 incoming events decoded ✅
- All 4 query commands confirmed (`0xB0`, `0x20`, `0x10`, `0x12`) ✅
- 12 write commands confirmed (`0x37`, `0x39`, `0x85`, `0xBD`, `0xB9`, `0x83`, `0x89`, `0xBF`, `0xC1`, `0x27`, `0x49`, `0x09`) ✅
- `0x27` gain write encoding asymmetry discovered and documented ✅
- `0x3A` volume limiter confirmed absent on Nova Pro ✅
- `0xAE` corrected to `0xBF` for mic LED brightness ✅
- `0x09` save confirmed working on Nova Pro ✅
- `src/probe_write.py` added — single write probe + before/after 0xB0 diff tool ✅
