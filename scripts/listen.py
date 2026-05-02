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

# ── Query commands ────────────────────────────────────────────────────────────
# 0xB0, 0x20, 0x10, 0x12 confirmed on Nova Pro (session 2026-05-01).
# 0xA0 sent but no response observed – likely unsupported on Nova Pro.
QUERY_COMMANDS = [
    (0xB0, "status        (battery, partial decode – see HidCommands.md §6.1)"),
    (0x20, "mic / EQ      (gain level, sidetone raw, 10 EQ band values)"),
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
        # data[2]: 0x01 = 2.4 GHz only; 0x04 = 2.4 GHz + Bluetooth active
        # data[3]: 0x01 = BT active; 0x02 = BT transitioning/paired not streaming
        return (
            f"{tag}  Connectivity    → wireless={wireless} bluetooth={bluetooth}"
            f"  [2]=0x{data[2]:02X} [3]=0x{data[3]:02X}"
        )

    if cmd == 0xB7 and len(data) > 3:
        h = round(min(100, data[2] / 8 * 100))
        d = round(min(100, data[3] / 8 * 100))
        # data[4]: 0x08 = headset in dock; 0x01 = headset removed (bat reads 0%)
        extra = f"  [4]=0x{data[4]:02X}" if len(data) > 4 and data[4] != 0 else ""
        return f"{tag}  Battery         → headset={h}% dock={d}%{extra}"

    if cmd == 0x85 and len(data) > 2:
        lvl = data[2]
        note = "" if 1 <= lvl <= 10 else " ⚠ out of range"
        return f"{tag}  OLED Brightness → {lvl}/10{note}"

    if cmd == 0x39 and len(data) > 2:
        SIDETONE_LABELS = {0: "off", 1: "low", 2: "medium", 3: "high"}
        label = SIDETONE_LABELS.get(data[2], f"unknown({data[2]})")
        return f"{tag}  Sidetone        → {label} (level={data[2]})"

    if cmd == 0xBD and len(data) > 2:
        mode = ANC_MODES.get(data[2], f"unknown(0x{data[2]:02X})")
        return f"{tag}  ANC Mode        → {mode}"

    if cmd == 0xBB and len(data) > 2:
        muted = data[2] == 1
        return f"{tag}  Mic Mute        → {'muted' if muted else 'unmuted'}"

    # ── Confirmed incoming event: ChatMix dial ──

    if cmd == 0x45 and len(data) > 3:
        return f"{tag}  ChatMix         → game={data[2]} chat={data[3]}"

    # ── Confirmed incoming event: Gain Level ─────────────────────────────────
    # Observed values: 1=low, 2=high. Full range unknown.

    if cmd == 0x27 and len(data) > 2:
        GAIN_LABELS = {1: "low", 2: "high"}
        label = GAIN_LABELS.get(data[2], f"unknown({data[2]})")
        return f"{tag}  Gain Level      → {label} (raw={data[2]})  [range: 1=low, 2=high only]"

    if cmd == 0xB9 and len(data) > 2:
        lvl = data[2]
        note = "" if 1 <= lvl <= 10 else " ⚠ out of range"
        return f"{tag}  Transparency Lvl→ {lvl}/10{note}"

    # ── Confirmed incoming event: Mic Volume ─────────────────────────────────
    # 0x37 was assumed to be a write-only command (Nova 7X); on Nova Pro it is
    # also an incoming event fired when the user adjusts mic volume.

    if cmd == 0x37 and len(data) > 2:
        return f"{tag}  Mic Volume      → level={data[2]}  (range observed: 1–10)"

    # ── Unidentified events — user actions known, exact meanings pending ──────
    # Triggered in session 2026-05-01 session 2. Order matches user actions:
    # 0x83 = dim screen, 0x89 = home screen mode, 0xBF = mic LED, 0xC1 = auto off

    _TIMEOUT = {0: "off", 1: "1 min", 2: "5 min", 3: "10 min", 4: "15 min", 5: "30 min", 6: "60 min"}

    if cmd == 0x83 and len(data) > 2:
        label = _TIMEOUT.get(data[2], f"?({data[2]})")
        return f"{tag}  Dim Screen      → {label} (raw={data[2]})"

    if cmd == 0x89 and len(data) > 2:
        label = {0: "detailed", 1: "simple"}.get(data[2], f"?({data[2]})")
        return f"{tag}  Home Screen     → {label} (raw={data[2]})"

    if cmd == 0xBF and len(data) > 2:
        return f"{tag}  Mic LED         → {data[2]}/10"

    if cmd == 0xC1 and len(data) > 2:
        label = _TIMEOUT.get(data[2], f"?({data[2]})")
        return f"{tag}  Auto Off        → {label} (raw={data[2]})"

    if cmd == 0xC3 and len(data) > 2:
        label = {0: "performance/speed", 1: "extended range"}.get(data[2], f"?({data[2]})")
        return f"{tag}  2.4 GHz Mode    → {label} (raw={data[2]})"

    if cmd == 0xB2 and len(data) > 2:
        label = {0: "off", 1: "on"}.get(data[2], f"?({data[2]})")
        return f"{tag}  BT Default      → {label} (raw={data[2]})"

    if cmd == 0xB3 and len(data) > 2:
        label = {0: "off", 1: "-12dB", 2: "on"}.get(data[2], f"?({data[2]})")
        return f"{tag}  BT Auto-Mute    → {label} (raw={data[2]})"

    if cmd == 0x47 and len(data) > 5:
        return (
            f"{tag}  Stream Volumes  → "
            f"main={data[2]}  aux={data[4]}  mic={data[5]}"
        )

    if cmd == 0x43 and len(data) > 2:
        label = {1: "speaker", 2: "stream"}.get(data[2], f"?({data[2]})")
        return f"{tag}  Audio Output    → {label} (raw={data[2]})"

    # ── Confirmed query responses ─────────────────────────────────────────────
    # Offsets: data[0]=reportId  data[1]=cmd  data[2+]=payload

    # Battery confirmed at [6]/[7] (0-8 raw = 0-100%).
    # Audio output at [3], all fields mapped – see HidCommands.md §6.1.
    if cmd == 0xB0 and len(data) > 13:
        _CONN    = {0x01: "2.4GHz", 0x04: "2.4GHz+BT"}
        _ANC     = {0x00: "off", 0x01: "transparency", 0x02: "anc"}
        _WMODE   = {0x00: "performance", 0x01: "range"}
        _AUDIO   = {0x01: "speaker", 0x02: "stream"}
        h_bat    = round(min(100, data[6] / 8 * 100))
        d_bat    = round(min(100, data[7] / 8 * 100))
        conn     = _CONN.get(data[4], f"0x{data[4]:02X}")
        muted    = "muted" if data[9] == 1 else "unmuted"
        anc      = _ANC.get(data[10], f"0x{data[10]:02X}")
        audio    = _AUDIO.get(data[3], f"0x{data[3]:02X}")
        bt       = "on" if data[5] == 1 else "off"
        wmode    = _WMODE.get(data[13], f"0x{data[13]:02X}")
        return (
            f"{tag}  Status          → "
            f"headset_bat={h_bat}%  dock_bat={d_bat}%  "
            f"conn={conn}  mic_mute={muted}  anc={anc}  "
            f"bt={bt}  oled_brightness={data[11]}  audio_output={audio}  2.4ghz_mode={wmode}"
        )

    # 0x20 layout confirmed: [7-16] = 10 EQ bands (0-40, 0x14=center).
    # [22-25] = stream output volumes (main, padding, aux, mic) – see HidCommands.md §6.1.
    if cmd == 0x20 and len(data) > 25:
        _GAIN = {1: "low", 2: "high"}
        _SIDE = {0: "off", 1: "low", 2: "medium", 3: "high"}
        gain         = _GAIN.get(data[4], f"?({data[4]})")
        sidetone     = _SIDE.get(data[18], f"?({data[18]})")
        vol_pct      = round(max(0, min(100, (0x38 - data[3]) / 56 * 100)))
        eq_bands     = _raw(data[7:17])
        stream_main  = data[22]
        stream_aux   = data[24]
        stream_mic   = data[25]
        return (
            f"{tag}  Mic/EQ          → "
            f"gain={gain}  mic_vol={data[17]}  sidetone={sidetone}  "
            f"vol={vol_pct}%  chatmix_game={data[20]}  chatmix_chat={data[21]}  "
            f"stream_main={stream_main}  stream_aux={stream_aux}  stream_mic={stream_mic}  "
            f"eq_bands=[{eq_bands}]"
        )

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
        log(log_f, "[INFO ] Try: volume wheel, mute button, ANC button, ChatMix dial, gain button.")
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
