"""Command / query mode example.

Demonstrates querying device state and sending write commands.

    pip install -e package/
    python package/examples/query_and_write.py
"""

from arctis_hid import AncMode, GainLevel, SidetoneLevel, TimeoutStep, discover


def main() -> None:
    print("Searching for Arctis Nova Pro Wireless…")

    with discover() as h:
        # ── Query current state ────────────────────────────────────────────
        status = h.get_status()
        print("\n── Status ───────────────────────────────")
        print(f"  Headset battery : {status.headset_battery_pct:.0f}%")
        print(f"  Dock battery    : {status.dock_battery_pct:.0f}%")
        print(f"  ANC mode        : {status.anc_mode.name}")
        print(f"  Mic muted       : {status.mic_muted}")
        print(f"  OLED brightness : {status.oled_brightness}")
        print(f"  Wireless mode   : {status.wireless_mode.name}")
        print(f"  BT active       : {status.bt_active}")

        mic = h.get_mic_eq()
        print("\n── Mic / EQ ─────────────────────────────")
        print(f"  Volume          : {mic.volume_pct:.1f}%")
        print(f"  Gain            : {mic.gain.name}")
        print(f"  Mic volume      : {mic.mic_volume}")
        print(f"  Sidetone        : {mic.sidetone.name}")
        print(f"  Audio output    : {mic.audio_output.name}")
        print(f"  EQ preset index : {mic.eq_preset_index}")
        print(f"  EQ bands        : {mic.eq_bands}")
        print(f"  ChatMix game/chat: {mic.chatmix_game} / {mic.chatmix_chat}")

        fw = h.get_firmware_version()
        sn = h.get_serial_number()
        print(f"\n── Device info ──────────────────────────")
        print(f"  Firmware        : {fw}")
        print(f"  Serial number   : {sn}")

        # ── Example writes ─────────────────────────────────────────────────
        print("\n── Applying example settings ────────────")

        print("  Setting volume to 60%…")
        h.set_volume(60)

        print("  Setting ANC to TRANSPARENCY…")
        h.set_anc_mode(AncMode.TRANSPARENCY)
        h.set_transparency_level(5)

        print("  Setting gain to HIGH…")
        h.set_gain(GainLevel.HIGH)

        print("  Setting sidetone to LOW…")
        h.set_sidetone(SidetoneLevel.LOW)

        print("  Setting OLED brightness to 8…")
        h.set_oled_brightness(8)

        print("  Setting auto-off to 30 min…")
        h.set_auto_off_timeout(TimeoutStep.THIRTY_MIN)

        print("  Setting custom EQ (flat +2 dB on bands 1 and 10)…")
        bands = [22, 20, 20, 20, 20, 20, 20, 20, 20, 22]
        h.set_eq_bands(bands)

        print("\nDone. Settings have been saved to the headset.")


if __name__ == "__main__":
    main()
