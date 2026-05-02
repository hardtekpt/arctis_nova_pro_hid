"""
ANC/Transparency write-command probe.

Sends a single write packet to the device, queries 0xB0 before and after to
detect whether ANC mode changed, and drains any events that fire in response.

Usage:
  python src/probe_write.py --cmd 0xBD --param 0x01   # try 0xBD → transparency
  python src/probe_write.py --cmd 0xBD --param 0x00   # try 0xBD → off
  python src/probe_write.py --cmd 0xBD --param 0x02   # try 0xBD → ANC
  python src/probe_write.py --cmd 0xB9 --param 0x05   # try transparency level 5
  python src/probe_write.py --cmd 0xBE --param 0x01 --no-save

Candidates to try (in order):
  0xBD  same byte as the incoming event (SteelSeries often mirrors read/write)
  0xBE  adjacent, listed as unknown probe candidate in TestChecklist
  0xBC  adjacent below
  0xB9  transparency level event — may be writable (0x37 mic vol is bidirectional)
"""

import argparse
import sys
import time
from pathlib import Path

import hid

# Allow `from listen import ...` when running as `python src/probe_write.py`
sys.path.insert(0, str(Path(__file__).parent))

from listen import (  # noqa: E402
    ARCTIS_NOVA_PRO_PIDS,
    COMMAND_INTERFACE,
    PACKET_SIZE,
    REPORT_ID,
    STEELSERIES_VID,
    USAGE_CONTROL,
    USAGE_EVENTS,
    _raw,
    build_query,
    decode_packet,
    find_handles,
)

ANC_LABELS = {0x00: "off", 0x01: "transparency", 0x02: "anc"}

CMD_SAVE   = 0x09
CMD_STATUS = 0xB0

WRITE_DELAY = 0.20   # seconds: between write and save, and save and re-query
EVENT_WINDOW = 0.35  # seconds: drain events after write


def build_write(cmd: int, param: int) -> bytes:
    pkt = bytearray(PACKET_SIZE)
    pkt[0] = REPORT_ID
    pkt[1] = cmd
    pkt[2] = param
    return bytes(pkt)


def query_b0(ctrl) -> list[int] | None:
    ctrl.write(list(build_query(CMD_STATUS)))
    time.sleep(0.10)
    data = ctrl.read(PACKET_SIZE, 200)
    return list(data) if data else None


def drain(dev, window_s: float, label: str) -> list[list[int]]:
    """Collect all readable packets from dev within window_s seconds."""
    packets: list[list[int]] = []
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        data = dev.read(PACKET_SIZE, 40)
        if data:
            packets.append(list(data))
    return packets


def anc_label(raw: int) -> str:
    return ANC_LABELS.get(raw, f"unknown(0x{raw:02X})")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arctis Nova Pro — single write-command probe"
    )
    parser.add_argument(
        "--cmd",
        required=True,
        type=lambda x: int(x, 0),
        metavar="BYTE",
        help="Command byte to test (e.g. 0xBD)",
    )
    parser.add_argument(
        "--param",
        required=True,
        type=lambda x: int(x, 0),
        metavar="BYTE",
        help="Parameter byte at position [2] (e.g. 0x01 = transparency)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip the 0x09 save command after writing",
    )
    args = parser.parse_args()

    ctrl_path, evt_path, device_name = find_handles()
    if not ctrl_path:
        print("ERROR: Control handle (0xFFC0) not found — is the base station plugged in?")
        sys.exit(1)

    print(f"Device : {device_name}")
    print(f"[PROBE ] cmd=0x{args.cmd:02X}  param=0x{args.param:02X}"
          f"{'  (no-save)' if args.no_save else ''}")
    print()

    ctrl = hid.device()
    ctrl.open_path(ctrl_path)
    ctrl.set_nonblocking(1)

    evt = None
    if evt_path:
        evt = hid.device()
        evt.open_path(evt_path)
        evt.set_nonblocking(1)

    try:
        # ── Baseline ─────────────────────────────────────────────────────────
        before = query_b0(ctrl)
        if before and len(before) > 11:
            anc_before = before[10]
            print(f"[BEFORE] 0xB0[10] = 0x{anc_before:02X} ({anc_label(anc_before)})"
                  f"  oled_brightness={before[11]}")
        else:
            print(f"[BEFORE] 0xB0 query failed or short: {before}")
            anc_before = None

        # ── Write ─────────────────────────────────────────────────────────────
        write_pkt = build_write(args.cmd, args.param)
        print(f"[WRITE ] sent [{_raw(write_pkt[:8])} ...]")
        ctrl.write(list(write_pkt))

        # ── Drain events during wait window ───────────────────────────────────
        time.sleep(WRITE_DELAY)
        if evt:
            for e in drain(evt, EVENT_WINDOW, "EVT  "):
                decoded = decode_packet(e, "EVT  ")
                tag = decoded.strip() if decoded else f"RAW: {_raw(e)}"
                print(f"[EVENT ] {tag}")
        # Also drain any unsolicited ctrl packets
        for _ in range(6):
            d = ctrl.read(PACKET_SIZE, 30)
            if d:
                decoded = decode_packet(list(d), "CTRL ")
                tag = decoded.strip() if decoded else f"RAW: {_raw(list(d))}"
                print(f"[CTRL  ] {tag}")

        # ── Save ──────────────────────────────────────────────────────────────
        if not args.no_save:
            print(f"[SAVE  ] sent 0x{CMD_SAVE:02X}")
            ctrl.write(list(build_query(CMD_SAVE)))
            time.sleep(WRITE_DELAY)

        # ── Re-query ──────────────────────────────────────────────────────────
        after = query_b0(ctrl)
        if after and len(after) > 11:
            anc_after = after[10]
            if anc_before is not None:
                changed = anc_after != anc_before
                marker = "  ✅ CHANGED" if changed else "  (unchanged)"
            else:
                marker = ""
            print(f"[AFTER ] 0xB0[10] = 0x{anc_after:02X} ({anc_label(anc_after)}){marker}")
        else:
            print(f"[AFTER ] 0xB0 query failed: {after}")

    finally:
        ctrl.close()
        if evt:
            evt.close()


if __name__ == "__main__":
    main()
