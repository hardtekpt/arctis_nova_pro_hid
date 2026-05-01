"""
Phase 1 – HID Command Discovery: Query + Event Listener

Opens both collections on interface 4 of the Arctis Nova Pro base station:
  0xFFC0  (control)  – send query commands, read responses
  0xFF00  (events)   – read incoming device events (buttons, dials, state changes)

Usage:
  python src/listen.py             # send queries at startup then listen
  python src/listen.py --no-query  # listen only (no writes to device)

Interact with the headset (volume wheel, mute button, ANC button, etc.) while
this script is running. All packets are decoded where known and logged to
logs/hid_session_<timestamp>.log for later analysis.
"""

import argparse
import hid
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Device constants ──────────────────────────────────────────────────────────
STEELSERIES_VID = 0x1038

ARCTIS_NOVA_PRO_PIDS = {
    0x12CB: "Arctis Nova Pro Wireless",
    0x12CD: "Arctis Nova Pro Wireless",
    0x12E0: "Arctis Nova Pro Wireless X",
    0x12E5: "Arctis Nova Pro Wireless X",
    0x225D: "Arctis Nova Pro Wireless",
}

COMMAND_INTERFACE = 4
USAGE_CONTROL     = 0xFFC0   # bidirectional: write commands + read responses
USAGE_EVENTS      = 0xFF00   # read-only: incoming device events

REPORT_ID    = 0x06    # outgoing report ID (host → device)
PACKET_SIZE  = 64
POLL_TIMEOUT = 50      # ms per handle per loop tick

# ── Candidate query commands ──────────────────────────────────────────────────
# These originate from the Arctis Nova 7X protocol (closest documented sibling).
# The device response will confirm whether each command is valid on the Nova Pro.
QUERY_COMMANDS = [
    (0xB0, "status        (battery %, charging, game/chat vol, sleep, mute)"),
    (0xA0, "config        (idle timeout, LED brightness)"),
    (0x20, "mic params    (volume, sidetone level, volume limiter)"),
    (0x10, "firmware ver  (ASCII string)"),
    (0x12, "serial number (ASCII string)"),
]

# ── Known incoming event decoders (confirmed on Nova Pro) ────────────────────
ANC_MODES = {0: "off", 1: "transparency", 2: "anc"}


