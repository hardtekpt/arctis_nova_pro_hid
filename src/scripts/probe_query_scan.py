"""
Full opcode query scanner.

Sends [0x06, CMD, 0x00, 0x00×61] for every opcode 0x00–0xFF on Col01 and logs
which ones return a non-trivial response. Discovers undiscovered query commands.

Usage:
  python scripts/probe_query_scan.py
  python scripts/probe_query_scan.py --delay 0.15   # slower, more reliable
  python scripts/probe_query_scan.py --start 0x80   # scan from a specific opcode

Expected hits: 0xB0, 0x20, 0x10, 0x12 (already confirmed). Any NEW hit is an
undiscovered query command — use probe_full_diff.py to decode its byte fields.

Total scan time: ~31 s at default 120 ms delay.
"""

import argparse
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

KNOWN_QUERY_CMDS = {0xB0, 0x20, 0x10, 0x12}

# Responses are "interesting" if:
#  - byte[1] is non-zero (not an empty/noise packet)
#  - at least one byte in [2..63] is non-zero (has payload beyond the opcode echo)
def _is_interesting(data: list[int], cmd: int) -> bool:
    if len(data) < 3:
        return False
    if data[1] != cmd:
        return False
    return any(b != 0 for b in data[2:])


def _hex_dump(data: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arctis Nova Pro — full opcode query scanner"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.12,
        metavar="SECS",
        help="Seconds to wait for response after each query (default: 0.12)",
    )
    parser.add_argument(
        "--start",
        type=lambda x: int(x, 0),
        default=0x00,
        metavar="BYTE",
        help="First opcode to scan (default: 0x00)",
    )
    parser.add_argument(
        "--end",
        type=lambda x: int(x, 0),
        default=0xFF,
        metavar="BYTE",
        help="Last opcode to scan, inclusive (default: 0xFF)",
    )
    args = parser.parse_args()

    ctrl_path, _, device_name = find_handles()
    if not ctrl_path:
        print("ERROR: Control handle (0xFFC0) not found — is the base station plugged in?")
        sys.exit(1)

    total = args.end - args.start + 1
    est_s = total * args.delay
    print(f"Device : {device_name}")
    print(f"Scanning opcodes 0x{args.start:02X}–0x{args.end:02X}  ({total} opcodes, ~{est_s:.0f}s)")
    print("KNOWN = already confirmed query  |  RESPONSIVE = new hit  |  . = no response\n")

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    responsive: list[tuple[int, list[int]]] = []

    try:
        for cmd in range(args.start, args.end + 1):
            pkt = bytearray(PACKET_SIZE)
            pkt[0] = REPORT_ID
            pkt[1] = cmd
            ctrl.write(list(pkt))
            time.sleep(args.delay)

            # Drain: read all buffered packets (device may echo + respond)
            response: list[int] | None = None
            for _ in range(4):
                data = ctrl.read(PACKET_SIZE, 50)
                if data:
                    d = list(data)
                    if _is_interesting(d, cmd):
                        response = d
                        break

            if cmd in KNOWN_QUERY_CMDS:
                status = f"KNOWN:      0x{cmd:02X}"
                if response:
                    status += f"  [{_hex_dump(response[:20])} ...]"
                print(status)
            elif response:
                line = f"RESPONSIVE: 0x{cmd:02X}  [{_hex_dump(response)}]"
                print(line)
                responsive.append((cmd, response))
            else:
                print(".", end="", flush=True)

    finally:
        ctrl.close()

    print("\n\n" + "=" * 60)
    if responsive:
        print(f"NEW query commands found ({len(responsive)}):")
        for cmd, data in responsive:
            print(f"  0x{cmd:02X}  full response: {_hex_dump(data)}")
        print("\nNext step: run probe_full_diff.py while toggling each target setting")
        print("to map which byte in each new response encodes which setting.")
    else:
        print("No new query commands found beyond the 4 known ones.")
        print("The 7 missing settings are likely in unmapped bytes of 0xB0 / 0x20.")
        print("Run probe_full_diff.py and toggle each setting in GG to locate them.")


if __name__ == "__main__":
    main()
