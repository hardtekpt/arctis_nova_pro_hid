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
- Runs the startup query set: `0xB0`, `0x20`, `0x10`, `0x12`, `0x80`
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
1. Run `probe_full_diff.py` while toggling a GG setting to identify which `0xB0`/`0x20` byte changes.
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
python src/scripts/probe_query_scan.py --delay 0.15          # slower, more reliable
python src/scripts/probe_query_scan.py --start 0x80          # resume from a specific opcode
python src/scripts/probe_query_scan.py --check-settings      # detect per-opcode mutations
```

**Flags:**
| Flag | Default | Description |
|------|---------|-------------|
| `--delay` | `0.12` | Seconds to wait for a response after each query |
| `--start` | `0x00` | First opcode to scan |
| `--end` | `0xFF` | Last opcode to scan (inclusive) |
| `--check-settings` | off | Snapshot and diff all known settings after every probe |

**Output labels:**
- `KNOWN:` — one of the confirmed query commands (`0xB0`, `0x20`, `0x10`, `0x12`, `0x80`)
- `RESPONSIVE:` — new opcode that returned non-trivial data; full 64-byte hex dump
- `MUTATING:` — no response data, but settings changed (only with `--check-settings`)
- `.` — no response, no settings change (silent/benign opcode)
- `[RESET]` — the command caused the base station to disconnect

**Reset detection:** If an opcode causes the base station to disconnect (`OSError` on write or read), the script:
1. Logs `[RESET] 0xXX caused a disconnect` with the error message.
2. Waits up to 30 s for the device to reappear and re-opens the handle.
3. Queries firmware version (`0x10`) and prints whether it changed vs. the baseline recorded at startup.
4. With `--check-settings`, snapshots settings immediately after reconnect and shows what changed.
5. Resumes scanning from the next opcode.

**Settings tracking (`--check-settings`):** After every probe, queries `0xB0` (status), `0x20` (mic/EQ), and `0x80` (display) and diffs the full response against the previous snapshot. This uses a rolling baseline — the "after" snapshot for opcode N becomes the "before" snapshot for opcode N+1, so each row in the summary shows only the incremental changes from that specific opcode. A `← N setting(s) changed` suffix is appended to KNOWN/RESPONSIVE/MUTATING lines inline. The final summary prints a full settings-change table:

```
SETTINGS CHANGES PER COMMAND (3 commands affected settings):

  0x25  [RESPONSIVE]
    headset_volume: 82% → 57%

  0x39  [MUTATING]
    sidetone: off → low

  0x2E  [KNOWN]
    eq_preset: preset 0x00 → custom
