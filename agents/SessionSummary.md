# Session Summary — HID Discovery (Phase 1 + Phase 2 discovery sessions)

Sessions: `2026-05-01` / `2026-05-02`

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
  discover.py           # enumerate all HID devices, identify Nova Pro interface paths
  listen.py             # start-up queries + event loop; logs everything to logs/ (IF4 only)
  monitor_all.py        # open EVERY device interface simultaneously — find what GG uses
  probe_write.py        # single write probe: sends one packet, diffs ALL 64 0xB0 bytes before/after
  probe_b0_diff.py      # interactive before/after 0xB0 full-dump diff (toggle GG setting → see which byte changes)
  probe_full_diff.py    # dual 0xB0 + 0x20 before/after diff (catches unmapped bytes in both responses)
  probe_query_scan.py   # scan all 256 opcodes as potential query commands; finds undiscovered responses
  find_usb_bus.py       # identify which Wireshark USBPcap interface to use for GG traffic capture
  parse_gg_capture.py   # decode a Wireshark .json/.pcapng capture → shows GG's host→device commands
api/
  __init__.py        # Phase 2 API implementation (in progress)
docs/
  HidCommands.md     # the full protocol reference (keep this authoritative)
  TestChecklist.md   # per-command test rows with pass/fail status
logs/                # session logs (gitignored)
requirements.txt     # hidapi
agents/
  MainIdea.md        # project brief
  SessionSummary.md  # this file
