# Session Summary — HID Discovery + API Build

Sessions: `2026-05-01` / `2026-05-02` (Phase 1 discovery) / `2026-05-03` (Phase 2 API build + Phase 3 OLED) / `2026-05-09` (0xB0 full decode + 0x80 discovery)

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
  scripts/              # Phase 1 discovery tools (not part of the package)
    discover.py         # enumerate all HID devices, identify Nova Pro interface paths
    listen.py           # start-up queries + event loop; logs everything to logs/
    monitor_all.py      # open EVERY device interface simultaneously — find what GG uses
    probe_write.py      # single write probe: diffs ALL 64 0xB0 bytes before/after a write
    probe_full_diff.py  # interactive before/after diff of BOTH 0xB0 + 0x20 responses
    probe_query_scan.py # scan all 256 opcodes as potential query commands
    find_usb_bus.py     # identify which Wireshark USBPcap interface to use
    parse_gg_capture.py # decode a Wireshark .json/.pcapng capture of GG traffic
    test_cli.py         # unified test CLI covering TestChecklist.md
  api/
    __init__.py         # original stub — superseded by src/package/
  package/              # ← PRIMARY: standalone pip-installable package
    arctis_hid/
      __init__.py       # public surface: discover, enums, models, events
      discovery.py      # discover() → AbstractHeadset
      exceptions.py     # DeviceError hierarchy
      core/
        transport.py    # HidTransport: raw HID I/O (interrupt + feature reports)
        dispatcher.py   # EventDispatcher: on/off/emit by event class name
        types.py        # shared enums: AncMode, GainLevel, SidetoneLevel, …
      devices/
        base.py         # AbstractHeadset + AbstractOled ABCs
        nova_pro/
          constants.py  # all CMD_* bytes, field indices, OLED constants
          codec.py      # all byte-level encode/decode (isolated from API)
          models.py     # StatusData, MicEqData, 22 typed event dataclasses
          headset.py    # ArctisNovaProWireless(AbstractHeadset)
          oled.py       # ArctisNovaProOled — Phase 3 complete
    examples/
      listen_events.py  # event/callback mode demo
      query_and_write.py# command mode demo
      oled_demo.py      # OLED brightness/text/image/animation/gif demo (requires Pillow)
    pyproject.toml
    README.md
    DEVELOPER.md
    DOCUMENTATION.md    # complete API reference (auto-updated after any package code change)
docs/
  HidCommands.md        # full protocol reference incl. interface layout — authoritative source of truth
  TestChecklist.md      # per-command test rows with pass/fail status
  Scripts.md            # purpose and usage of every discovery script
  GgoledReference.md    # OLED protocol takeaways from ggoled Rust reference implementation
logs/                   # session logs (gitignored)
requirements.txt        # hidapi (scripts only; package has its own pyproject.toml)
agents/
  MainIdea.md           # project brief
  SessionSummary.md     # this file