def _raw(data: list[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)


def decode_packet(data: list[int], source: str) -> str | None:
    """Return a human-readable decode string, or None if command is unknown."""
    if len(data) < 2:
        return None

    cmd = data[1]
    tag = f"[{source:5}] 0x{cmd:02X}"

    # ── Confirmed incoming events (docs/HidCommands.md) ──

    if cmd == 0x25 and len(data) > 2:
        raw = data[2]
        pct = round(max(0, min(100, (0x38 - raw) / 56 * 100)))
        return f"{tag}  Volume          → {pct}% (raw=0x{raw:02X})"

    if cmd == 0xB5 and len(data) > 4:
        wireless  = data[4] == 8
        bluetooth = data[3] == 1
        return f"{tag}  Connectivity    → wireless={wireless} bluetooth={bluetooth}"

    if cmd == 0xB7 and len(data) > 3:
        h = round(min(100, data[2] / 8 * 100))
        d = round(min(100, data[3] / 8 * 100))
        return f"{tag}  Battery         → headset={h}% dock={d}%"

    if cmd == 0x85 and len(data) > 2:
        lvl = data[2]
        note = "" if 1 <= lvl <= 10 else " ⚠ out of range"
        return f"{tag}  OLED Brightness → {lvl}/10{note}"

    if cmd == 0x39 and len(data) > 2:
        return f"{tag}  Sidetone        → level={data[2]}"

    if cmd == 0xBD and len(data) > 2:
        mode = ANC_MODES.get(data[2], f"unknown(0x{data[2]:02X})")
        return f"{tag}  ANC Mode        → {mode}"

    if cmd == 0xBB and len(data) > 2:
        muted = data[2] == 1
        return f"{tag}  Mic Mute        → {'muted' if muted else 'unmuted'}"

    # ── Confirmed incoming event: ChatMix dial (Arctis-on-Linux, PID 0x12E0) ──

    if cmd == 0x45 and len(data) > 3:
        return f"{tag}  ChatMix         → game={data[2]} chat={data[3]}"

    # ── Candidate query responses (Nova 7X origin – being verified) ──────────
    # Offsets: data[0]=reportId  data[1]=cmd  data[2+]=payload

    if cmd == 0xB0 and len(data) > 6:
        return (
            f"{tag}  Status          → "
            f"sleep=0x{data[2]:02X}  battery={data[3]}%  "
            f"charging=0x{data[4]:02X}  game_vol={data[5]}  chat_vol={data[6]}"
        )

    if cmd == 0xA0 and len(data) > 3:
        return f"{tag}  Config          → idle_timeout={data[2]}min  led_brightness={data[3]}"

    if cmd == 0x20 and len(data) > 4:
        return f"{tag}  Mic Params      → volume={data[2]}  sidetone={data[3]}  limiter={data[4]}"

    if cmd in (0x10, 0x12) and len(data) > 2:
        label = "Firmware" if cmd == 0x10 else "Serial"
        text = bytes(data[2:]).split(b"\x00")[0].decode("ascii", errors="replace").strip()
        return f"{tag}  {label:<14}  → {text!r}"

    return None  # unknown — caller will print a note alongside the raw line


# ── Device handle discovery ───────────────────────────────────────────────────

def find_handles() -> tuple[bytes | None, bytes | None, str]:
    """Return (control_path, events_path, device_name). Either path may be None."""
    ctrl_path = evt_path = None
    name = "Unknown"

    for d in hid.enumerate():
        if d["vendor_id"] != STEELSERIES_VID:
            continue
        if d["product_id"] not in ARCTIS_NOVA_PRO_PIDS:
            continue
        if d["interface_number"] != COMMAND_INTERFACE:
            continue
        name = ARCTIS_NOVA_PRO_PIDS[d["product_id"]]
        if d["usage_page"] == USAGE_CONTROL:
            ctrl_path = d["path"]
        elif d["usage_page"] == USAGE_EVENTS:
            evt_path = d["path"]

    return ctrl_path, evt_path, name


# ── Packet building ───────────────────────────────────────────────────────────

def build_query(cmd_byte: int) -> bytes:
    pkt = bytearray(PACKET_SIZE)
    pkt[0] = REPORT_ID
    pkt[1] = cmd_byte
    return bytes(pkt)


# ── Logging helpers ───────────────────────────────────────────────────────────

def open_log() -> tuple:
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = log_dir / f"hid_session_{ts}.log"
    return open(path, "w", encoding="utf-8"), path


def log(f, line: str) -> None:
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    full = f"[{ts}] {line}"
    print(full)
    f.write(full + "\n")
    f.flush()


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Arctis Nova Pro HID listener + query tool"
    )
    parser.add_argument(
        "--no-query",
        action="store_true",
        help="Skip sending query commands at startup (listen-only mode)",
    )
    args = parser.parse_args()

    ctrl_path, evt_path, device_name = find_handles()

    if not ctrl_path and not evt_path:
        print("\nNo Arctis Nova Pro device found.")
        print("  • Make sure the base station is plugged in via USB.")
        print(f"  • Known PIDs: {', '.join(f'0x{p:04X}' for p in ARCTIS_NOVA_PRO_PIDS)}")
        sys.exit(1)

    log_f, log_path = open_log()
    print(f"\nDevice : {device_name}")
    print(f"Log    : {log_path}\n")

    ctrl = evt = None

    try:
        if ctrl_path:
            ctrl = hid.device()
            ctrl.open_path(ctrl_path)
            ctrl.set_nonblocking(1)
            path_str = ctrl_path.decode() if isinstance(ctrl_path, bytes) else ctrl_path
            log(log_f, f"[INFO ] Control handle opened  (0xFFC0): {path_str}")
        else:
            log(log_f, "[WARN ] Control handle (0xFFC0) not found – write queries disabled")

        if evt_path:
            evt = hid.device()
            evt.open_path(evt_path)
            evt.set_nonblocking(1)
            path_str = evt_path.decode() if isinstance(evt_path, bytes) else evt_path
            log(log_f, f"[INFO ] Events  handle opened  (0xFF00): {path_str}")
        else:
            log(log_f, "[WARN ] Events handle (0xFF00) not found – event reads may be limited")

        # Send candidate query commands at startup
        if ctrl and not args.no_query:
            log(log_f, "")
            log(log_f, "[INFO ] Sending candidate query commands (Nova 7X origin, verifying on Nova Pro)…")
            for cmd_byte, desc in QUERY_COMMANDS:
                pkt = build_query(cmd_byte)
                log(log_f, f"[QUERY] TX  0x{cmd_byte:02X}  {desc}")
                log(log_f, f"[QUERY]     {_raw(pkt)}")
                ctrl.write(list(pkt))
                time.sleep(0.08)   # give the device time to respond before the next query

        log(log_f, "")
        log(log_f, "[INFO ] Event loop active – interact with the headset. Ctrl+C to stop.")
        log(log_f, "[INFO ] Try: volume wheel, mute button, ANC button, ChatMix dial.")
        log(log_f, "")

        # Poll both handles until the user stops the script
        while True:
            for dev, source in ((ctrl, "CTRL "), (evt, "EVT  ")):
                if dev is None:
                    continue
                data = dev.read(PACKET_SIZE, POLL_TIMEOUT)
                if not data:
                    continue

                log(log_f, f"[{source}] RAW: {_raw(data)}")
                decoded = decode_packet(data, source)
                if decoded:
                    log(log_f, decoded)
                else:
                    cmd = data[1] if len(data) > 1 else "?"
                    log(log_f, f"[{source}] 0x{cmd:02X}  (unknown – raw bytes above)")

    except KeyboardInterrupt:
        log(log_f, "\n[INFO ] Stopped by user.")
    finally:
        if ctrl:
            ctrl.close()
        if evt:
            evt.close()
        log_f.close()
        print(f"\nSession saved → {log_path}")


if __name__ == "__main__":
    main()
