# Discovery Scripts Reference

All scripts live in `src/scripts/` and are **Phase 1 reverse-engineering tools** — they probe and listen to the raw HID protocol to discover and verify commands. They are standalone utilities and are not imported by the `arctis-hid` package.

**Prerequisites:**
```bash
pip install -r requirements.txt   # installs hidapi
```

Most scripts must be run with a connected base station. On Windows, running as Administrator is sometimes required for HID access.

---

## listen.py

**Purpose:** Open both HID collections on the headset, optionally send a fixed set of startup query commands, then enter a live event loop that logs and decodes every incoming packet.

This was the primary discovery tool for Phase 1 — it revealed all known event opcodes and field offsets by logging raw packets while interacting with the headset physically.

**Usage:**
```bash
python src/scripts/listen.py              # send queries at startup, then listen
python src/scripts/listen.py --no-query  # listen-only, no writes
```

**Flags:**
| Flag | Description |
|------|-------------|
| `--no-query` | Skip the startup query burst (useful when you only want to watch events) |

**Output:**
- Decoded packet lines for all known opcodes (`0xB0`, `0x20`, `0x25`, `0xBD`, `0xBB`, etc.)
- Raw hex dump for unknown packets
- Session log saved to `logs/hid_session_<timestamp>.log`

**Key internals:**
- Opens both `0xFFC0` (control) and `0xFF00` (events) handles via `hidapi`
- Polls both at 50 ms intervals
- Runs the startup query set: `0xB0`, `0x20`, `0x10`, `0x12`
- Packet decoder lives in `decode_packet()` — imported by `probe_write.py`

---

## probe_write.py

**Purpose:** Send a single HID write command and diff the `0xB0` status response before and after to see which byte changed. Used to confirm that a command byte has the intended effect.

**Usage:**
```bash
python src/scripts/probe_write.py --cmd 0xBD --param 0x01
python src/scripts/probe_write.py --cmd 0x47 --data 80,0,40,60
python src/scripts/probe_write.py --cmd 0x25 --param 0x1C --no-save
```

**Flags:**
| Flag | Required | Description |
|------|----------|-------------|
| `--cmd` | Yes | Command byte to probe (e.g. `0xBD`) |
| `--param` | One of these | Single payload byte |
| `--data` | One of these | Comma-separated multi-byte payload (e.g. `80,0,40,60`) |
| `--no-save` | No | Skip the `0x09` save command after the write |

**Output:**
```
[BEFORE] 06 B0 ...
[WRITE ] 06 BD 01 00 ...
[EVENT ] ...decoded event...
[AFTER ] 06 B0 ...
[DIFF  ] byte[10]: 00 -> 01
```

**Discovery workflow:**
1. Run `probe_b0_diff.py` while toggling a GG setting to identify which `0xB0` byte changes.
2. Run `probe_write.py --cmd <candidate> --param <value>` and observe `[DIFF]` output.
3. If the same byte changes, the command is confirmed.

---

## probe_full_diff.py

**Purpose:** Interactive before/after diff of both `0xB0` (status) and `0x20` (mic/EQ) response packets. Queries both before and after user input, printing which bytes changed. Use this to map any unknown GG setting to a specific byte position in either response.

**Usage:**
```bash
python src/scripts/probe_full_diff.py
```

**Workflow:**
1. Run the script — it queries `0xB0` and `0x20` and saves both as "before" snapshots.
2. Toggle a **single** setting in SteelSeries GG (ANC, mic brightness, timeout, EQ preset, etc.).
3. Press Enter — the script re-queries both and prints a byte-level diff for each.
4. Repeat for each setting you want to map.

**Output:** Shows byte-level diffs for both packets with index, before value, and after value clearly labelled.

---

## probe_query_scan.py

**Purpose:** Iterate over all 256 possible query opcodes (`0x00`–`0xFF`), send each one, and record any non-trivial response. Used to find undiscovered query commands beyond the known set.

**Usage:**
```bash
python src/scripts/probe_query_scan.py
```

**Output:** Prints each opcode that returned a non-zero response with the raw bytes. Unknown responses are candidates for deeper investigation with `probe_write.py` or `probe_b0_diff.py`.

**Caution:** Sending unknown write commands (as opposed to queries) can change device settings. This script only sends read-style packets but some opcodes may trigger side effects.

---

## discover.py

**Purpose:** Enumerate all HID devices on the system and identify which interfaces belong to the Arctis Nova Pro. Prints vendor ID, product ID, usage page, interface number, and HID path for each matching device.

**Usage:**
```bash
python src/scripts/discover.py
```

**Output:**
```
VID=0x1038  PID=0x12E0  usage=0xFFC0  iface=4  path=\\?\hid#...  ← control
VID=0x1038  PID=0x12E0  usage=0xFF00  iface=4  path=\\?\hid#...  ← events
```

Use this first when troubleshooting connectivity — it confirms which HID paths to open and verifies the device is visible to the OS.

---

## monitor_all.py

**Purpose:** Open every HID interface on the Arctis Nova Pro simultaneously and log all incoming traffic. Used to determine which interface SteelSeries GG communicates on.

**Usage:**
```bash
python src/scripts/monitor_all.py
```

**Output:** Labelled packet streams from all open handles, allowing comparison of what GG sends/receives vs. what the Phase 1 scripts use.

**Note:** May conflict with GG if both try to open the same exclusive handle.

---

## find_usb_bus.py

**Purpose:** Identify the correct Wireshark USBPcap interface number for the Arctis Nova Pro. Enumerates USB buses and matches the headset by VID/PID.

**Usage:**
```bash
python src/scripts/find_usb_bus.py
```

**Output:**
```
Headset found on USBPcap3 (bus 3, port 4)
Use: USBPcap3 in Wireshark
```

Used as a setup step before capturing HID traffic with Wireshark (see `docs/WiresharkCaptureGuide.md`).

---

## parse_gg_capture.py

**Purpose:** Decode a Wireshark capture of SteelSeries GG ↔ headset USB traffic. Accepts both `.json` (Wireshark JSON export) and `.pcapng` formats.

**Usage:**
```bash
python src/scripts/parse_gg_capture.py capture.json
python src/scripts/parse_gg_capture.py capture.pcapng
```

**Output:**
- Decoded lines for every known opcode using the same decoder as `listen.py`
- Direction indicator (host→device or device→host)
- Raw hex for unknown packets

**Use case:** Compare what GG sends/receives against what the Python package sends to verify protocol compatibility or discover new commands.

---

## test_cli.py

**Purpose:** Unified CLI test harness covering all commands in `docs/TestChecklist.md`. Allows exercising every headset write and read command in sequence from the command line.

**Usage:**
```bash
python src/scripts/test_cli.py --help
python src/scripts/test_cli.py status
python src/scripts/test_cli.py set-volume 75
python src/scripts/test_cli.py set-anc transparency
```

**Key flags:** Run `--help` for the full list. Each subcommand maps directly to a checklist item.

**Note:** Uses the `arctis-hid` package (`src/package/`). Requires `pip install -e src/package/` first.
