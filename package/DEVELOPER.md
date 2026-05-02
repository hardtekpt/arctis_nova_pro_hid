# arctis-hid — Developer Guide

This document covers the package architecture, HID protocol reference, and how to extend the library.

---

## Architecture overview

```
arctis_hid/
├── __init__.py            ← Public surface (re-exports everything)
├── discovery.py           ← discover() — enumerate HID, return AbstractHeadset
├── exceptions.py          ← DeviceError hierarchy
├── core/
│   ├── transport.py       ← HidTransport: raw packet I/O (hidapi wrapper)
│   ├── dispatcher.py      ← EventDispatcher: callback registration + fire
│   └── types.py           ← Shared enums (AncMode, GainLevel, …)
└── devices/
    ├── base.py            ← AbstractHeadset + AbstractOled (ABCs)
    └── nova_pro/
        ├── constants.py   ← Command bytes, field indices, device IDs
        ├── codec.py       ← Encode/decode: all byte-level conversions
        ├── models.py      ← Dataclasses: StatusData, MicEqData, *Event
        └── headset.py     ← ArctisNovaProWireless(AbstractHeadset)
```

### Layer rules

| Layer | Knows about | Must NOT know about |
|-------|-------------|---------------------|
| `core/transport` | `hidapi` | device protocol |
| `core/dispatcher` | callbacks | device protocol |
| `devices/base` | abstract interface | concrete devices |
| `nova_pro/constants` | raw bytes | Python types |
| `nova_pro/codec` | constants + models | transport |
| `nova_pro/headset` | all layers above | hidapi directly |

---

## HID protocol reference

### Device identification

| Field | Value |
|-------|-------|
| VID | `0x1038` (SteelSeries) |
| Tested PID | `0x12E0` (Arctis Nova Pro Wireless X) |
| Other PIDs | `0x12CB`, `0x12CD`, `0x12E5`, `0x225D` |
| USB interface | 4 |
| Col01 usage page | `0xFFC0` — bidirectional (queries + writes) |
| Col02 usage page | `0xFF00` — read-only (unsolicited events) |
| Packet size | 64 bytes |
| Outgoing report ID | `0x06` |
| Incoming report ID | `0x06` (query response) or `0x07` (events) |

### Packet format

```
Write / query:  [0x06, CMD, PARAM, 0x00 × 61]   (64 bytes → Col01)
Save:           [0x06, 0x09, 0x00 × 62]          (always after writes)
```

### Timing

| Constant | Value | Reason |
|----------|-------|--------|
| Poll timeout | 50 ms | Keeps event latency low without busy-looping |
| Query delay | 100 ms | Device needs time to prepare the response |
| Write→save gap | ~0 ms | Can be back-to-back; device queues them |

### Save is mandatory

After **every** write command, `0x09` must be sent or settings revert on the next power cycle. `ArctisNovaProWireless._save()` handles this automatically — all `set_*` methods call it.

---

## Encoding quirks

### Volume (inverted)

```python
# 0x38 (56) = 0%,  0x00 = 100%
encode: raw = round((1 - pct/100) * 56)
decode: pct = max(0, min(100, (0x38 - raw) / 56 * 100))
```

### Battery

```python
# raw 0–8 → 0–100%
pct = min(100, raw / 8 * 100)
```

### Gain — asymmetric encoding

The write encoding for `CMD_GAIN` (`0x27`) is inverted relative to events and the `0x20` query:

| Context | LOW | HIGH |
|---------|-----|------|
| Write (`0x27`) | `0x01` | `0x00` |
| Event (`0x27`) | `0x01` | `0x02` |
| Query `0x20[4]` | `0x01` | `0x02` |

`codec.encode_gain()` handles the write inversion; `codec.decode_gain_event/query()` handle the read side.

### EQ bands

Range 0–40, where `0x14` (20 decimal) = flat / 0 dB.

### Silent writes

`CMD_WIRELESS` (`0xC3`) produces **no Col02 event** when written. Always verify via `get_status().wireless_mode`.

---

## Event filtering

The device pushes unsolicited `0x10` (firmware version) packets on **Col01** whenever the headset wirelessly reconnects. `codec.decode_event()` returns `None` for these so they are silently dropped.

