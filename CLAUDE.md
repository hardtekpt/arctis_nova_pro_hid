## Rules

- Create a separate branch for each feature or implementation step.
- When a feature is completed merge to the development branch automatically.
- Only merge to the main/master branch when I say.
- When merging to master, automatically create a new tag with an incremented version according to the implemented feature (micro, minor, major).

---

## Project

A Python HID API for the **SteelSeries Arctis Nova Pro Wireless** headset (PID `0x12E0`).
Goal: full programmatic control over every headset setting via USB HID.

Phase 1 (complete) — discover the HID command map.
Phase 2 (current) — build the API on top of confirmed knowledge.

Technology: Python 3, lightweight backend API framework, simple CLI for testing.

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
  HidCommands.md    # full protocol reference — authoritative source of truth
  TestChecklist.md  # per-command test rows with pass/fail status
logs/               # HID session logs (gitignored)
agents/
  MainIdea.md       # original project brief
  SessionSummary.md # Phase 1 findings, confirmed commands, key lessons
requirements.txt    # hidapi
```

---

## Device

| Field | Value |
|---|---|
| VID | `0x1038` (SteelSeries) |
| PID on bench | `0x12E0` (Arctis Nova Pro Wireless X) |
| Other PIDs | `0x12CB`, `0x12CD`, `0x12E5`, `0x225D` |
| USB interface | 4 |
| Control collection (Col01) | usage page `0xFFC0` — send commands, read responses |
| Events collection (Col02) | usage page `0xFF00` — read-only unsolicited events |
| Packet size | 64 bytes |
| Report ID (outgoing) | `0x06` |
| Report ID (incoming) | `0x06` (query responses) or `0x07` (events) |

---

## HID protocol — confirmed commands

### Packet format

```
Write / query:  [0x06, CMD, PARAM, 0x00 × 61]   (64 bytes, sent to Col01)
Save:           [0x06, 0x09, 0x00 × 62]          (always send after writes)
```

### Query commands (host → Col01 → response on same handle)

| Command | Returns |
|---------|---------|
| `0xB0` | Status: battery, connectivity, ANC mode, mic mute, OLED brightness |
| `0x20` | Mic/EQ: gain, mic vol, sidetone, 10 EQ bands, ChatMix, headset vol |
| `0x10` | Firmware version (ASCII, null-terminated) |
| `0x12` | Serial number (ASCII, null-terminated) |

`0x10` is also pushed **unsolicited** on Col01 when the headset reconnects wirelessly.

### `0xB0` response field map

| Byte | Meaning | Values |
|------|---------|--------|
| [4] | Connectivity mode | `0x01`=2.4 GHz only, `0x04`=2.4 GHz + BT active |
| [5] | BT state | `0x00`=off, `0x01`=active |
| [6] | Headset battery raw | ÷ 8 × 100 = % |
| [7] | Dock battery raw | ÷ 8 × 100 = % |
| [9] | Mic mute | `0x00`=unmuted, `0x01`=muted |
| [10] | ANC mode | `0x00`=off, `0x01`=transparency, `0x02`=ANC |
| [11] | OLED brightness | 1–10 |

### `0x20` response field map

| Byte | Meaning | Values |
|------|---------|--------|
| [3] | Headset volume raw | inverted: `pct = (0x38 − data[3]) / 56 × 100` |
| [4] | Gain | `0x01`=low, `0x02`=high |
| [7–16] | EQ bands × 10 | 0–40, `0x14`=20=flat/0 dB |
| [17] | Mic volume | 1–10 |
| [18] | Sidetone | 0=off, 1=low, 2=medium, 3=high |
| [20] | ChatMix game | 0–100 |
| [21] | ChatMix chat | 0–100 |

### Write commands (host → Col01, always follow with `0x09`)

| Command | Description | Param | Encoding |
|---------|-------------|-------|----------|
| `0x37` | Set mic volume | 1–10 | |
| `0x39` | Set sidetone | 0–3 | 0=off, 1=low, 2=medium, 3=high |
| `0x85` | Set OLED brightness | 1–10 | |
| `0xBD` | Set ANC mode | 0–2 | 0=off, 1=transparency, 2=ANC |
| `0xB9` | Set transparency level | 1–10 | transparency mode only |
| `0x83` | Set dim screen timeout | 0–6 | 0=off; 1–6 = 1/5/10/15/30/60 min |
| `0x89` | Set home screen mode | 0–1 | 0=detailed, 1=simple |
| `0xBF` | Set mic LED brightness | 1–10 | |
| `0xC1` | Set auto off timeout | 0–6 | 0=off; 1–6 = 1/5/10/15/30/60 min |
| `0x27` | Set gain | 0–1 | **0=high, 1=low** ⚠ inverted vs event/query |
| `0x49` | ChatMix enable | 0–1 | 0=disable, 1=enable |
| `0x09` | Save / persist | — | send after every write |

### Incoming events (device → Col02, report ID `0x07`)

| Command | Meaning | Key bytes |
|---------|---------|-----------|
| `0x25` | Volume | `[2]` raw, inverted: `pct = (0x38 − raw) / 56 × 100` |
| `0xB5` | Connectivity change | `[2]`=mode, `[3]`=BT state, `[4]`=wireless |
| `0xB7` | Battery levels | `[2]`=headset raw, `[3]`=dock raw (÷8×100=%) |
| `0x85` | OLED brightness | `[2]`=level 1–10 |
| `0x39` | Sidetone | `[2]`=0–3 |
| `0xBD` | ANC mode | `[2]`=0 off, 1 transparency, 2 ANC |
| `0xBB` | Mic mute | `[2]`=0 unmuted, 1 muted |
| `0x45` | ChatMix dial | `[2]`=game (0–100), `[3]`=chat (0–100) |
| `0x27` | Gain | `[2]`=1 low, 2 high (different from write encoding) |
| `0x37` | Mic volume | `[2]`=1–10 |
| `0x83` | Dim screen timeout | `[2]`=0–6 |
| `0x89` | Home screen mode | `[2]`=0 detailed, 1 simple |
| `0xBF` | Mic LED brightness | `[2]`=1–10 |
| `0xC1` | Auto off timeout | `[2]`=0–6 |
| `0xB9` | Transparency level | `[2]`=1–10, transparency mode only |

---

## Key implementation notes

- **Open both handles**: Col01 (`0xFFC0`) for queries/writes; Col02 (`0xFF00`) for events. Use `device.set_nonblocking(1)` and poll at ~50 ms.
- **Save after writes**: `0x09` is confirmed required on Nova Pro — settings revert on power cycle without it.
- **`0x27` gain encoding asymmetry**: write uses `0x00`=high / `0x01`=low; incoming event and `0x20` query use `0x01`=low / `0x02`=high. Abstract this in the API.
- **`0x10` noise**: device pushes unsolicited firmware version packets on Col01 when headset wirelessly reconnects — filter by checking `data[1] == 0x10`.
- **ChatMix**: `0x45` events only fire when ChatMix is enabled (`0x49` param `0x01`).
- **Volume write**: no write command for headset volume found — appears hardware-controlled only.
- **EQ bands**: 10 bytes at `0x20[7–16]`, range 0–40, `0x14`=flat. Write via `0x33` with profile `0x00` (2.4 GHz) or `0x01` (BT) — not yet verified on Nova Pro.
- **Volume encoding**: `raw = round((1 − pct/100) × 56)`; `0x38`=0%, `0x00`=100%.

---

## How to run the scripts

```bash
pip install -r requirements.txt

python scripts/listen.py            # queries at startup + event loop
python scripts/listen.py --no-query # listen only

python scripts/probe_write.py --cmd 0xBD --param 0x01   # write probe
python scripts/discover.py          # enumerate HID interfaces
```
