"""
Full opcode query scanner.

Sends [0x06, CMD, 0x00, 0x00×61] for every opcode 0x00–0xFF on Col01 and logs
which ones return a non-trivial response. Discovers undiscovered query commands.

Usage:
  python scripts/probe_query_scan.py
  python scripts/probe_query_scan.py --delay 0.15   # slower, more reliable
  python scripts/probe_query_scan.py --start 0x80   # scan from a specific opcode

Expected hits: 0xB0, 0x20, 0x10, 0x12, 0x80 (already confirmed). Any NEW hit
is an undiscovered query command — use probe_full_diff.py to decode its fields.

Reset detection: if a command causes the base station to disconnect, the script
logs the offending opcode, waits for the device to reconnect, checks whether the
firmware version changed, and continues scanning from the next opcode.

Total scan time: ~31 s at default 120 ms delay (plus reconnect pauses).
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

KNOWN_QUERY_CMDS = {0xB0, 0x20, 0x10, 0x12, 0x80}

RECONNECT_TIMEOUT_S = 30.0
RECONNECT_POLL_S = 0.5


def _is_interesting(data: list[int], cmd: int) -> bool:
    if len(data) < 3:
        return False
    if data[1] != cmd:
        return False
    return any(b != 0 for b in data[2:])


def _hex_dump(data: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def _query_firmware(ctrl: hid.device) -> str:
    """Send a 0x10 firmware query and return the version string, or '<unknown>'."""
    pkt = bytearray(PACKET_SIZE)
    pkt[0] = REPORT_ID
    pkt[1] = 0x10
    try:
        ctrl.write(list(pkt))
        time.sleep(0.15)
        for _ in range(4):
            data = ctrl.read(PACKET_SIZE, 50)
            if data and list(data)[1] == 0x10:
                raw = bytes(list(data)[2:])
                return raw.split(b"\x00")[0].decode("ascii", errors="replace")
    except OSError:
        pass
    return "<unknown>"


def _reconnect() -> hid.device:
    """
    Block until the base station reappears on USB and return a re-opened Col01 handle.
    Raises RuntimeError if the device does not come back within RECONNECT_TIMEOUT_S.
    """
    deadline = time.time() + RECONNECT_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(RECONNECT_POLL_S)
        ctrl_path, _, _ = find_handles()
        if ctrl_path:
            dev = hid.device()
            try:
                dev.open_path(ctrl_path)
                dev.set_nonblocking(1)
                return dev
            except OSError:
                pass  # appeared but vanished again — keep polling
    raise RuntimeError(
        f"Base station did not reconnect within {RECONNECT_TIMEOUT_S:.0f}s"
    )


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
    print("KNOWN = already confirmed query  |  RESPONSIVE = new hit  |  . = no response")
    print("RESET = command caused a device disconnect\n")

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    baseline_firmware = _query_firmware(ctrl)
    print(f"Firmware (baseline): {baseline_firmware}\n")

    responsive: list[tuple[int, list[int]]] = []
    reset_cmds: list[int] = []

    for cmd in range(args.start, args.end + 1):
        pkt = bytearray(PACKET_SIZE)
        pkt[0] = REPORT_ID
        pkt[1] = cmd

        # --- send the query ---
        disconnected = False
        try:
            ctrl.write(list(pkt))
            time.sleep(args.delay)
        except OSError as exc:
            disconnected = True
            print(f"\n[RESET] 0x{cmd:02X} caused a disconnect on write: {exc}")

        # --- drain response (skip if already disconnected) ---
        response: list[int] | None = None
        if not disconnected:
            try:
                for _ in range(4):
                    data = ctrl.read(PACKET_SIZE, 50)
                    if data:
                        d = list(data)
                        if _is_interesting(d, cmd):
                            response = d
                            break
            except OSError as exc:
                disconnected = True
                print(f"\n[RESET] 0x{cmd:02X} caused a disconnect on read: {exc}")

        # --- handle disconnect ---
        if disconnected:
            reset_cmds.append(cmd)
            try:
                ctrl.close()
            except Exception:
                pass

            print(f"    Waiting for base station to reconnect (up to {RECONNECT_TIMEOUT_S:.0f}s)...")
            try:
                ctrl = _reconnect()
            except RuntimeError as exc:
                print(f"    ERROR: {exc}")
                print("    Aborting scan.")
                break

            new_fw = _query_firmware(ctrl)
            if new_fw != baseline_firmware:
                print(f"    [FW CHANGED] {baseline_firmware!r} → {new_fw!r}")
            else:
                print(f"    Firmware unchanged: {new_fw!r}")
            print(f"    Resuming from 0x{cmd + 1:02X}...", flush=True)
            continue

        # --- classify response ---
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

    try:
        ctrl.close()
    except Exception:
        pass

    print("\n\n" + "=" * 60)

    if reset_cmds:
        print(f"Commands that caused a RESET ({len(reset_cmds)}):")
        for c in reset_cmds:
            print(f"  0x{c:02X}")
        print()

    if responsive:
        print(f"NEW query commands found ({len(responsive)}):")
        for cmd, data in responsive:
            print(f"  0x{cmd:02X}  full response: {_hex_dump(data)}")
        print("\nNext step: run probe_full_diff.py while toggling each target setting")
        print("to map which byte in each new response encodes which setting.")
    else:
        print("No new query commands found beyond the known ones.")
        print("The remaining unknowns are likely in unmapped bytes of 0xB0 / 0x20.")
        print("Run probe_full_diff.py and toggle each setting in GG to locate them.")


if __name__ == "__main__":
    main()