```

Git branches: `master` → `development` → feature branches.
Rule: auto-merge feature → development; only merge to master when the user explicitly says so.

---

## Phase status

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1 | ✅ Complete | Full protocol map confirmed (2026-05-01 / 2026-05-02) |
| Phase 2 — Core API | ✅ Complete | `package/arctis_hid` built and merged (2026-05-03) |
| Phase 3 — OLED draw | ✅ Complete | Protocol confirmed via ggoled; `ArctisNovaProOled` built and merged (2026-05-03) |

---

## What is confirmed (protocol)

### Incoming events (device → host, Col02, report ID `0x07`)

| Command | Meaning | Key bytes | Notes |
|---------|---------|-----------|-------|
| `0x25` | Headset volume | `[2]`=raw (inverted: `pct=(0x38-raw)/56×100`) | |
| `0xB5` | Connectivity change | `[2]`=mode, `[3]`=BT state, `[4]`=wireless | |
| `0xB7` | Battery levels | `[2]`=headset raw, `[3]`=dock raw (÷8×100=%) | |
| `0x85` | OLED brightness | `[2]`=level (1–10) | |
| `0x39` | Sidetone | `[2]`=0–3 | |
| `0xBD` | ANC mode | `[2]`=0 off, 1 transparency, 2 ANC | |
| `0xBB` | Mic mute | `[2]`=0 unmuted, 1 muted | Hardware button only |
| `0x45` | ChatMix dial | `[2]`=game (0–100), `[3]`=chat (0–100) | Only fires when ChatMix enabled (`0x49`) |
| `0x27` | Gain level | `[2]`=1 low, 2 high | Inverted vs write encoding |
| `0x37` | Mic volume | `[2]`=level (1–10) | |
| `0x83` | Dim screen timeout | `[2]`=0–6 | |
| `0x89` | Home screen mode | `[2]`=0 detailed, 1 simple | |
| `0xBF` | Mic LED brightness | `[2]`=level (1–10) | |
| `0xC1` | Auto off timeout | `[2]`=0–6 | |
| `0xB9` | Transparency level | `[2]`=level (1–10) | Transparency mode only |
| `0xC3` | 2.4 GHz mode | `[2]`=0 performance, 1 extended | Silent from GG |
| `0xB2` | BT default | `[2]`=0 off, 1 on | |
| `0xB3` | BT auto-mute | `[2]`=0 off, 1 -12dB, 2 on | |
| `0x47` | Output stream volumes | `[2]`=main, `[4]`=aux, `[5]`=mic (0–100) | Event-only |
| `0x43` | Audio output selection | `[2]`=1 speakers, 2 stream | |
| `0x2E` | EQ preset selection | `[2]`=index; `0x04`=custom, `0x00–0x03`+`0x05–0x18`=named | Also write |
| `0x31` | EQ band level change | `[2]`=band (1–10), `[3]`=level (0–40) | **Event only** — writing causes flat preset |

### Query commands (host → Col01)

| Command | Response content |
|---------|-----------------|
| `0xB0` | Status (battery, connectivity, ANC, mic mute, transparency level, mic LED brightness, BT default `[2]`, BT auto-mute `[3]`, auto off timeout `[12]`, 2.4 GHz mode) |
| `0x20` | Mic/EQ params (gain, mic vol, sidetone, EQ bands, ChatMix, stream volumes, headset vol, audio output) |
| `0x10` | Firmware version (ASCII; also pushed unsolicited on wireless reconnect) |
| `0x12` | Serial number (ASCII) |
| `0x80` | Base-station display: dim screen timeout `[2]`, OLED brightness `[3]`, home screen mode `[5]`. Confirmed 2026-05-09. |

### Write commands (always follow with `0x09`)

| Command | Description | Param |
|---------|-------------|-------|
| `0x25` | Headset volume | 0–56 raw (inverted) |
| `0x37` | Mic volume | 1–10 |
| `0x39` | Sidetone | 0–3 |
| `0x85` | OLED brightness | 1–10 |
| `0xBD` | ANC mode | 0–2 |
| `0xB9` | Transparency level | 1–10 |
| `0x83` | Dim screen timeout | 0–6 |
| `0x89` | Home screen mode | 0–1 |
| `0xBF` | Mic LED brightness | 1–10 |
| `0xC1` | Auto off timeout | 0–6 |
| `0x27` | Gain | 0=high, 1=low (**inverted** vs event/query) |
| `0x49` | ChatMix enable | 0–1 |
| `0xC3` | 2.4 GHz mode | 0–1 (silent — no Col02 event) |
| `0xB2` | BT default | 0–1 |
| `0xB3` | BT auto-mute | 0–2 |
| `0x43` | Audio output | 1–2 |
| `0x47` | Stream volumes | multi-byte: `[main, 0x00, aux, mic]` |
| `0x2E` | EQ preset select | 0–24 (0x04=custom) |
| `0x33` | Custom EQ bands | 10 bytes at [2–11], 0–40, 20=flat |
| `0x09` | Save / persist | — always send after writes |

### OLED commands (confirmed, implemented in `oled.py`)

| Command | Type | Description |
|---------|------|-------------|
| `0x93` | HID feature report (1024 bytes × 2) | Draw custom frame — left half (x=0) then right half (x=64) |
| `0x95` | Interrupt write | Return OLED control to GG / Sonar |

---

## Phase 1 key lessons

1. **Event opcode = write opcode** — without exception across all confirmed commands.
2. **`0x27` gain is the only encoding asymmetry found** — write `0x00`=high, but event/query use `0x02`=high.
3. **Some writes are silent** — `0xC3` produces no Col02 event; verify via re-querying `0xB0[13]`.
4. **Always diff all 64 bytes of `0xB0`** in probes, not just `[10]`. Early probes missed `0xB2`.
5. **Trust confirmed write values over inferred event mapping.** `0xB3` was initially decoded wrong from log sequence.
6. **`0x09` save is confirmed required** on Nova Pro — settings revert on power cycle without it.
7. **`0x31` write side-effect**: writing `0x31` switches to flat preset, not setting band levels. Use `0x33`.
8. **`hidapi` only sees Interrupt IN** — GG's Interrupt OUT writes are invisible at the Python layer. Physical button/dial changes fire Col02 events; GG software changes do not.

---

## Phase 3 key lessons (2026-05-03)

1. **Confirmed the full OLED protocol from ggoled source code.** The [ggoled](https://github.com/JerwuQu/ggoled) project (Rust) directly implements the same HID commands for PID `0x12E0`. This eliminated the need for a Wireshark capture: screen dimensions are 128×64 (not the placeholder 40), the bitmap encoding is column-major 1-bit LSB-first, and the `0x93` feature report is split into two 64-column chunks.

2. **Column-major 1-bit bitmap encoding.** Each column of 64 pixels maps to 8 contiguous bytes. Pixel `(x, y)` sits at byte `x*8 + y//8`, bit `y%8` (LSB = y=0 = top). This is the only layout the device accepts — row-major encodings will produce garbage on screen.

