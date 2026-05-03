"""
Parse a Wireshark USB capture of GG Engine ↔ Arctis Nova Pro traffic.

Decodes both directions:
  GG → DEV  host-to-device Interrupt OUT — GG's write and query commands
  DEV → GG  device-to-host Interrupt IN  — responses and unsolicited events

Supported input formats:
  .json     Wireshark JSON export (File → Export Packet Dissections → As JSON)
            No extra Python dependencies beyond stdlib.
  .pcapng   Raw Wireshark capture file.
  .pcap     Raw Wireshark capture file.
            Both pcapng/pcap require: pip install pyshark
            pyshark wraps tshark; Wireshark must be installed with tshark.

Usage:
  python scripts/parse_gg_capture.py capture.json
  python scripts/parse_gg_capture.py capture.pcapng
  python scripts/parse_gg_capture.py capture.json --device 3.17
  python scripts/parse_gg_capture.py capture.json --out-only
  python scripts/parse_gg_capture.py capture.json --in-only

How to obtain the capture file:
  See docs/WiresharkCaptureGuide.md for step-by-step instructions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterator

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import _raw, decode_packet  # noqa: E402

# ── Known commands (used to flag undiscovered opcodes from GG) ────────────────

_KNOWN = frozenset({
    # Query commands
    0xB0, 0x20, 0x10, 0x12,
    # Write commands
    0x09, 0x25, 0x27, 0x37, 0x39, 0x43, 0x49,
    0x83, 0x85, 0x89, 0xB2, 0xB3, 0xB9, 0xBD, 0xBF, 0xC1, 0xC3,
    # Device-initiated events (same byte as write)
    0x45, 0x47, 0xBB, 0xB5, 0xB7,
})


# ── Shared helpers ────────────────────────────────────────────────────────────

def _parse_hex_str(s: str) -> list[int]:
    """'06:b0:00' or '06 b0 00' → [6, 176, 0]."""
    sep = ":" if ":" in s else " "
    return [int(b, 16) for b in s.split(sep) if b.strip()]


def _to_int(val: object) -> int | None:
    """Parse '0x00000001', '1', or 1 → int. Returns None on failure."""
    try:
        s = str(val).strip()
        return int(s, 16) if s.startswith(("0x", "0X")) else int(s)
    except (ValueError, TypeError):
        return None


def _print_event(
    ts: str,
    host_to_dev: bool,
    data: list[int],
    new_commands: set[int],
) -> None:
    direction = "GG→DEV" if host_to_dev else "DEV→GG"
    cmd = data[1] if len(data) > 1 else 0x00
    brief = _raw(data[:10]) + (" …" if len(data) > 10 else "")
    decoded = decode_packet(data, direction)

    if decoded:
        print(f"[{ts:>13}] [{direction}] {decoded.strip()}")
    else:
        param = data[2] if len(data) > 2 else 0
        flag = "  *** UNKNOWN ***" if host_to_dev and cmd not in _KNOWN else ""
        print(
            f"[{ts:>13}] [{direction}] 0x{cmd:02X}  param=0x{param:02X}"
            f"  [{brief}]{flag}"
        )

    if host_to_dev and cmd not in _KNOWN:
        new_commands.add(cmd)


# ── JSON parser (stdlib only) ─────────────────────────────────────────────────

def _json_field(layers: dict, key: str) -> str | None:
    """Get a Wireshark JSON field from layers — handles both flat and nested."""
    val = layers.get(key)
    if val and isinstance(val, str):
        return val
    usb = layers.get("usb", {})
    if isinstance(usb, dict):
        val = usb.get(key)
        if val and isinstance(val, str):
            return val
    return None


def _json_direction(layers: dict) -> bool | None:
    """Return True=host→device, False=device→host, None=can't determine."""
    usb = layers.get("usb", {})
    if not isinstance(usb, dict):
        return None
    urb = usb.get("usb.urb_type", "")

    # endpoint direction bit: 0=OUT (host→device), 1=IN (device→host)
    ep_dir: int | None = None
    tree = usb.get("usb.endpoint_address_tree", {})
    if isinstance(tree, dict):
        ep_dir = _to_int(tree.get("usb.endpoint.direction"))
    if ep_dir is None:
        ep_str = usb.get("usb.endpoint_address")
        if ep_str:
            ep = _to_int(ep_str)
            if ep is not None:
                ep_dir = 1 if (ep & 0x80) else 0

    if ep_dir is None:
        return None

    # Submit to OUT endpoint → host is sending data to device
    if urb in ("S", "83", "0x53") and ep_dir == 0:
        return True
    # Complete from IN endpoint → device has sent data to host
    if urb in ("C", "67", "0x43") and ep_dir == 1:
        return False
    return None


