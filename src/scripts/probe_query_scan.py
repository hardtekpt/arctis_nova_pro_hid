"""
Full opcode query scanner.

Sends [0x06, CMD, 0x00, 0x00×61] for every opcode 0x00–0xFF on Col01 and logs
which ones return a non-trivial response. Discovers undiscovered query commands.

Usage:
  python scripts/probe_query_scan.py
  python scripts/probe_query_scan.py --delay 0.15         # slower, more reliable
  python scripts/probe_query_scan.py --start 0x80         # scan from a specific opcode
  python scripts/probe_query_scan.py --check-settings     # detect per-opcode mutations

Expected hits: 0xB0, 0x20, 0x10, 0x12, 0x80 (already confirmed). Any NEW hit
is an undiscovered query command — use probe_full_diff.py to decode its fields.

Reset detection: if a command causes the base station to disconnect, the script
logs the offending opcode, waits for the device to reconnect, checks whether the
firmware version changed, and continues scanning from the next opcode.

Settings tracking (--check-settings): after every probe the script queries
0xB0/0x20/0x80 and diffs the response against the previous snapshot. Opcodes
that silently mutate a setting without returning data are labelled MUTATING.
A full per-command settings-change table is printed at the end.
Adds ~0.3 s overhead per opcode (~77 s extra over a full 256-opcode scan).

Total scan time: ~31 s at default 120 ms delay (plus reconnect/snapshot pauses).
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
SNAPSHOT_DELAY_S = 0.10  # per-query pause when taking a settings snapshot

_TIMEOUT_STEPS = {
    0: "off", 1: "1 min", 2: "5 min",
    3: "10 min", 4: "15 min", 5: "30 min", 6: "60 min",
}

# Each entry: (query_cmd, byte_index, field_name, value_formatter)
_SETTINGS_FIELDS = [
    # ── 0xB0 status ──────────────────────────────────────────────────────────
    (0xB0,  2, "bt_default",         lambda v: {0: "off", 1: "on"}.get(v, f"0x{v:02X}")),
    (0xB0,  3, "bt_auto_mute",       lambda v: {0: "off", 1: "-12 dB", 2: "full"}.get(v, f"0x{v:02X}")),
    (0xB0,  4, "connectivity",       lambda v: {0x01: "2.4 GHz only", 0x04: "2.4 GHz + BT"}.get(v, f"0x{v:02X}")),
    (0xB0,  5, "bt_state",           lambda v: {0: "off", 1: "active"}.get(v, f"0x{v:02X}")),
    (0xB0,  6, "headset_battery",    lambda v: f"{min(100, v / 8 * 100):.0f}%"),
    (0xB0,  7, "dock_battery",       lambda v: f"{min(100, v / 8 * 100):.0f}%"),
    (0xB0,  8, "transparency_lvl",   str),
    (0xB0,  9, "mic_mute",           lambda v: {0: "unmuted", 1: "muted"}.get(v, f"0x{v:02X}")),
    (0xB0, 10, "anc_mode",           lambda v: {0: "off", 1: "transparency", 2: "ANC"}.get(v, f"0x{v:02X}")),
    (0xB0, 11, "mic_led_brightness", str),
    (0xB0, 12, "auto_off_timeout",   lambda v: _TIMEOUT_STEPS.get(v, f"0x{v:02X}")),
    (0xB0, 13, "wireless_mode",      lambda v: {0: "performance", 1: "extended range"}.get(v, f"0x{v:02X}")),
    # ── 0x20 mic/EQ ──────────────────────────────────────────────────────────
    (0x20,  3, "headset_volume",     lambda v: f"{max(0, min(100, (0x38 - v) / 56 * 100)):.0f}%"),
    (0x20,  4, "gain",               lambda v: {1: "low", 2: "high"}.get(v, f"0x{v:02X}")),
    (0x20,  6, "eq_preset",          lambda v: "custom" if v == 0x04 else f"preset 0x{v:02X}"),
    (0x20,  7, "eq_band_1",          str),
    (0x20,  8, "eq_band_2",          str),
    (0x20,  9, "eq_band_3",          str),
    (0x20, 10, "eq_band_4",          str),
    (0x20, 11, "eq_band_5",          str),
    (0x20, 12, "eq_band_6",          str),
    (0x20, 13, "eq_band_7",          str),
    (0x20, 14, "eq_band_8",          str),
    (0x20, 15, "eq_band_9",          str),
    (0x20, 16, "eq_band_10",         str),
    (0x20, 17, "mic_volume",         str),
    (0x20, 18, "sidetone",           lambda v: {0: "off", 1: "low", 2: "medium", 3: "high"}.get(v, f"0x{v:02X}")),
    (0x20, 19, "audio_output",       lambda v: {1: "speakers", 2: "stream"}.get(v, f"0x{v:02X}")),
    (0x20, 20, "chatmix_game",       str),
    (0x20, 21, "chatmix_chat",       str),
    (0x20, 22, "stream_main_vol",    str),
    (0x20, 24, "stream_aux_vol",     str),
    (0x20, 25, "stream_mic_vol",     str),
    # ── 0x80 base-station display ────────────────────────────────────────────
    (0x80,  2, "dim_timeout",        lambda v: _TIMEOUT_STEPS.get(v, f"0x{v:02X}")),
    (0x80,  3, "oled_brightness",    str),
    (0x80,  5, "home_screen",        lambda v: {0: "detailed", 1: "simple"}.get(v, f"0x{v:02X}")),
]


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


def _snapshot_settings(ctrl: hid.device) -> dict[int, list[int]]:
    """Query 0xB0, 0x20, and 0x80; return {cmd: raw_response_bytes}."""
    snap: dict[int, list[int]] = {}
    for cmd in (0xB0, 0x20, 0x80):
        pkt = bytearray(PACKET_SIZE)
        pkt[0] = REPORT_ID
        pkt[1] = cmd
        try:
            ctrl.write(list(pkt))
            time.sleep(SNAPSHOT_DELAY_S)
            for _ in range(4):
                data = ctrl.read(PACKET_SIZE, 50)
                if data and list(data)[1] == cmd:
                    snap[cmd] = list(data)
                    break
        except OSError:
            pass
    return snap


def _diff_settings(
    before: dict[int, list[int]],
    after: dict[int, list[int]],
) -> list[tuple[str, str, str]]:
    """Return (field_name, before_str, after_str) for every byte that changed."""
    changes = []
    for query_cmd, idx, label, fmt in _SETTINGS_FIELDS:
        b_data = before.get(query_cmd, [])
        a_data = after.get(query_cmd, [])
        if len(b_data) <= idx or len(a_data) <= idx:
            continue
        bv, av = b_data[idx], a_data[idx]
        if bv != av:
            changes.append((label, fmt(bv), fmt(av)))
    return changes


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
    parser.add_argument(
        "--check-settings",
        action="store_true",
        help=(
            "After each probe, query 0xB0/0x20/0x80 and diff against the previous "
            "snapshot to detect which settings the opcode mutated. Silent opcodes "
            "that change settings are labelled MUTATING. Adds ~0.3 s per opcode."
        ),
    )
    args = parser.parse_args()

    ctrl_path, _, device_name = find_handles()
    if not ctrl_path:
        print("ERROR: Control handle (0xFFC0) not found — is the base station plugged in?")
        sys.exit(1)

    total = args.end - args.start + 1
    est_s = total * (args.delay + (3 * SNAPSHOT_DELAY_S if args.check_settings else 0))
    print(f"Device : {device_name}")
    print(f"Scanning opcodes 0x{args.start:02X}–0x{args.end:02X}  ({total} opcodes, ~{est_s:.0f}s)")
    print("KNOWN    = already confirmed query  |  RESPONSIVE = new hit")
    print("MUTATING = silently changed a setting (no response data)")
    print("RESET    = caused a disconnect       |  .          = no response, no change\n")

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    baseline_firmware = _query_firmware(ctrl)
    print(f"Firmware (baseline): {baseline_firmware}\n")

    # Rolling settings snapshot: after_n becomes before_{n+1}.
    current_snap: dict[int, list[int]] = {}
    if args.check_settings:
        print("Taking initial settings snapshot...", flush=True)
        current_snap = _snapshot_settings(ctrl)
        print()

    responsive: list[tuple[int, list[int]]] = []
    reset_cmds: list[int] = []
    mutating_cmds: list[int] = []
    # cmd → [(field_name, before_str, after_str), ...]
    setting_changes: dict[int, list[tuple[str, str, str]]] = {}

    mid_dots = False  # True while dots have been printed without a trailing newline

    def _nl() -> None:
        nonlocal mid_dots
        if mid_dots:
            print()
            mid_dots = False

    try:
        for cmd in range(args.start, args.end + 1):
            pkt = bytearray(PACKET_SIZE)
            pkt[0] = REPORT_ID
            pkt[1] = cmd

            # ── send probe ───────────────────────────────────────────────────
            disconnected = False
            try:
                ctrl.write(list(pkt))
                time.sleep(args.delay)
            except OSError as exc:
                disconnected = True
                _nl()
                print(f"[RESET] 0x{cmd:02X} caused a disconnect on write: {exc}")

            # ── drain response ───────────────────────────────────────────────
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
                    _nl()
                    print(f"[RESET] 0x{cmd:02X} caused a disconnect on read: {exc}")

            # ── handle disconnect ────────────────────────────────────────────
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

                if args.check_settings:
                    new_snap = _snapshot_settings(ctrl)
                    changes = _diff_settings(current_snap, new_snap)
                    if changes:
                        setting_changes[cmd] = changes
                        print(f"    {len(changes)} setting(s) changed after reset:")
                        for name, bv, av in changes:
                            print(f"      {name}: {bv} → {av}")
                    current_snap = new_snap

                print(f"    Resuming from 0x{cmd + 1:02X}...", flush=True)
                continue

            # ── settings snapshot ────────────────────────────────────────────
            changes: list[tuple[str, str, str]] = []
            if args.check_settings:
                new_snap = _snapshot_settings(ctrl)
                changes = _diff_settings(current_snap, new_snap)
                if changes:
                    setting_changes[cmd] = changes
                current_snap = new_snap

            # ── classify and print ───────────────────────────────────────────
            change_tag = f"  ← {len(changes)} setting(s) changed" if changes else ""

            if cmd in KNOWN_QUERY_CMDS:
                _nl()
                line = f"KNOWN:      0x{cmd:02X}"
                if response:
                    line += f"  [{_hex_dump(response[:20])} ...]"
                print(line + change_tag)

            elif response:
                _nl()
                print(f"RESPONSIVE: 0x{cmd:02X}  [{_hex_dump(response)}]" + change_tag)
                responsive.append((cmd, response))

            elif changes:
                _nl()
                print(f"MUTATING:   0x{cmd:02X}" + change_tag)
                mutating_cmds.append(cmd)

            else:
                print(".", end="", flush=True)
                mid_dots = True

    finally:
        _nl()
        try:
            ctrl.close()
        except Exception:
            pass

    print("\n" + "=" * 60)

    if reset_cmds:
        print(f"\nCommands that caused a RESET ({len(reset_cmds)}):")
        for c in reset_cmds:
            print(f"  0x{c:02X}")

    if mutating_cmds:
        print(f"\nCommands that silently MUTATED settings ({len(mutating_cmds)}):")
        for c in mutating_cmds:
            print(f"  0x{c:02X}")

    if responsive:
        print(f"\nNEW query commands found ({len(responsive)}):")
        for cmd, data in responsive:
            print(f"  0x{cmd:02X}  full response: {_hex_dump(data)}")
        print("\nNext step: run probe_full_diff.py while toggling each target setting")
        print("to map which byte in each new response encodes which setting.")
    else:
        print("\nNo new query commands found beyond the known ones.")
        print("The remaining unknowns are likely in unmapped bytes of 0xB0 / 0x20.")
        print("Run probe_full_diff.py and toggle each setting in GG to locate them.")

    if setting_changes:
        print(f"\n{'=' * 60}")
        print(f"SETTINGS CHANGES PER COMMAND ({len(setting_changes)} commands affected settings):\n")
        for cmd in sorted(setting_changes.keys()):
            kind = (
                "RESET"     if cmd in reset_cmds    else
                "MUTATING"  if cmd in mutating_cmds else
                "KNOWN"     if cmd in KNOWN_QUERY_CMDS else
                "RESPONSIVE"
            )
            print(f"  0x{cmd:02X}  [{kind}]")
            for name, bv, av in setting_changes[cmd]:
                print(f"    {name}: {bv} → {av}")
            print()
    elif args.check_settings:
        print("\nNo settings changes detected across all scanned opcodes.")


if __name__ == "__main__":
    main()
