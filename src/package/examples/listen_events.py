"""Event / listen mode example.

Run this script while using the headset — turn the volume dial, press
the mic mute button, change ANC mode, etc. — and watch events print in
real time.

    pip install -e package/
    python package/examples/listen_events.py
"""

import signal
import sys

from arctis_hid import (
    AncModeEvent,
    BatteryEvent,
    ChatMixEvent,
    ConnectivityEvent,
    GainEvent,
    MicMuteEvent,
    MicVolumeEvent,
    SidetoneEvent,
    VolumeEvent,
    discover,
)


def main() -> None:
    print("Searching for Arctis Nova Pro Wireless…")
    headset = discover()
    print("Found headset. Listening for events (Ctrl-C to stop).\n")

    headset.on("VolumeEvent",       lambda e: print(f"[Volume]      {e.percent:.1f}%"))
    headset.on("BatteryEvent",      lambda e: print(f"[Battery]     headset={e.headset_pct:.0f}%  dock={e.dock_pct:.0f}%"))
    headset.on("MicMuteEvent",      lambda e: print(f"[Mic mute]    {'muted' if e.muted else 'unmuted'}"))
    headset.on("AncModeEvent",      lambda e: print(f"[ANC]         {e.mode.name}"))
    headset.on("ConnectivityEvent", lambda e: print(f"[Connectivity] mode={e.mode:#04x}  bt={e.bt_active}  wireless={e.wireless}"))
    headset.on("GainEvent",         lambda e: print(f"[Gain]        {e.level.name}"))
    headset.on("MicVolumeEvent",    lambda e: print(f"[Mic volume]  {e.level}"))
    headset.on("SidetoneEvent",     lambda e: print(f"[Sidetone]    {e.level.name}"))
    headset.on("ChatMixEvent",      lambda e: print(f"[ChatMix]     game={e.game}  chat={e.chat}"))

    def _shutdown(sig: int, frame: object) -> None:
        print("\nStopping…")
        headset.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)

    headset.listen()   # blocks until Ctrl-C or headset disconnects


if __name__ == "__main__":
    main()