def _json_find_device(packets: list[dict]) -> str | None:
    """Scan descriptor packets for SteelSeries VID → return 'bus.addr'."""
    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})
        usb = layers.get("usb", {})
        if not isinstance(usb, dict):
            continue
        vendor = usb.get("usb.idVendor", "")
        if "1038" in vendor.lower():
            bus = usb.get("usb.bus_id", "")
            addr = usb.get("usb.device_address", "")
            if bus and addr:
                return f"{bus}.{addr}"
    return None


def _json_iter(
    packets: list[dict],
    target: str | None,
) -> Iterator[tuple[str, bool, list[int]]]:
    """Yield (timestamp, host_to_dev, data) for every relevant interrupt packet."""
    for pkt in packets:
        layers = pkt.get("_source", {}).get("layers", {})
        usb = layers.get("usb", {})
        if not isinstance(usb, dict):
            continue

        if target:
            bus = usb.get("usb.bus_id", "")
            addr = usb.get("usb.device_address", "")
            if f"{bus}.{addr}" != target:
                continue

        tt = _to_int(usb.get("usb.transfer_type", ""))
        if tt != 0x01:  # 0x01 = Interrupt
            continue

        direction = _json_direction(layers)
        if direction is None:
            continue

        raw = _json_field(layers, "usb.capdata") or _json_field(
            layers, "usb.data_fragment"
        )
        if not raw:
            continue
        try:
            data = _parse_hex_str(raw)
        except ValueError:
            continue
        if len(data) < 2:
            continue

        frame = layers.get("frame", {})
        ts = str(
            frame.get("frame.time_relative", frame.get("frame.time_epoch", "?"))
        )[:13]
        yield ts, direction, data


def parse_json(path: str, target: str | None, only_out: bool, only_in: bool) -> None:
    with open(path, encoding="utf-8") as fh:
        try:
            raw = json.load(fh)
        except json.JSONDecodeError as exc:
            print(f"ERROR: invalid JSON — {exc}")
            print("Export from Wireshark via File → Export Packet Dissections → As JSON.")
            sys.exit(1)

    packets: list[dict] = raw if isinstance(raw, list) else raw.get("packets", [])

    if not target:
        target = _json_find_device(packets)
        if target:
            print(f"Auto-detected SteelSeries device at bus.address: {target}\n")
        else:
            print(
                "Could not auto-detect device address (no descriptor packets in capture).\n"
                "Run  python scripts/find_usb_bus.py  then re-run with --device BUS.ADDR\n"
                "Showing all interrupt traffic (may include non-SteelSeries devices).\n"
            )

    shown = 0
    new_cmds: set[int] = set()
    for ts, h2d, data in _json_iter(packets, target):
        if only_out and not h2d:
            continue
        if only_in and h2d:
            continue
        _print_event(ts, h2d, data, new_cmds)
        shown += 1

    _print_summary(shown, new_cmds)


# ── Pcapng parser (pyshark / tshark) ─────────────────────────────────────────

