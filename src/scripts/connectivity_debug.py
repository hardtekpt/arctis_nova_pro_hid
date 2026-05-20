"""connectivity_debug.py — Connectivity and power state diagnostic tool.

Queries get_status (0xB0), get_connectivity (0xB5) and get_battery (0xB7),
then prints raw bytes for the relevant fields in each response alongside the
live ConnectivityStatus derived from the headset instance after each query.
Also listens on Col02 for 0xB5 (connectivity), 0xC3 (wireless mode),
DeviceDisconnectedEvent and DeviceReconnectedEvent.

Run from the repo root:
    python src/scripts/connectivity_debug.py

Press Ctrl-C to exit the event loop.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "package"))

from arctis_hid import discover
from arctis_hid.devices.nova_pro import constants as C


# ── Formatting helpers ─────────────────────────────────────────────────────

def _hex(raw: int) -> str:
    return f"0x{raw:02X}"


def _row(label: str, byte_ref: str, raw: int) -> None:
    print(f"  {label:<24} [{byte_ref}] raw={_hex(raw)}")


def _print_connectivity(prefix: str, cs) -> None:
    print(f"  connectivity → usb={cs.usb}, headset_power={cs.headset_power}, "
          f"wireless={cs.wireless}, bt={cs.bt}")


# ── Query printers ─────────────────────────────────────────────────────────

def print_status(h, data: list[int]) -> None:
    print("\n── 0xB0  get_status ─────────────────────────────────────────")
    _row("connectivity_mode",   "B0[4]",  data[C.B0_CONN])
    _row("bt_active",           "B0[5]",  data[C.B0_BT])
    _row("wireless_link_state", "B0[14]", data[C.B0_WIRELESS_LINK])
    _row("headset_powered",     "B0[15]", data[C.B0_PWR])
    _print_connectivity("get_status", h.connectivity)


def print_connectivity(h, data: list[int]) -> None:
    print("\n── 0xB5  get_connectivity ───────────────────────────────────")
    _row("connectivity_mode",   "B5[2]",  data[C.B5_CONN])
    _row("bt_connected",        "B5[3]",  data[C.B5_BT_CONNECTED])
    _print_connectivity("get_connectivity", h.connectivity)


def print_battery(h, data: list[int]) -> None:
    print("\n── 0xB7  get_battery ────────────────────────────────────────")
    _row("headset_powered",     "B7[4]",  data[C.B7_PWR])
    _print_connectivity("get_battery", h.connectivity)


# ── Event handlers ─────────────────────────────────────────────────────────

def _make_handlers(h):
    def on_connectivity(evt) -> None:
        print(f"\n>> ConnectivityEvent (0xB5)")
        _print_connectivity("event", evt.connectivity)

    def on_wireless_mode(evt) -> None:
        print(f"\n>> WirelessModeEvent (0xC3)  mode={evt.mode}")

    def on_disconnected(evt) -> None:
        print("\n>> DeviceDisconnectedEvent — USB HID connection lost")
        _print_connectivity("post-disconnect", h.connectivity)

    def on_reconnected(evt) -> None:
        print("\n>> DeviceReconnectedEvent  — USB HID connection restored")
        _print_connectivity("post-reconnect", h.connectivity)

    return on_connectivity, on_wireless_mode, on_disconnected, on_reconnected


# ── Main ───────────────────────────────────────────────────────────────────

def main() -> None:
    print("connectivity_debug: querying device …")

    with discover() as h:
        # --- snapshot queries (update headset connectivity state) ---
        raw_b0 = h._transport.query(C.CMD_STATUS)
        from arctis_hid.devices.nova_pro import codec
        h._apply_b0_conn(codec.decode_b0_conn(raw_b0))
        print_status(h, raw_b0)

        raw_b5 = h._transport.query(C.CMD_CONNECTIVITY)
        h._apply_b5_conn(codec.decode_b5_query(raw_b5), from_event=False)
        print_connectivity(h, raw_b5)

        raw_b7 = h._transport.query(C.CMD_BATTERY)
        h._cs_headset_power = (raw_b7[C.B7_PWR] == 0x08)
        print_battery(h, raw_b7)

        # --- event listener ---
        on_conn, on_wl, on_disc, on_reconn = _make_handlers(h)
        h.on("ConnectivityEvent",       on_conn)
        h.on("WirelessModeEvent",       on_wl)
        h.on("DeviceDisconnectedEvent", on_disc)
        h.on("DeviceReconnectedEvent",  on_reconn)

        print("\n── Listening for events (Ctrl-C to exit) ────────────────")
        h.listen()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDone.")