3. **Feature reports vs. interrupt writes for OLED.** `0x93` draw must use `send_feature_report()` (1024 bytes), not `write()` (64 bytes). `0x95` release and `0x85` brightness use `write()`. Mixing them crashes the packet or produces no response.

4. **Exponential-backoff retry on feature reports.** ggoled retries failed `send_feature_report` calls up to 10 times with delay `attempt² ms`. The OLED path is the only place in the package that needs retry; interrupt writes do not.

5. **Pillow (PIL) as an optional dependency.** The OLED drawing API (image loading, text rendering, GIF parsing) requires Pillow. It is declared as an optional extra (`pip install 'arctis-hid[oled]'`). All methods that need it call `_require_pil()` which raises a clear `ImportError` with the install hint. `draw_raw()` and `release()` work without Pillow.

6. **Lazy instantiation of `ArctisNovaProOled`.** The `headset.oled` property creates the controller on first access and caches it. This avoids importing Pillow at import time and keeps the controller lifecycle tied to the headset instance.

7. **`encode_frame` as a standalone exportable function.** Separating the encoding logic from the controller lets users pre-encode frames offline (e.g. in a pipeline) and call `draw_raw()` with the result, bypassing Pillow entirely.

8. **`loops=0` convention for infinite playback.** Both `play_animation()` and `play_gif()` use `loops=0` to mean "loop forever" (via `itertools.count()`), matching ggoled's `-l 0` flag semantics. `range(loops)` would give an empty iterator for 0, so the check `if loops > 0 else itertools.count()` is required.

---

## Phase 2 key lessons (2026-05-03)

1. **Separate codec layer from the API layer.** All byte-level encoding quirks (inverted volume, asymmetric gain, battery scaling, `0x10` noise filter) live in `codec.py`. The headset class never touches raw bytes — it calls codec helpers. This made the headset class straightforward to write and easy to audit.

2. **Create the AbstractOled interface before the implementation exists.** By defining `AbstractOled` and stubbing `headset.oled → None` now, the public API contract is set. Phase 3 just wires in the concrete class without breaking any callers.

3. **HID feature reports are a different transport path from interrupt writes.** OLED draw (`0x93`) uses `hid.device.send_feature_report()`, not `write()`. `HidTransport.write_feature_report()` is already stubbed. Don't conflate the two in the protocol layer.

4. **Use the event class name as the dispatcher key, not the opcode.** `headset.on("VolumeEvent", cb)` reads naturally; `headset.on(0x25, cb)` would be a leaky abstraction. `emit_typed()` derives the key automatically from the dataclass type.

5. **Auto-select custom EQ preset before writing bands.** `set_eq_bands()` internally sends `CMD_EQ_PRESET 0x04` before `CMD_EQ_BANDS`. Without this the write silently does nothing. Encapsulate the multi-step protocol in one method to prevent user footguns.

6. **Encode `GainLevel` as LOW=0/HIGH=1 in the enum, then invert at the write boundary.** `encode_gain(GainLevel.HIGH) → 0x00`. Keeping the enum semantically correct (LOW < HIGH) and inverting only at the codec edge is cleaner than an inverted enum.

7. **Daemon threads for the event loop.** `start()` creates a `daemon=True` thread so the process can exit cleanly even if `stop()` is never called. `listen()` simply calls `start()` + `thread.join()`.

8. **Discovery opens the device and returns it ready to use.** The caller just calls `discover()` — no separate `open()` needed unless constructing `ArctisNovaProWireless` directly. This matches the context manager pattern.

9. **Feature branch per feature, merge to development on completion.** The full Phase 2 package was built in `feature/arctis-hid-package` and merged with `--no-ff` to keep history readable.

---

## Phase 1 session-09 key lessons (2026-05-09)