```

Git branches: `master` → `development` → feature branches.
Rule: auto-merge feature → development; only merge to master when the
user explicitly says so.

---

## Discovery status: Phase 1 COMPLETE + Phase 2 additional commands confirmed

Phase 1 mapped the full core command set (2026-05-01).
Phase 2 discovery sessions (2026-05-02) added 6 more commands and expanded `0xB0` field knowledge.
Phase 2 session 3 (2026-05-02 evening) confirmed two new EQ events (`0x2E`, `0x31`), the `0x2E` write, and the `0x33` custom EQ band write.
The full EQ command set is now confirmed. Only `0xA3` (idle timeout) and EQ preset name mapping remain unverified.

---

## Key lessons

1. **Event opcode = write opcode.** For every confirmed write command, the
   command byte is the same as the incoming event byte. Sending `[0x06, CMD,
   param, 0x00×61]` to Col01 works whenever Col02 fires that same CMD. This
   pattern held without exception across all sessions.

2. **`0x27` gain is the only encoding asymmetry found so far.** The write uses
   `0x00`=high / `0x01`=low, while the event and `0x20` query use `0x01`=low /
   `0x02`=high. All other commands use identical encoding for both event and write.

3. **Some writes are silent — no Col02 event fires.** `0xC3` (2.4 GHz mode) is
   confirmed writable but produces no event on Col02 when changed from GG. Its
   current value is readable from `0xB0[13]`. Other settings changed silently
   from GG may follow the same pattern. The `probe_b0_diff.py` tool was built
   specifically to detect these.

4. **`probe_write.py` must watch ALL 64 bytes of `0xB0`, not just [10].** The
   original probe only diffed `0xB0[10]` (ANC mode), which caused `0xB2`
   (BT default) to be incorrectly logged as "no visible effect" — the effect was
   on Col02, not in `0xB0`. The tool now prints the full 64-byte diff and all
   Col02 events fired during the probe window.

5. **Event value order must be verified by probing writes, not assumed from log
   sequence.** `0xB3` (BT auto-mute) was initially decoded from a log as
   `0x01`=on, `0x02`=-12dB. Write testing confirmed the correct order is
   `0x01`=-12dB, `0x02`=on. Trust confirmed write values over inferred event mapping.

6. **`0xB0` contains more queryable state than initially mapped.** Byte `[13]`
   encodes 2.4 GHz mode. Running `probe_b0_diff.py` while changing settings in
   GG is the fastest way to find which byte a new setting occupies.

7. **`0x09` save is confirmed required on Nova Pro.** Settings written without
   `0x09` do not survive a power cycle. Always send save after writes.

8. **`0x3A` volume limiter does not exist on this device.** Nova 7X protocol
   references include it; the Nova Pro Wireless does not.

9. **`0xAE` was a wrong candidate.** Mic LED brightness is `0xBF`, not `0xAE`.
   The Nova 7X reference was incorrect for this device.

10. **`0x31` EQ band events fire per-band, not per-commit — and `0x31` must never be used as a write command.** Every drag movement of a band slider fires a continuous stream of `0x31` events with `[2]`=band index (1–10) and `[3]`=current level (0–40). This is live streaming, not a final-value event. The band index aligns 1:1 with `0x20[7–16]` (band 1 = `0x20[7]`, band 10 = `0x20[16]`). Writing `0x31` does not set band levels — it switches the device to the flat preset instead. Use `0x33` for EQ writes.

11. **`0x2E` is the EQ preset selector — confirmed as both event and write command.** Fires as the user scrolls through preset options in GG. `0x04` = custom EQ. `0x00–0x03` and `0x05–0x18` = 19 named presets. Write: `[0x06, 0x2E, index, 0x00×61]`. Index → preset name mapping still unknown.

12. **GG-initiated changes are invisible to listen.py.** Toggling settings in
    SteelSeries GG produces no traffic on Col01 (0xFFC0) or Col02 (0xFF00) as
    seen by listen.py. The same setting changed on the physical base station
    DOES fire a Col02 event. This means either (a) GG uses a different HID
    interface that listen.py never opens, or (b) GG writes to Col01 but the
    device fires no Col02 event for software-initiated changes (only hardware
    actions trigger Col02 events). Use `monitor_all.py` to distinguish between
    these cases — it opens every interface the device exposes.

---

## What is confirmed

### Incoming events (device → host, unsolicited)

All arrive on Col02 (`0xFF00`) with report ID `0x07`.

| Command | Meaning | Key bytes | Notes |
|---------|---------|-----------|-------|
| `0x25` | Headset volume | `[2]`=raw (inverted: `pct=(0x38-raw)/56×100`) | 0x38=0%, 0x00=100% |
| `0xB5` | Connectivity change | `[2]`=mode, `[3]`=BT state, `[4]`=wireless | 0x01/0x04 mode; 0x08=wireless active |
| `0xB7` | Battery levels | `[2]`=headset raw, `[3]`=dock raw (÷8×100=%) | `[4]`=0x08 docked, 0x01 removed |
| `0x85` | OLED brightness | `[2]`=level (1–10) | |
| `0x39` | Sidetone | `[2]`=0 off, 1 low, 2 medium, 3 high | |
| `0xBD` | ANC mode | `[2]`=0 off, 1 transparency, 2 ANC | |
| `0xBB` | Mic mute | `[2]`=0 unmuted, 1 muted | Hardware button only |
| `0x45` | ChatMix dial | `[2]`=game (0–100), `[3]`=chat (0–100) | Only fires when ChatMix enabled (`0x49`) |
| `0x27` | Gain level | `[2]`=1 low, 2 high | Only 2 discrete values |
| `0x37` | Mic volume | `[2]`=level (1–10) | Also a write command |
| `0x83` | Dim screen timeout | `[2]`=0 off, 1–6 (1/5/10/15/30/60 min) | |
| `0x89` | Home screen mode | `[2]`=0 detailed, 1 simple | |
| `0xBF` | Mic LED brightness | `[2]`=level (1–10) | |
| `0xC1` | Auto off timeout | `[2]`=0 off, 1–6 (1/5/10/15/30/60 min) | |
| `0xB9` | Transparency level | `[2]`=level (1–10) | Transparency mode only |
| `0xC3` | 2.4 GHz mode | `[2]`=0 performance/speed, 1 extended range | Also `0xB0[13]`; silent from GG (no Col02 event) |
| `0xB2` | BT default | `[2]`=0 off, 1 on | Also a write command |
| `0xB3` | BT auto-mute | `[2]`=0 off, 1 -12dB, 2 on | Also a write command |
| `0x47` | Output stream volumes | `[2]`=main (0–100), `[4]`=aux (0–100), `[5]`=mic (0–100) | `[3]`=0x00 constant; event-only |
| `0x43` | Audio output selection | `[2]`=1 speakers, 2 stream | Also a write command |
| `0x2E` | EQ preset selection | `[2]`=preset index (`0x04`=custom, `0x00–0x03`+`0x05–0x18`=named presets) | Also a write command ✅ |
| `0x31` | EQ band level change | `[2]`=band (1–10), `[3]`=level (0–40, `0x14`=flat/0 dB) | **Event only — do not write** (write switches to flat preset) |

### Query commands (host → device, Col01 `0xFFC0`)

Send `[0x06, cmdByte, 0x00×62]`. Response arrives on same handle.

| Command | Response content |
|---------|-----------------|
| `0xB0` | Status (battery, connectivity, ANC, mic mute, OLED brightness, 2.4 GHz mode) |
| `0x20` | Mic/EQ params (gain, mic vol, sidetone, EQ bands, ChatMix, headset vol) |
| `0x10` | Firmware version (ASCII string) |
| `0x12` | Serial number (ASCII string) |

`0xA0` was tested — no response from this device.

`0x10` (firmware) is also pushed **unsolicited** on Col01 when the headset reconnects wirelessly.

### `0xB0` response field map (64 bytes)

```
[0x06, 0xB0, 0x00, 0x00, conn, bt, hbat, dbat, 0x08, mute, anc, oled, 0x00, mode2g, 0x08, 0x08, ...]
  [0]   [1]   [2]   [3]   [4]  [5]  [6]   [7]   [8]   [9]  [10]  [11]  [12]  [13]   [14]  [15]