```

Fields tracked: all named fields from `0xB0[2–13]`, `0x20[3–25]`, and `0x80[2,3,5]`, with human-readable value formatting (battery as %, gain as low/high, timeouts as "5 min", etc.). Adds ~0.3 s overhead per opcode (~77 s extra over a full scan).

**Caution:** Sending unknown opcodes as queries can change device settings. This script only sends read-style packets (no `0x09` save), but some opcodes trigger side effects including silent writes and device resets.

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

**Purpose:** Decode a Wireshark capture of SteelSeries GG ↔ headset USB traffic. Accepts both `.json` (Wireshark JSON export) and `.pcapng`/`.pcap` formats.

**Usage:**
```bash
python src/scripts/parse_gg_capture.py --file capture.json
python src/scripts/parse_gg_capture.py --file capture.pcapng
python src/scripts/parse_gg_capture.py --file capture.json --device 3.17
python src/scripts/parse_gg_capture.py --file capture.json --out-only
python src/scripts/parse_gg_capture.py --file capture.json --in-only
```

**Flags:**
| Flag | Required | Description |
|------|----------|-------------|
| `--file` / `-f` | Yes | Capture file (`.json`, `.pcapng`, or `.pcap`) |
| `--device` / `-d` | No | USB `bus.address` (e.g. `3.17`); auto-detected from descriptor packets if omitted |
| `--out-only` | No | Show only GG→device (host-to-device) packets |
| `--in-only` | No | Show only device→GG (device-to-host) packets |

**Output:**
- Decoded lines for every known opcode using the same decoder as `listen.py`
- Direction indicator (`GG→DEV` or `DEV→GG`)
- Raw hex for unknown packets, flagged with `*** UNKNOWN ***` if host-initiated
- Summary showing any command bytes not in the known map (candidates for further probing)

**Use case:** Compare what GG sends/receives against what the Python package sends to verify protocol compatibility or discover new commands.

---

## test_cli.py

**Purpose:** Unified test harness covering every item in `docs/TestChecklist.md`. Wraps the `arctis-hid` package to exercise every query, write, event, OLED, and edge-case command from a single script.

**Prerequisites:**
```bash
pip install -e src/package/           # core package
pip install -e 'src/package/[oled]'   # add Pillow for oled-* commands
```

All arguments use `--` notation. `--command` selects the operation; value arguments are separate flags.

**Modes:**

### Interactive menu (`--interactive`)

```bash
python src/scripts/test_cli.py --interactive
python src/scripts/test_cli.py -i
```

Launches a navigable terminal menu. Use numbered entries to select a category, then a command within it. Values are prompted inline with validation and sensible defaults. A verify toggle is available from the main menu.

### Command-line (`--command`)

```bash
python src/scripts/test_cli.py --command <CMD> [flags...]
python src/scripts/test_cli.py --verify --command <CMD> [flags...]
```

**Global flags:**
| Flag | Description |
|------|-------------|
| `--command` / `-c` | Command to run (required unless `--interactive`) |
| `--verify` | Re-query after each write and print before/after field values |
| `--interactive` / `-i` | Launch interactive terminal menu |

**Query commands (§2):**
```bash
python src/scripts/test_cli.py --command query    # all queries at once (0xB0/0x20/0x80/0x10/0x12)
python src/scripts/test_cli.py --command status   # 0xB0 status packet
python src/scripts/test_cli.py --command miceq    # 0x20 mic/EQ packet
python src/scripts/test_cli.py --command display  # 0x80 base-station display packet
```

**Event listener (§1):**
```bash
python src/scripts/test_cli.py --command listen   # block until Ctrl-C
```

**Write commands (§3–5):**
```bash
python src/scripts/test_cli.py --verify --command volume           --pct 75
python src/scripts/test_cli.py --verify --command mic-vol          --level 6
python src/scripts/test_cli.py --verify --command sidetone         --level high
python src/scripts/test_cli.py --verify --command anc              --mode transparency
python src/scripts/test_cli.py         --command transparency      --level 7
python src/scripts/test_cli.py --verify --command gain             --level low
python src/scripts/test_cli.py --verify --command oled-brightness  --level 5
python src/scripts/test_cli.py         --command mic-led           --level 5
python src/scripts/test_cli.py --verify --command audio-output     --output speakers
python src/scripts/test_cli.py --verify --command stream-volumes   --main 80 --aux 80 --mic 60
python src/scripts/test_cli.py         --command chatmix           --state on
python src/scripts/test_cli.py         --command dim-timeout       --step 15
python src/scripts/test_cli.py         --command home-screen       --mode simple
python src/scripts/test_cli.py         --command auto-off          --step 30
python src/scripts/test_cli.py --verify --command wireless-mode    --mode performance
python src/scripts/test_cli.py         --command bt-default        --state on
python src/scripts/test_cli.py         --command bt-auto-mute      --mode off
python src/scripts/test_cli.py --verify --command eq-preset        --index 0x04
python src/scripts/test_cli.py --verify --command eq-bands         --bands 20 20 20 20 20 20 20 20 20 20
```

**OLED commands (§10, requires Pillow):**
```bash
python src/scripts/test_cli.py --command oled-clear
python src/scripts/test_cli.py --command oled-release
python src/scripts/test_cli.py --command oled-text    --text "Hello" [--x N] [--y N] [--invert] [--font path.ttf]
python src/scripts/test_cli.py --command oled-scroll  --text "The quick brown fox" [--fps 15]
python src/scripts/test_cli.py --command oled-img     --path banner.png [--threshold 100]
python src/scripts/test_cli.py --command oled-anim    --frames f1.png f2.png [--fps 10] [--loops 3]
python src/scripts/test_cli.py --command oled-gif     --path anim.gif [--loops 3]
```

**Edge cases (§9):**
```bash
python src/scripts/test_cli.py --command edge-volume-min
python src/scripts/test_cli.py --command edge-volume-max
python src/scripts/test_cli.py --command edge-sidetone-oob --value 0x04
python src/scripts/test_cli.py --command edge-mic-vol-oob  --value 0x00
```

**`--verify` behaviour:** When passed, the script queries the relevant field before and after the write and prints `before → after [OK/UNEXPECTED]`. Commands with no query-reflected field print a note to verify visually or via `--command listen`.

---

## probe_sonar_api.py

**Purpose:** Query the SteelSeries GG Sonar local REST API to discover EQ preset names and audio configuration data. Reads `coreProps.json` to find the Sonar HTTPS address, then queries the `/configs` and `/configs/selected` endpoints.

This is a supplementary discovery tool for mapping EQ preset indices to human-readable names (the HID `0x2E`/`0x20[6]` preset index → name mapping is not exposed over HID). GG Sonar runs a local HTTPS server with a self-signed certificate; the script ignores certificate errors.

**Usage:**
```bash
python src/scripts/probe_sonar_api.py
python src/scripts/probe_sonar_api.py --endpoint /configs/selected
python src/scripts/probe_sonar_api.py --endpoint /volumeSettings/classic
```

**Flags:**
| Flag | Required | Description |
|------|----------|-------------|
| `--endpoint` | No | Extra endpoint to fetch in addition to `/configs`, `/configs/selected`, `/features` |

**Output:** JSON responses from each endpoint, pretty-printed. Any `HTTP 404` or connection error is printed with context rather than crashing.

**Requirements:** SteelSeries GG / Engine 3 must be running. `coreProps.json` must exist at `C:\ProgramData\SteelSeries\SteelSeries Engine 3\coreProps.json`. No additional pip packages — uses Python stdlib only.
