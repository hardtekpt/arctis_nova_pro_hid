"""
Monitor ALL HID interfaces for the Arctis Nova Pro simultaneously.

listen.py only opens interface 4 (0xFFC0 + 0xFF00). This script opens every
HID path the device exposes — all interface numbers, all usage pages — and
logs any traffic from any handle. Use it to find which interface SteelSeries
GG uses when it reads or writes settings.

Usage:
  python scripts/monitor_all.py

Workflow:
  1. Run this script (keep SteelSeries GG open on the headset settings page).
  2. Toggle settings in GG one at a time.
  3. Watch for lines tagged [IFxx UP:0xYYYY] in the output.
  4. The interface + usage page that shows traffic is what GG uses.
  5. If no traffic appears on any handle → GG writes are silent (no events fired).

Note: GG may hold exclusive access to some handles. Those will be reported
as [SKIP] at startup. On Windows, HID handles are usually shareable but
exclusive access is possible.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import (  # noqa: E402
    ARCTIS_NOVA_PRO_PIDS,
    PACKET_SIZE,
    POLL_TIMEOUT,
    STEELSERIES_VID,
    USAGE_CONTROL,
    USAGE_EVENTS,
    _raw,
    decode_packet,
    open_log,
    log,
)

_KNOWN_USAGE = {USAGE_CONTROL: "Col01/ctrl", USAGE_EVENTS: "Col02/evt"}


def main() -> None:
    all_ifaces = [
        d
        for d in hid.enumerate()
        if d["vendor_id"] == STEELSERIES_VID
        and d["product_id"] in ARCTIS_NOVA_PRO_PIDS
    ]

    if not all_ifaces:
        print("No Arctis Nova Pro device found. Is the base station plugged in?")
        sys.exit(1)

    all_ifaces.sort(key=lambda d: (d["interface_number"], d["usage_page"]))
    name = ARCTIS_NOVA_PRO_PIDS[all_ifaces[0]["product_id"]]

    print(f"Device : {name}")
    print(f"Found  : {len(all_ifaces)} HID interface(s) total\n")
    print(f"  {'IF':>3}  {'UsagePage':>10}  {'Known role':14}  Path")
    print("  " + "-" * 72)
    for d in all_ifaces:
        iface_num = d["interface_number"]
        up = d["usage_page"]
        role = _KNOWN_USAGE.get(up, "unknown")
        path = d["path"].decode() if isinstance(d["path"], bytes) else d["path"]
        print(f"  {iface_num:>3}  0x{up:04X}        {role:<14}  {path}")
    print()

    handles: list[tuple[hid.device, str]] = []
    print("Opening all interfaces...\n")
    for d in all_ifaces:
        iface_num = d["interface_number"]
        up = d["usage_page"]
        label = f"IF{iface_num:02d} UP:0x{up:04X}"
        path = d["path"]
        try:
            dev = hid.device()
            dev.open_path(path)
            dev.set_nonblocking(1)
            handles.append((dev, label))
            role = _KNOWN_USAGE.get(up, "*** UNKNOWN ***")
            print(f"  [OPEN] {label}  ({role})")
        except Exception as exc:
            print(f"  [SKIP] {label}  ({exc})")

    if not handles:
        print("\nERROR: Could not open any interface.")
        sys.exit(1)

    log_f, log_path = open_log()
    print(f"\nLog    : {log_path}")
    print("\n" + "=" * 60)
    print("Listening on all open interfaces.")
    print("Toggle settings in SteelSeries GG now. Ctrl+C to stop.\n")
    print("Key:")
    print("  IF04 UP:0xFFC0 = Col01/ctrl  (known — our query/write channel)")
    print("  IF04 UP:0xFF00 = Col02/evt   (known — hardware event channel)")
    print("  Any other IF or UP = previously unmonitored interface\n")

    try:
        while True:
            for dev, label in handles:
                data = dev.read(PACKET_SIZE, POLL_TIMEOUT)
                if not data:
                    continue
                d = list(data)
                log(log_f, f"[{label}] RAW: {_raw(d)}")
                decoded = decode_packet(d, label)
                if decoded:
                    log(log_f, decoded)
                else:
                    cmd = data[1] if len(data) > 1 else "?"
                    log(log_f, f"[{label}] 0x{cmd:02X}  (unknown command)")

    except KeyboardInterrupt:
        log(log_f, "\n[INFO ] Stopped by user.")
    finally:
        for dev, _ in handles:
            try:
                dev.close()
            except Exception:
                pass
        log_f.close()
        print(f"\nSession saved → {log_path}")


if __name__ == "__main__":
    main()