```

| Byte | Meaning | Values |
|------|---------|--------|
| [4] | Connectivity mode | `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active |
| [5] | BT state | `0x00`=off, `0x01`=BT active |
| [6] | Headset battery raw | ÷ 8 × 100 = % |
| [7] | Dock battery raw | ÷ 8 × 100 = % |
| [9] | Mic mute | `0x00`=unmuted, `0x01`=muted |
| [10] | ANC mode | `0x00`=off, `0x01`=transparency, `0x02`=ANC |
| [11] | OLED brightness | 1–10; `0x0A`=10=max |
| [13] | 2.4 GHz mode | `0x00`=performance/speed, `0x01`=extended range |

### `0x20` response field map (64 bytes)

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

### Write commands (host → device, Col01 `0xFFC0`)

Packet: `[0x06, CMD, PARAM, 0x00×61]` (64 bytes). Always follow with `0x09`.

| Command | Description | Param | Notes |
|---------|-------------|-------|-------|
| `0x25` | Set headset volume | 0–56 raw | Inverted: `raw = round((1−pct/100)×56)`; `0x38`=0%, `0x00`=100% |
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
| `0xC3` | Set 2.4 GHz mode | 0–1 | 0=performance/speed, 1=extended range; `0xB0[13]` reflects value; silent (no Col02 event) |
| `0xB2` | Set BT default | 0–1 | 0=off, 1=on |
| `0xB3` | Set BT auto-mute | 0–2 | 0=off, 1=-12dB, 2=on |
| `0x43` | Set audio output | 1–2 | 1=speakers, 2=stream |
| `0x09` | Save / persist | — | Send after every write to commit to flash |

---

## What is still unknown / needs more work

1. **`0x20` data[2]** — constant `0x01` in all sessions. Likely a protocol version byte; safe to ignore.
2. **`0xB0` data[12]** — changed from `0x05` to `0x06` across sessions; weak correlation with battery level. No actionable hypothesis.
3. **`0xB0` data[2–3]** and **`0xB0` data[8]** — constant `0x00` / `0x08`; no hypothesis.
4. **`0x20` data[5–6]**, **data[19]**, **data[22–25]** — appear to be padding; no change observed.
5. **Unverified write commands:**
   - `0xA3` — idle timeout (0–90 min) — not blocking Phase 2
6. **`0x47` stream volumes** — event-only so far; write command unconfirmed.
7. **Other `0xB0` bytes** — `probe_b0_diff.py` has only been run for 2.4 GHz mode so far. Other settings changed silently from GG may be stored in unmapped bytes.
8. **Query commands for 7 settings** — BT default (`0xB2`), BT auto-mute (`0xB3`), audio output (`0x43`), dim screen (`0x83`), home screen (`0x89`), mic LED brightness (`0xBF`), auto off (`0xC1`) have no known query command. GG shows their current values at startup, so it must read them somehow. Discovery in progress — see `probe_full_diff.py`, `probe_query_scan.py`, and `monitor_all.py`.
9. **GG communication interface unknown** — when settings are changed via GG software, NO traffic appears in `listen.py` (which only monitors IF4 / 0xFFC0 + 0xFF00). When the same settings are changed via the physical base station controls, events DO appear on Col02. Two hypotheses: (a) GG uses a different HID interface (not IF4), or (b) GG writes to Col01 are silent — no Col02 event fires for software-initiated changes, only for hardware-initiated ones. Run `monitor_all.py` while toggling GG settings to determine which interface (if any) carries GG traffic.

---

## Phase 2 API surface

| Method | Command | Notes |
|--------|---------|-------|
| `get_status()` | `0xB0` + `0x20` | battery %, ANC, mute, connectivity, vol, gain, mic vol, sidetone, ChatMix, OLED brightness, 2.4 GHz mode |
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
| `set_24ghz_mode(0–1)` | `0xC3` | 0=performance, 1=extended range |
| `set_bt_default(bool)` | `0xB2` | |
| `set_bt_auto_mute(0–2)` | `0xB3` | 0=off, 1=-12dB, 2=on |
| `set_audio_output(1–2)` | `0x43` | 1=speakers, 2=stream |
| `set_eq_preset(0–18)` | `0x2E` | `0x04`=custom; `0x00–0x03`+`0x05–0x18`=named presets |
| `set_eq_bands(10 values)` | `0x33` | call after `set_eq_preset(0x04)`; values 0–40, 20=flat |
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
- **Volume encoding**: inverted scale. `0x38`=0%, `0x00`=100%. Formula: `raw = round((1 - pct/100) * 56)`.
- **Silent writes**: some settings (confirmed: `0xC3`) produce no Col02 event and no Col01 response when written. The only way to verify a silent write worked is to re-query `0xB0` and check the relevant byte. Use `probe_b0_diff.py` to identify which byte a new silent setting occupies.
- **Probe pitfall**: early probes only checked `0xB0[10]` (ANC byte) for changes. Always diff all 64 bytes and also drain Col02 events during the probe window — a write may produce an event on Col02 without touching `0xB0` at all.

