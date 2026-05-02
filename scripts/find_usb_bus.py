"""
Identify the correct USBPcap interface in Wireshark for capturing
SteelSeries Arctis Nova Pro USB traffic.

Usage:
  python scripts/find_usb_bus.py
"""

import json
import subprocess
import sys
from pathlib import Path

import hid

sys.path.insert(0, str(Path(__file__).parent))

from listen import ARCTIS_NOVA_PRO_PIDS, STEELSERIES_VID  # noqa: E402


def _ps(script: str) -> str | None:
    """Run a PowerShell script, return stdout or None on failure."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=25,
        )
        out = result.stdout.strip()
        return out if result.returncode == 0 and out else None
    except Exception:
        return None


def find_usb_device_info() -> dict | None:
    """Walk the Windows device tree from the SteelSeries USB device up to its
    host controller; return a dict with device name, host controller name, and
    all host controllers sorted by instance ID (USBPcap assigns numbers in
    that order)."""
    pid_list = "|".join(f"PID_{p:04X}" for p in ARCTIS_NOVA_PRO_PIDS)

    script = rf"""
$pidList = '{pid_list}'.Split('|')
$dev = $null
foreach ($pid in $pidList) {{
    $dev = Get-PnpDevice | Where-Object {{
        $_.HardwareID -match "USB\\VID_1038.*$pid" -and $_.Status -eq 'OK'
    }} | Select-Object -First 1
    if ($dev) {{ break }}
}}
if (-not $dev) {{ exit 1 }}

# Walk parent chain toward the USB host controller
$cur = $dev
$hcName  = $null
$hcInstId = $null
for ($i = 0; $i -lt 8; $i++) {{
    $pid2 = (Get-PnpDeviceProperty -InstanceId $cur.InstanceId `
               -KeyName 'DEVPKEY_Device_Parent' `
               -ErrorAction SilentlyContinue).Data
    if (-not $pid2) {{ break }}
    $parent = Get-PnpDevice -InstanceId $pid2 -ErrorAction SilentlyContinue
    if (-not $parent) {{ break }}
    $cur = $parent
    if ($cur.FriendlyName -match 'Host Controller' -or
        ($cur.Class -eq 'USB' -and $cur.HardwareID -match '^PCI\\')) {{
        $hcName   = $cur.FriendlyName
        $hcInstId = $cur.InstanceId
        break
    }}
}}

# List all USB host controllers in instance-ID order
# (USBPcap numbers them 1, 2, 3 ... in this order)
$allHCs = Get-PnpDevice | Where-Object {{
    $_.FriendlyName -match 'Host Controller' -and
    ($_.Class -eq 'USB' -or $_.Class -eq 'USBDevice')
}} | Sort-Object InstanceId | ForEach-Object -Begin {{ $n = 1 }} -Process {{
    [PSCustomObject]@{{
        USBPcap = "USBPcap$n"
        Name    = $_.FriendlyName
        InstId  = $_.InstanceId
        IsMatch = ($_.InstanceId -eq $hcInstId)
    }}
    $n++
}}

@{{
    DeviceName       = $dev.FriendlyName
    DeviceInstanceId = $dev.InstanceId
    HostController   = $hcName
    HostControllerInstId = $hcInstId
    AllControllers   = @($allHCs)
}} | ConvertTo-Json -Depth 4
"""

    out = _ps(script)
    if out:
        try:
            return json.loads(out)
        except json.JSONDecodeError:
            pass
    return None


def main() -> None:
    ifaces = [
        d
        for d in hid.enumerate()
        if d["vendor_id"] == STEELSERIES_VID
        and d["product_id"] in ARCTIS_NOVA_PRO_PIDS
    ]

    if not ifaces:
        print("No Arctis Nova Pro device found. Is the base station plugged in?")
        sys.exit(1)

    name = ARCTIS_NOVA_PRO_PIDS[ifaces[0]["product_id"]]
    print(f"Device : {name}  (VID=0x1038)\n")

    print("HID interface paths:")
    for d in sorted(ifaces, key=lambda x: (x["interface_number"], x["usage_page"])):
        path = d["path"].decode() if isinstance(d["path"], bytes) else d["path"]
        print(f"  IF{d['interface_number']:02d}  UP:0x{d['usage_page']:04X}  {path}")

    print("\nQuerying USB device tree via PowerShell …\n")
    info = find_usb_device_info()

    if info:
        print(f"  USB composite device : {info.get('DeviceName', '?')}")
        print(f"  Host controller      : {info.get('HostController', '(not found)')}")
        print()

        controllers = info.get("AllControllers") or []
        if isinstance(controllers, dict):
            controllers = [controllers]

        if controllers:
            print("  USB host controllers (→ USBPcap interface numbers):")
            for hc in controllers:
                marker = "  ← headset is on THIS bus" if hc.get("IsMatch") else ""
                print(f"    {hc.get('USBPcap', '?'):10}  {hc.get('Name', '?')}{marker}")
    else:
        print("  PowerShell query failed (try running as Administrator).")

    print()
    print("=" * 62)
    print("How to select the USBPcap interface in Wireshark")
    print("=" * 62)
    print("""
Recommended — capture on ALL buses at once (simplest):
  1. Open Wireshark
  2. Ctrl-click every USBPcap interface in the interface list
  3. Click Start
  4. Unplug and replug the headset base station USB cable
  5. Apply filter: usb.idVendor == 0x1038
  6. The interface that shows traffic is the correct one
  7. Stop, note the interface name, and restart on that one only

Alternatively — use the USBPcap number printed above (if found):
  Open Wireshark → select that USBPcap interface → Start

See docs/WiresharkCaptureGuide.md for the full capture procedure.
""")


if __name__ == "__main__":
    main()