1. **Not all queryable settings live in `0xB0`.** Base-station display settings (OLED brightness, dim screen timeout, home screen mode) are grouped under a separate query opcode `0x80`. GG issues this query in addition to `0xB0`/`0x20` at startup.
2. **Interrogating an unknown opcode first is faster than diffing `0xB0`.** Rather than assuming all settings are in known queries, sending `0x80` as a raw query and inspecting all response bytes found the answer in one shot.
3. **The timeout step encoding is reused verbatim across dim screen (`0x80[2]`), auto-off (`0xB0[12]`), and both write/event commands (`0x83`/`0xC1`)**. The `TimeoutStep` enum captures this shared encoding.
4. **`0xB0[11]` is mic LED brightness** — was mistakenly labelled "unknown" early in the session; the `listen.py` decode already printed it correctly.

---

## What is still unknown / needs more work

1. **OLED draw not yet tested on physical hardware.** The `0x93` protocol was confirmed from ggoled source (not a live capture on our bench device). Functional test against PID `0x12E0` still needed; bitmap encoding and report timing should be verified visually.
2. **All settings now queryable** — `0x80` confirmed 2026-05-09 as the missing query for OLED brightness `[3]`, dim screen timeout `[2]`, and home screen mode `[5]`. Zero unknowns remain across the five confirmed query commands (`0xB0`, `0x20`, `0x10`, `0x12`, `0x80`).
3. **EQ preset name → index mapping** — `0x04`=custom confirmed; `0x00–0x03` and `0x05–0x18` = named presets (19 total), names unknown.
4. **`0xA3` idle timeout** — candidate command from Nova 7X; not yet tested on Nova Pro.
5. **Write persistence verification** — most write commands persist across power cycles per `0x09` send, but only a subset have been explicitly tested after reboot.
6. **GG communication interface** — still unknown which HID interface GG writes to. `monitor_all.py` was built to detect this; capture has not yet been performed.

---

## Encoding quick reference

```python
# Volume (inverted)
encode: raw = round((1 - pct/100) * 56)   # 0x38=0%, 0x00=100%
decode: pct = max(0, min(100, (0x38 - raw) / 56 * 100))

# Battery
decode: pct = min(100, raw / 8 * 100)

# Gain — write is inverted vs event/query
write:        0x00=high  0x01=low
event/query:  0x01=low   0x02=high

# EQ bands: 0–40, 20 (0x14) = flat/0 dB

# OLED bitmap — column-major 1-bit, LSB = top (y=0)
# pixel (x, y) → byte: x*8 + y//8, bit: y%8
# Full frame: 128 cols × 8 bytes/col = 1024 bytes
# Sent as two 0x93 feature reports (1024 bytes each):
#   report 1: x=0..63  (dst_x=0)
#   report 2: x=64..127 (dst_x=64)
```

---

## How to use the package

```bash
pip install -e src/package/
pip install -e 'src/package/[oled]'   # also installs Pillow for OLED drawing

# Command mode
python src/package/examples/query_and_write.py

# Event/listen mode
python src/package/examples/listen_events.py

# OLED demo (brightness / text / image / animation / gif)
python src/package/examples/oled_demo.py brightness 5
python src/package/examples/oled_demo.py text "Hello"
python src/package/examples/oled_demo.py img photo.png
python src/package/examples/oled_demo.py anim --fps 10 --loops 3 f1.png f2.png
python src/package/examples/oled_demo.py gif anim.gif

# In code
from arctis_hid import discover, AncMode
with discover() as h:
    print(h.get_status())
    h.set_anc_mode(AncMode.TRANSPARENCY)
    h.on("VolumeEvent", lambda e: print(e.percent))
    h.listen()

# OLED in code (requires Pillow)
from arctis_hid import discover
with discover() as h:
    h.set_oled_brightness(7)
    h.oled.draw_text("Hello, World!")
    h.oled.draw_image("banner.png")
    h.oled.play_gif("spinner.gif", loops=3)
    # returns screen to GG/Sonar on context exit
```

## How to run the discovery scripts

```bash
pip install -r requirements.txt

python src/scripts/listen.py              # queries at startup + event loop
python src/scripts/listen.py --no-query  # listen only
python src/scripts/probe_write.py --cmd 0xBD --param 0x01
python src/scripts/probe_full_diff.py    # interactive before/after diff (0xB0 + 0x20)
python src/scripts/probe_query_scan.py   # scan all 256 opcodes
python src/scripts/find_usb_bus.py       # find Wireshark interface
python src/scripts/parse_gg_capture.py gg_capture.json
```