---

## How to run the tools

```bash
pip install -r requirements.txt

# queries at startup + event loop (IF4 only: 0xFFC0 + 0xFF00)
python scripts/listen.py

# listen only (no writes)
python scripts/listen.py --no-query

# open ALL device interfaces simultaneously — use to find which interface GG uses
python scripts/monitor_all.py

# single write probe — diffs ALL 64 bytes of 0xB0 before/after
python scripts/probe_write.py --cmd 0xBD --param 0x01

# interactive before/after 0xB0 + 0x20 dual diff (for finding unmapped state bytes)
python scripts/probe_full_diff.py

# interactive before/after 0xB0-only diff (original single-response tool)
python scripts/probe_b0_diff.py

# scan all 256 opcodes as potential query commands (~31 s)
python scripts/probe_query_scan.py

# --- USB sniffing (for discovering GG's host→device query commands) ---

# find which Wireshark USBPcap interface corresponds to the headset's USB bus
python scripts/find_usb_bus.py

# decode a Wireshark JSON export or pcapng file of GG traffic
python scripts/parse_gg_capture.py gg_capture.json
python scripts/parse_gg_capture.py gg_capture.json --out-only   # GG→device only
python scripts/parse_gg_capture.py gg_capture.pcapng             # needs: pip install pyshark

# full capture procedure: see docs/WiresharkCaptureGuide.md
```

Interact with the headset. All packets are decoded and logged to `logs/hid_session_<timestamp>.log`.

---

## Git state

Branch: `development`

Cumulative confirmed across all sessions:
- All 20 incoming events decoded ✅
- All 4 query commands confirmed (`0xB0`, `0x20`, `0x10`, `0x12`) ✅
- 19 write commands confirmed (`0x25`, `0x37`, `0x39`, `0x85`, `0xBD`, `0xB9`, `0x83`, `0x89`, `0xBF`, `0xC1`, `0x27`, `0x49`, `0xC3`, `0xB2`, `0xB3`, `0x43`, `0x09`, `0x2E`, `0x33`) ✅
- `0xB0[13]` confirmed as 2.4 GHz mode state field ✅
- `probe_b0_diff.py` added — full 64-byte interactive diff tool ✅
- `probe_write.py` upgraded — now diffs all 64 bytes, not just `[10]` ✅
- `0x27` gain write encoding asymmetry confirmed and abstracted ✅
- `0xC3` silent-write discovery methodology established ✅
- `0x3A` volume limiter confirmed absent on Nova Pro ✅
- `0xAE` corrected to `0xBF` for mic LED brightness ✅
- `monitor_all.py` added — opens every device interface to identify GG's communication path ✅
- `probe_full_diff.py` added — dual 0xB0 + 0x20 diff tool for unmapped byte detection ✅
- `probe_query_scan.py` added — full opcode scanner for undiscovered query commands ✅
- **Root cause confirmed**: `hidapi` only sees device→host (Interrupt IN) traffic. GG's host→device writes (Interrupt OUT) are invisible at the Python HID level — fundamental OS limitation ✅
- `find_usb_bus.py` added — identifies the correct Wireshark USBPcap interface for the headset ✅
- `parse_gg_capture.py` added — decodes Wireshark JSON/pcapng capture, flags unknown GG commands ✅
- `docs/WiresharkCaptureGuide.md` added — full step-by-step USB sniffing guide ✅
- **Open issue**: USB sniffing capture not yet performed; query commands for 7 settings still unknown ⏳
- `0x2E` (EQ preset selection) confirmed as incoming event and write command ✅; `0x04`=custom, `0x00–0x03`+`0x05–0x18`=named presets ✅
- `0x31` (EQ band level change) confirmed as incoming event; **write causes flat-preset switch — event-only** ✅
- `listen.py` updated to decode `0x2E` and `0x31` ✅
- EQ preset name → index mapping still unknown ⏳
- `0x33` (set custom EQ band levels) confirmed ✅ — `[0x06, 0x33, b1..b10, 0x00×52]`; 10 band values at bytes [2–11], no profile prefix, 20=flat
