"""
Interactive 0xB0 before/after full-byte diff tool.

Use this to detect whether a GG setting change (e.g. 2.4 GHz Speed/Range)
is reflected anywhere in the 0xB0 status response — including unknown bytes.

Usage:
  python scripts/probe_b0_diff.py

Workflow:
  1. Script queries 0xB0 and prints all 64 bytes (BEFORE snapshot).
  2. You toggle the target setting in SteelSeries GG.
  3. Press Enter.
  4. Script queries 0xB0 again and prints a diff of all changed bytes.

If any byte changes, that byte index is the state field for the setting.
Use probe_write.py to then test write candidates that affect the same byte.
"""

import sys
import time
from pathlib import Path

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import (  # noqa: E402
    PACKET_SIZE,
    REPORT_ID,
    build_query,
    find_handles,
)

CMD_STATUS = 0xB0


def query_b0(ctrl) -> list[int] | None:
    ctrl.write(list(build_query(CMD_STATUS)))
    time.sleep(0.15)
    data = ctrl.read(PACKET_SIZE, 300)
    return list(data) if data else None


def print_snapshot(label: str, data: list[int]) -> None:
    print(f"\n{label} — 0xB0 full response ({len(data)} bytes)")
    print("  idx  hex  dec")
    for i, b in enumerate(data):
        print(f"  [{i:02d}]  {b:02X}   {b:3d}")


def print_diff(before: list[int], after: list[int]) -> None:
    changed = [(i, before[i], after[i]) for i in range(min(len(before), len(after))) if before[i] != after[i]]
    if not changed:
        print("\n  (no bytes changed)")
        return
    print(f"\n  {len(changed)} byte(s) changed:")
    print("  idx  before  after")
    for i, b, a in changed:
        print(f"  [{i:02d}]  0x{b:02X}={b:3d}  →  0x{a:02X}={a:3d}  *** CHANGED ***")


def main() -> None:
    ctrl_path, _, device_name = find_handles()
    if not ctrl_path:
        print("ERROR: Control handle (0xFFC0) not found — is the base station plugged in?")
        sys.exit(1)

    print(f"Device : {device_name}")
    print("This tool diffs all 64 bytes of the 0xB0 status response before/after a GG change.")

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    try:
        before = query_b0(ctrl)
        if not before:
            print("ERROR: 0xB0 query returned no data.")
            return

        print_snapshot("BEFORE", before)

        input("\n>>> Toggle the setting in SteelSeries GG, then press Enter to re-query...")

        after = query_b0(ctrl)
        if not after:
            print("ERROR: 0xB0 query returned no data after change.")
            return

        print_snapshot("AFTER", after)
        print("\n=== DIFF ===")
        print_diff(before, after)

    finally:
        ctrl.close()


if __name__ == "__main__":
    main()
