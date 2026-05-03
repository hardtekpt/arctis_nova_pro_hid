"""
Dual 0xB0 + 0x20 before/after full-byte diff tool.

Queries BOTH the 0xB0 (status) and 0x20 (mic/EQ) responses, diffs all bytes
after you toggle a setting in SteelSeries GG. Catches settings that live in
currently-unmapped bytes of either response.

Usage:
  python scripts/probe_full_diff.py

Workflow:
  1. Script queries 0xB0 and 0x20, prints all bytes of both (BEFORE).
  2. Toggle ONE target setting in SteelSeries GG.
  3. Press Enter.
  4. Script re-queries both, prints diffs for each response.

Run once per setting: BT default, auto-mute, audio output, dim screen,
home screen, mic LED brightness, auto off.
"""

import sys
import time
from pathlib import Path

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import (  # noqa: E402
    PACKET_SIZE,
    build_query,
    find_handles,
)

QUERY_CMDS = [
    (0xB0, "0xB0 status"),
    (0x20, "0x20 mic/EQ"),
]


def query_cmd(ctrl, cmd: int) -> list[int] | None:
    ctrl.write(list(build_query(cmd)))
    time.sleep(0.15)
    data = ctrl.read(PACKET_SIZE, 300)
    return list(data) if data else None


def print_snapshot(label: str, cmd_label: str, data: list[int]) -> None:
    print(f"\n  {label} — {cmd_label} ({len(data)} bytes)")
    print("    idx  hex  dec")
    for i, b in enumerate(data):
        print(f"    [{i:02d}]  {b:02X}   {b:3d}")


def print_diff(cmd_label: str, before: list[int], after: list[int]) -> None:
    changed = [
        (i, before[i], after[i])
        for i in range(min(len(before), len(after)))
        if before[i] != after[i]
    ]
    print(f"\n  === DIFF {cmd_label} ===")
    if not changed:
        print("    (no bytes changed)")
        return
    print(f"    {len(changed)} byte(s) changed:")
    print("    idx  before  after")
    for i, b, a in changed:
        print(f"    [{i:02d}]  0x{b:02X}={b:3d}  →  0x{a:02X}={a:3d}  *** CHANGED ***")


def main() -> None:
    ctrl_path, _, device_name = find_handles()
    if not ctrl_path:
        print("ERROR: Control handle (0xFFC0) not found — is the base station plugged in?")
        sys.exit(1)

    print(f"Device : {device_name}")
    print("Diffs ALL bytes of 0xB0 (status) AND 0x20 (mic/EQ) before/after a GG change.")
    print("Run once per unknown setting; toggle only ONE setting between prompts.\n")

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    try:
        before: dict[int, list[int]] = {}
        for cmd, label in QUERY_CMDS:
            data = query_cmd(ctrl, cmd)
            if not data:
                print(f"ERROR: {label} query returned no data.")
                return
            before[cmd] = data
            print_snapshot("BEFORE", label, data)

        input("\n>>> Toggle the setting in SteelSeries GG, then press Enter to re-query...")

        after: dict[int, list[int]] = {}
        for cmd, label in QUERY_CMDS:
            data = query_cmd(ctrl, cmd)
            if not data:
                print(f"ERROR: {label} query returned no data after change.")
                return
            after[cmd] = data
            print_snapshot("AFTER ", label, data)

        print("\n" + "=" * 60)
        for cmd, label in QUERY_CMDS:
            print_diff(label, before[cmd], after[cmd])

    finally:
        ctrl.close()


if __name__ == "__main__":
    main()