def _pcap_iter(
    path: str,
    target: str | None,
) -> Iterator[tuple[str, bool, list[int]]]:
    try:
        import pyshark
    except ImportError:
        print("ERROR: pyshark is not installed.  Run:  pip install pyshark")
        print(
            "Alternatively export the capture as JSON from Wireshark:\n"
            "  File → Export Packet Dissections → As JSON\n"
            "Then re-run with the .json file."
        )
        sys.exit(1)

    filt = "usb.transfer_type == 0x01"
    print(f"Opening {path} with pyshark (tshark required)…")
    try:
        cap = pyshark.FileCapture(path, display_filter=filt, keep_packets=False)
    except Exception as exc:
        print(f"ERROR: could not open capture: {exc}")
        sys.exit(1)

    if not target:
        print("Scanning for SteelSeries device address…")
        try:
            scan = pyshark.FileCapture(path, keep_packets=False)
            for pkt in scan:
                try:
                    v = pkt.usb.get_field_value("usb.idVendor") or ""
                    if "1038" in v:
                        target = f"{pkt.usb.bus_id}.{pkt.usb.device_address}"
                        break
                except Exception:
                    continue
            scan.close()
        except Exception:
            pass
        if target:
            print(f"Auto-detected SteelSeries device at: {target}\n")
        else:
            print("Could not auto-detect device address — showing all interrupt traffic.\n")

    try:
        for pkt in cap:
            try:
                bus = pkt.usb.bus_id
                addr = pkt.usb.device_address
                if target and f"{bus}.{addr}" != target:
                    continue

                urb = pkt.usb.urb_type  # 'S' or 'C'
                try:
                    ep = int(pkt.usb.endpoint_address, 16)
                except Exception:
                    continue
                ep_dir = 1 if (ep & 0x80) else 0

                if urb in ("S", "83") and ep_dir == 0:
                    h2d = True
                elif urb in ("C", "67") and ep_dir == 1:
                    h2d = False
                else:
                    continue

                raw = None
                for field in ("capdata", "data_fragment"):
                    try:
                        raw = str(getattr(pkt.usb, field))
                        break
                    except AttributeError:
                        continue
                if not raw:
                    continue
                try:
                    data = _parse_hex_str(raw)
                except ValueError:
                    continue
                if len(data) < 2:
                    continue

                ts = str(pkt.sniff_timestamp)[:13]
                yield ts, h2d, data

            except AttributeError:
                continue
    finally:
        cap.close()


def parse_pcap(path: str, target: str | None, only_out: bool, only_in: bool) -> None:
    shown = 0
    new_cmds: set[int] = set()
    for ts, h2d, data in _pcap_iter(path, target):
        if only_out and not h2d:
            continue
        if only_in and h2d:
            continue
        _print_event(ts, h2d, data, new_cmds)
        shown += 1
    _print_summary(shown, new_cmds)


# ── Summary ───────────────────────────────────────────────────────────────────

def _print_summary(shown: int, new_cmds: set[int]) -> None:
    print()
    print(f"{'─' * 60}")
    print(f"Displayed {shown} interrupt transfer(s).")
    if new_cmds:
        print(f"\n*** {len(new_cmds)} unknown command(s) seen from GG (not in known map): ***")
        for cmd in sorted(new_cmds):
            print(f"  0x{cmd:02X}  — candidate new query or write command")
        print(
            "\nNext step: run probe_write.py or probe_full_diff.py to characterise"
            " each unknown command."
        )
    else:
        print(
            "\nAll commands seen from GG match the known map.\n"
            "If you expected new query commands, confirm the capture contains\n"
            "the GG settings page open/change events (see WiresharkCaptureGuide.md)."
        )


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Decode Wireshark USB capture of GG Engine ↔ Arctis Nova Pro"
    )
    ap.add_argument("capture", help="Capture file (.json or .pcapng/.pcap)")
    ap.add_argument(
        "--device", "-d",
        metavar="BUS.ADDR",
        help="USB bus.device address e.g. 3.17 (auto-detected if omitted)",
    )
    ap.add_argument(
        "--out-only",
        action="store_true",
        help="Show only GG→device packets",
    )
    ap.add_argument(
        "--in-only",
        action="store_true",
        help="Show only device→GG packets",
    )
    args = ap.parse_args()

    p = Path(args.capture)
    if not p.exists():
        print(f"ERROR: file not found: {p}")
        sys.exit(1)

    dir_label = " (GG→DEV only)" if args.out_only else " (DEV→GG only)" if args.in_only else ""
    print(f"File   : {p}")
    print(f"Device : {args.device or '(auto-detect)'}{dir_label}")
    print()

    suf = p.suffix.lower()
    if suf == ".json":
        parse_json(str(p), args.device, args.out_only, args.in_only)
    elif suf in (".pcapng", ".pcap", ".cap"):
        parse_pcap(str(p), args.device, args.out_only, args.in_only)
    else:
        print(f"ERROR: unknown extension '{suf}'. Expected .json, .pcapng, or .pcap.")
        sys.exit(1)


if __name__ == "__main__":
    main()
