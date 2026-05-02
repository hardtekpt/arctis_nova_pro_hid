"""
Phase 1 – Interface Discovery
Enumerates all connected HID devices and identifies Arctis Nova Pro interfaces.
"""

import hid

STEELSERIES_VID = 0x1038

ARCTIS_NOVA_PRO_PIDS = {
    0x12CB: "Arctis Nova Pro Wireless",
    0x12CD: "Arctis Nova Pro Wireless",
    0x12E0: "Arctis Nova Pro Wireless X",
    0x12E5: "Arctis Nova Pro Wireless X",
    0x225D: "Arctis Nova Pro Wireless",
}

COMMAND_INTERFACE = 4


def enumerate_all_devices() -> list[dict]:
    return hid.enumerate()


def print_all_devices(devices: list[dict]) -> None:
    print("\n=== All Connected HID Devices ===\n")
    print(f"{'VID':>6}  {'PID':>6}  {'IF':>3}  {'UsagePage':>10}  {'Usage':>6}  Product")
    print("-" * 72)
    for d in sorted(devices, key=lambda x: (x["vendor_id"], x["product_id"], x["interface_number"])):
        vid = f"0x{d['vendor_id']:04X}"
        pid = f"0x{d['product_id']:04X}"
        iface = d["interface_number"]
        usage_page = f"0x{d['usage_page']:04X}"
        usage = f"0x{d['usage']:04X}"
        product = d.get("product_string") or d.get("manufacturer_string") or ""
        print(f"{vid:>6}  {pid:>6}  {iface:>3}  {usage_page:>10}  {usage:>6}  {product}")
    print()


def find_arctis_devices(devices: list[dict]) -> dict[int, list[dict]]:
    """Return a dict of PID → list of interfaces for matching SteelSeries devices."""
    matches: dict[int, list[dict]] = {}
    for d in devices:
        if d["vendor_id"] == STEELSERIES_VID and d["product_id"] in ARCTIS_NOVA_PRO_PIDS:
            pid = d["product_id"]
            matches.setdefault(pid, []).append(d)
    return matches


def print_arctis_summary(matches: dict[int, list[dict]]) -> None:
    print("=== Arctis Nova Pro — Interface Summary ===\n")

    if not matches:
        print("  No Arctis Nova Pro device detected.")
        print()
        print("  Troubleshooting:")
        print("    - Make sure the base station is plugged in via USB.")
        print("    - Try a different USB port or cable.")
        print("    - Known PIDs:", ", ".join(f"0x{p:04X}" for p in ARCTIS_NOVA_PRO_PIDS))
        print("    - If your device has a different PID, add it to ARCTIS_NOVA_PRO_PIDS.")
        print()
        return

    for pid, interfaces in matches.items():
        name = ARCTIS_NOVA_PRO_PIDS[pid]
        print(f"  Device : {name} (PID 0x{pid:04X})")
        print(f"  {'IF':>3}  {'UsagePage':>10}  {'Usage':>6}  Path")
        print("  " + "-" * 68)
        for iface in sorted(interfaces, key=lambda x: x["interface_number"]):
            iface_num = iface["interface_number"]
            usage_page = f"0x{iface['usage_page']:04X}"
            usage = f"0x{iface['usage']:04X}"
            path = iface["path"].decode() if isinstance(iface["path"], bytes) else iface["path"]
            marker = "  <-- COMMAND INTERFACE" if iface_num == COMMAND_INTERFACE else ""
            print(f"  {iface_num:>3}  {usage_page:>10}  {usage:>6}  {path}{marker}")
        print()

    command_paths = [
        iface["path"]
        for interfaces in matches.values()
        for iface in interfaces
        if iface["interface_number"] == COMMAND_INTERFACE
    ]

    if command_paths:
        print(f"  Interface {COMMAND_INTERFACE} path(s) to use for HID reads/writes:")
        for p in command_paths:
            path_str = p.decode() if isinstance(p, bytes) else p
            print(f"    {path_str}")
    else:
        print(f"  WARNING: No interface {COMMAND_INTERFACE} found for this device.")
        print("  The headset may not be powered on or wirelessly connected to the base station.")
    print()


def main() -> None:
    devices = enumerate_all_devices()
    print_all_devices(devices)
    matches = find_arctis_devices(devices)
    print_arctis_summary(matches)


if __name__ == "__main__":
    main()
