# Wireshark USB Capture Guide
## Capturing SteelSeries GG ↔ Arctis Nova Pro Traffic

**Goal:** record every USB packet GG Engine sends to and receives from the
headset, so we can discover the query commands it uses to read the 7 settings
that have no known query opcode (BT default, auto-mute, audio output, dim screen,
home screen, mic LED brightness, auto off).

---

## Why Python HID alone cannot see GG's packets

`hidapi` / `hid.read()` only receives **device → host** (Interrupt IN)
transfers — packets the device sends to the PC. It cannot observe what any
other process writes to the device. GG's commands are **host → device**
(Interrupt OUT) transfers; they are invisible to our scripts. USB-level
capture with USBPcap sees both directions simultaneously.

---

## Prerequisites

| Tool | Install | Notes |
|---|---|---|
| **Wireshark** (≥ 4.0) | [wireshark.org/download.html](https://www.wireshark.org/download.html) | Windows installer — check **"Install USBPcap"** during setup |
| **Python 3** + project deps | already installed | |
| **pyshark** (optional) | `pip install pyshark` | only needed for `.pcapng` input; not needed for JSON export |

> **Tip:** if Wireshark is already installed without USBPcap, re-run the
> installer and choose "Modify" to add USBPcap.

---

## Step 1 — Find the correct USBPcap interface

Run the helper script:

```
python scripts/find_usb_bus.py
```

It prints a table like:

```
USB host controllers (→ USBPcap interface numbers):
  USBPcap1    Intel(R) USB 3.0 eXtensible Host Controller
  USBPcap2    AMD USB 3.10 eXtensible Host Controller  ← headset is on THIS bus
```

If the script cannot detect the host controller automatically, use either of
these manual methods:

**Method A — capture on all buses at once (simplest):**
1. Open Wireshark.
2. In the interface list, `Ctrl`-click every interface whose name begins with
   `USBPcap`.
3. Click **Start**.
4. Unplug and replug the headset's USB cable.
5. Apply the display filter: `usb.idVendor == 0x1038`
6. Whichever USBPcap interface shows traffic is the correct one.
7. Note the name, stop the capture, and continue with Step 2 using only that
   interface.

**Method B — Device Manager:**
1. Open Device Manager → **View → Devices by connection**.
2. Expand USB root hubs from the top until you find
   `SteelSeries Arctis Nova Pro`.
3. The root hub it lives under maps to `USBPcap1`, `USBPcap2`, etc. counting
   down from the top of the USB tree.

---

## Step 2 — Configure the capture

1. Open Wireshark.
2. Select the USBPcap interface identified in Step 1.
3. In **Capture → Options → Input**, set a capture filter to reduce noise:
   ```
   (no capture filter needed — we filter with display filters instead)
   ```
   Leave the capture filter blank; filtering during live capture can drop
   packets.
4. Click **Start**.

---

## Step 3 — Trigger GG Engine traffic

With the capture running:

1. **Open SteelSeries GG** and navigate to the headset settings page.  
   GG sends startup query commands when it loads the page — these are the
   "read current state" packets we want most.

2. Change each of the following settings **one at a time**, waiting ~2 seconds
   between each change:
   - BT Default (on/off)
   - BT Auto-Mute (off / −12 dB / on)
   - Audio Output (speakers / stream)
   - Dim Screen timeout
   - Home Screen mode (detailed / simple)
   - Mic LED Brightness
   - Auto Off timeout

3. For each setting, toggle it to a **non-default value**, then back to the
   original. This ensures we see both the write command and any response.

4. Close and reopen the GG settings page once more (triggers another round of
   startup queries).

---

## Step 4 — Stop the capture and export

1. Click **Stop** (■) in Wireshark.

2. Apply the display filter to reduce the view to only relevant packets:
   ```
   usb.idVendor == 0x1038 && usb.transfer_type == 0x01
   ```
   > If no packets appear with `usb.idVendor == 0x1038`, the enumeration
   > packets were not captured (device was already connected). Skip the
   > `usb.idVendor` part and filter by device address instead — see
   > Troubleshooting below.

3. Export the filtered view as JSON:  
   **File → Export Packet Dissections → As JSON…**  
   Save as `gg_capture.json` in the project root.

   > **Important:** export with the display filter active so the JSON contains
   > only the SteelSeries interrupt packets, not the entire capture.

---

## Step 5 — Parse the capture

```
python scripts/parse_gg_capture.py gg_capture.json
```

If the device address was not captured in the enumeration phase:
```
python scripts/parse_gg_capture.py gg_capture.json --device 3.17
```
(Replace `3.17` with the bus.device address shown by Wireshark's packet
detail pane — `usb.bus_id` `.` `usb.device_address`.)

Useful flags:
```
--out-only    show only GG→device packets (GG's commands)
--in-only     show only device→GG packets (device responses)
--device N.M  specify bus.device address manually
```

---

## Step 6 — Interpret the output

### Example output

```
File   : gg_capture.json
Device : (auto-detect)
Auto-detected SteelSeries device at bus.address: 3.17

[0.000000000] [GG→DEV] 0xB0  param=0x00  [06 B0 00 00 00 00 00 00 00 00 …]
[0.012345678] [DEV→GG] 0xB0  Status → headset_bat=12%  dock_bat=100%  …
[0.025000000] [GG→DEV] 0x20  param=0x00  [06 20 00 00 00 00 00 00 00 00 …]
[0.037000000] [DEV→GG] 0x20  Mic/EQ → gain=low  mic_vol=5  sidetone=off  …
[0.050000000] [GG→DEV] 0xC4  param=0x00  [06 C4 00 00 00 00 00 00 00 00 …]  *** UNKNOWN ***
[0.062000000] [DEV→GG] 0xC4  (unknown — raw bytes above)
```

### What to look for

| Pattern | Meaning |
|---|---|
| `[GG→DEV] 0xXX param=0x00` followed by `[DEV→GG] 0xXX …` | GG sent a query; device responded. The opcode `0xXX` is a new query command. |
| `[GG→DEV] 0xXX param=0xVV` with no response | GG sent a write command (param = the value it set). |
| `*** UNKNOWN ***` marker | This opcode is not in the confirmed command map — it is a discovery. |
| `[DEV→GG] 0xB7 Battery →` at startup | Device pushed unsolicited battery packet (already known). |

### Decoding a new query response

When a new opcode appears (e.g. `0xC4`):
1. Note its full response bytes from the `DEV→GG` line.
2. Run `probe_full_diff.py` — it will now show changes in the new response
   if you toggle the corresponding setting in GG.
3. Or run `probe_write.py --cmd 0xXX --param 0xVV` to write a known value,
   then re-query `0xC4` manually and verify the byte changed.
4. Add confirmed field mappings to `docs/HidCommands.md`.

---

## Troubleshooting

### No packets appear after applying the filter

The device was already connected when Wireshark started, so the USB
enumeration (which contains `usb.idVendor`) was not captured.

Fix: find the device address manually.
1. Remove the `usb.idVendor` part of the filter: use only `usb.transfer_type == 0x01`.
2. In the packet list, click any packet and look at the **Packet Details** pane.
3. Expand the **USB URB** section and read `usb.bus_id` and `usb.device_address`.
4. Look for an address that shows HID report data (first byte `0x06`).
5. Re-run parse_gg_capture.py with `--device BUS.ADDR`.

### "pyshark not installed" error when using .pcapng

Export from Wireshark as JSON instead (Step 4 above), or:
```
pip install pyshark
```
pyshark requires tshark, which is bundled with Wireshark on Windows.

### `find_usb_bus.py` shows "PowerShell query failed"

Run the terminal as **Administrator** — querying PnP device properties
sometimes requires elevated privileges.

### GG traffic still not visible after capture

- Confirm GG is communicating with the headset: change a setting in GG and
  verify the headset responds (e.g. volume changes, OLED brightness changes).
- Confirm the headset is connected to the **base station via USB** (not
  directly via USB-C to PC).
- Try capturing on a different USBPcap interface — the device may be on a
  different USB bus than expected.
- Try the reconnect trick in Step 1 / Method A to confirm the correct bus.

### Packet direction is wrong / all shown as one direction

- Wireshark's URB type (`usb.urb_type`) must be `S` (submit) or `C`
  (complete). If it shows hex values instead (`53`, `43`), the JSON parser
  handles this automatically.
- If endpoint direction cannot be determined, packets are skipped. Export as
  JSON with the full packet details pane expanded (use default export settings
  in Wireshark).
