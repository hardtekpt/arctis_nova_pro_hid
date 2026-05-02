import argparse
import sys
import time
from pathlib import Path

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import (
    PACKET_SIZE,
    REPORT_ID,
    build_query,
    decode_packet,
    find_handles,
    _raw,
)

CMD_SAVE = 0x09
CMD_STATUS = 0xB0

WRITE_DELAY = 0.20
EVENT_WINDOW = 0.35


def build_write(cmd: int, data: list[int]) -> bytes:
    pkt = bytearray(PACKET_SIZE)
    pkt[0] = REPORT_ID
    pkt[1] = cmd

    for i, val in enumerate(data):
        if 2 + i < PACKET_SIZE:
            pkt[2 + i] = val

    return bytes(pkt)


def query_b0(ctrl):
    ctrl.write(list(build_query(CMD_STATUS)))
    time.sleep(0.10)
    data = ctrl.read(PACKET_SIZE, 200)
    return list(data) if data else None


def drain(dev, window_s: float):
    packets = []
    deadline = time.monotonic() + window_s
    while time.monotonic() < deadline:
        data = dev.read(PACKET_SIZE, 40)
        if data:
            packets.append(list(data))
    return packets


def parse_data_arg(data_str: str) -> list[int]:
    return [int(x, 0) for x in data_str.split(",")]


def main():
    parser = argparse.ArgumentParser(
        description="Arctis Nova Pro — multi-byte write probe"
    )

    parser.add_argument(
        "--cmd",
        required=True,
        type=lambda x: int(x, 0),
        help="Command byte (e.g. 0x47)",
    )

    parser.add_argument(
        "--param",
        type=lambda x: int(x, 0),
        help="Single parameter (fallback)",
    )

    parser.add_argument(
        "--data",
        type=str,
        help="Comma-separated byte list (e.g. 80,0,40,60)",
    )

    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip save command",
    )

    args = parser.parse_args()

    # Resolve payload
    if args.data:
        payload = parse_data_arg(args.data)
    elif args.param is not None:
        payload = [args.param]
    else:
        print("ERROR: provide --param or --data")
        sys.exit(1)

    ctrl_path, evt_path, device_name = find_handles()

    if not ctrl_path:
        print("ERROR: Control handle not found")
        sys.exit(1)

    print(f"Device : {device_name}")
    print(f"[PROBE ] cmd=0x{args.cmd:02X}  data={payload}")
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
        # BEFORE
        before = query_b0(ctrl)
        if before:
            print(f"[BEFORE] {_raw(before)}")

        # WRITE
        pkt = build_write(args.cmd, payload)
        print(f"[WRITE ] {_raw(pkt[:16])} ...")
        ctrl.write(list(pkt))

        # EVENTS
        time.sleep(WRITE_DELAY)

        if evt:
            for e in drain(evt, EVENT_WINDOW):
                decoded = decode_packet(e, "EVT  ")
                print(f"[EVENT ] {decoded or _raw(e)}")

        # CTRL drain
        for _ in range(6):
            d = ctrl.read(PACKET_SIZE, 30)
            if d:
                decoded = decode_packet(list(d), "CTRL ")
                print(f"[CTRL  ] {decoded or _raw(list(d))}")

        # SAVE
        if not args.no_save:
            print("[SAVE  ]")
            ctrl.write(list(build_query(CMD_SAVE)))
            time.sleep(WRITE_DELAY)

        # AFTER
        after = query_b0(ctrl)
        if after:
            print(f"[AFTER ] {_raw(after)}")

            if before:
                diffs = [
                    (i, before[i], after[i])
                    for i in range(min(len(before), len(after)))
                    if before[i] != after[i]
                ]
                if diffs:
                    for i, b, a in diffs:
                        print(f"[DIFF  ] byte[{i}]: {b:02X} -> {a:02X}")
                else:
                    print("[DIFF  ] no change")

    finally:
        ctrl.close()
        if evt:
            evt.close()


if __name__ == "__main__":
    main()