---

## Adding a new command to Nova Pro

1. **`constants.py`** — add `CMD_NEW = 0xXX`
2. **`codec.py`** — add encode/decode helpers if the encoding is non-trivial
3. **`models.py`** — add a new event dataclass if it fires on Col02
4. **`headset.py`** — add `set_new_thing()` / `get_new_thing()` method; call `_save()` after writes
5. **`__init__.py`** (package root) — re-export any new public symbols
6. **`README.md`** — add a row to the API reference table

---

## Adding a new device model

1. Create `devices/<model_name>/` with the same structure as `nova_pro/`
2. Subclass `AbstractHeadset` in `headset.py`
3. Add its VID/PIDs to `discovery.py` (or create a model-specific `discover_<model>()`)
4. Export from `arctis_hid/__init__.py`

The `AbstractHeadset` contract requires: `open`, `close`, `get_status`, `get_mic_eq`, `get_firmware_version`, `get_serial_number`, `on`, `off`, `listen`, `start`, `stop`.

---

## OLED screen customization (Phase 3)

### Confirmed protocol facts

- **`CMD_OLED_DRAW` (`0x93`)**: Uses **HID feature reports** (not interrupt OUT). Each report is **1024 bytes**. A full frame requires **2 consecutive reports** (left half then right half).
- **`CMD_OLED_RELEASE` (`0x95`)**: Normal interrupt write. Returns OLED control to GG / Sonar.

### Transport support

`HidTransport.write_feature_report(report_id, data)` is already implemented and calls `hid.device.send_feature_report()`.

### Open questions (resolve before implementing `oled.py`)

| Question | Likely answer | How to verify |
|----------|--------------|---------------|
| Display dimensions | 128 × 40 px | Wireshark capture |
| Pixel format | 1-bit mono, row-major, MSB-first | Capture + visual test |
| Report header layout | report_id + sequence byte + half index | Decode raw capture |
| Frame rate limit | Unknown | Empirical test |
| Color depth | 1-bit mono (no grayscale) | Capture |

### How to decode the OLED protocol

1. Connect the headset and ensure GG is showing its default OLED screen.
2. Run `scripts/parse_gg_capture.py` with a Wireshark capture taken while GG draws a known image (e.g. all-black, all-white, checkerboard).
3. Look for `0x93` feature reports in the output.
4. Compare the pixel data region across different known images to determine bit layout.
5. Update `OLED_WIDTH`, `OLED_HEIGHT`, and the frame encoding in `nova_pro/constants.py`.
6. Implement `devices/nova_pro/oled.py`:

```python
class ArctisNovaProOled(AbstractOled):
    width  = 128   # update after verification
    height = 40    # update after verification

    def draw_raw(self, frame: bytes) -> None:
        # split into two halves, send each as a feature report via transport
        half = len(frame) // 2
        self._transport.write_feature_report(CMD_OLED_DRAW, frame[:half])
        self._transport.write_feature_report(CMD_OLED_DRAW, frame[half:])

    def draw_image(self, img) -> None:
        # PIL convenience: resize → 1-bit → pack → draw_raw
        ...

    def release(self) -> None:
        self._transport.write(CMD_OLED_RELEASE)
```

7. Wire `ArctisNovaProWireless.oled` property to return a lazily-created `ArctisNovaProOled`.
8. Add `oled = ["pillow"]` optional dep and update `README.md`.

---

## Running the examples

```bash
# Install in dev mode from the project root
pip install -e package/

# Query device state and apply sample settings
python package/examples/query_and_write.py

# Listen for hardware events in real time
python package/examples/listen_events.py
```

---

## Known limitations

- SteelSeries GG changes are **not visible** as Col02 events. Only physical control changes (dial, buttons) produce events.
- Several settings have no confirmed query command: `BT default`, `BT auto-mute`, `audio output`, `dim timeout`, `home screen`, `mic LED brightness`, `auto-off timeout`. GG reads them somehow — mechanism unknown.
- Preset name → index mapping for `CMD_EQ_PRESET` (`0x2E`) is unconfirmed. Index `0x04` = custom; `0x00–0x03` and `0x05–0x18` = named presets (names TBD).
- `CMD_0xA0` produced no response on the bench device.
