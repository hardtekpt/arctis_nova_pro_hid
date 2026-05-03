"""Arctis Nova Pro — unified test CLI covering docs/TestChecklist.md.

Requirements:
    pip install -e package/                  # core library
    pip install 'arctis-hid[oled]'           # adds Pillow for oled-* commands

NOTE: --verify must come BEFORE the subcommand name:
    python scripts/test_cli.py --verify sidetone --level high   [OK]
    python scripts/test_cli.py sidetone --level high --verify   [WRONG - flag must come first]

    # Launch interactive terminal menu
    python scripts/test_cli.py --interactive
    python scripts/test_cli.py -i

Usage examples:
    # Section 2 — query commands
    python scripts/test_cli.py query
    python scripts/test_cli.py status
    python scripts/test_cli.py miceq

    # Section 1 — event listener (interact with headset)
    python scripts/test_cli.py listen

    # Section 3/4 — write commands (add --verify to confirm round-trip)
    python scripts/test_cli.py --verify sidetone --level high
    python scripts/test_cli.py --verify anc --mode transparency
    python scripts/test_cli.py --verify volume --pct 60
    python scripts/test_cli.py --verify oled-brightness --level 7
    python scripts/test_cli.py --verify gain --level low
    python scripts/test_cli.py --verify mic-vol --level 8
    python scripts/test_cli.py --verify audio-output --output speakers
    python scripts/test_cli.py --verify stream-volumes --main 80 --aux 80 --mic 60
    python scripts/test_cli.py --verify wireless-mode --mode performance
    python scripts/test_cli.py --verify eq-preset --index 0x04
    python scripts/test_cli.py --verify eq-bands --bands 20 20 20 20 20 20 20 20 20 20

    python scripts/test_cli.py transparency --level 5
    python scripts/test_cli.py mic-led --level 5
    python scripts/test_cli.py dim-timeout --step 5
    python scripts/test_cli.py auto-off --step 30
    python scripts/test_cli.py home-screen --mode simple
    python scripts/test_cli.py chatmix --state on
    python scripts/test_cli.py bt-default --state on
    python scripts/test_cli.py bt-auto-mute --mode off

    # Section 10 — OLED (requires Pillow)
    python scripts/test_cli.py oled-text --text "Hello"
    python scripts/test_cli.py oled-text --text "Hi" --x 10 --y 20 --invert
    python scripts/test_cli.py oled-scroll --text "The quick brown fox" --fps 15
    python scripts/test_cli.py oled-img --path banner.png --threshold 100
    python scripts/test_cli.py oled-anim --frames frame1.png frame2.png --fps 10 --loops 5
    python scripts/test_cli.py oled-gif --path anim.gif --loops 3
    python scripts/test_cli.py oled-clear
    python scripts/test_cli.py oled-release

    # Section 9 — edge cases
    python scripts/test_cli.py edge-volume-min
    python scripts/test_cli.py edge-volume-max
    python scripts/test_cli.py edge-sidetone-oob --value 0x04
    python scripts/test_cli.py edge-mic-vol-oob --value 0x00
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "package"))

from arctis_hid import (
    AncMode,
    AudioOutput,
    BtAutoMute,
    GainLevel,
    HomeScreenMode,
    MicEqData,
    SidetoneLevel,
    StatusData,
    TimeoutStep,
    WirelessMode,
    discover,
)


# ── Helpers ────────────────────────────────────────────────────────────────

_TIMEOUT_MAP: dict[str, TimeoutStep] = {
    "off": TimeoutStep.OFF,
    "1":   TimeoutStep.ONE_MIN,
    "5":   TimeoutStep.FIVE_MIN,
    "10":  TimeoutStep.TEN_MIN,
    "15":  TimeoutStep.FIFTEEN_MIN,
    "30":  TimeoutStep.THIRTY_MIN,
    "60":  TimeoutStep.SIXTY_MIN,
}


def _timeout(s: str) -> TimeoutStep:
    return _TIMEOUT_MAP[s]


def _sep(title: str) -> None:
    pad = max(0, 42 - len(title))
    print(f"\n── {title} {'─' * pad}")


def _print_status(s: StatusData) -> None:
    _sep("Status (0xB0)")
    print(f"  Headset battery  : {s.headset_battery_pct:.0f}%")
    print(f"  Dock battery     : {s.dock_battery_pct:.0f}%")
    print(f"  Connectivity     : {s.connectivity_mode:#04x}")
    print(f"  BT active        : {s.bt_active}")
    print(f"  Mic muted        : {s.mic_muted}  (0xB0[9])")
    print(f"  ANC mode         : {s.anc_mode.name}  (0xB0[10]={s.anc_mode.value:#04x})")
    print(f"  Mic LED brightness: {s.mic_led_brightness}/10  (0xB0[11]={s.mic_led_brightness:#04x})")
    print(f"  Wireless mode    : {s.wireless_mode.name}  (0xB0[13]={s.wireless_mode.value:#04x})")


def _print_miceq(m: MicEqData) -> None:
    _sep("Mic / EQ (0x20)")
    print(f"  Volume           : {m.volume_pct:.1f}%  (0x20[3])")
    print(f"  Gain             : {m.gain.name}  (0x20[4]={m.gain.value:#04x})")
    print(f"  EQ preset index  : {m.eq_preset_index:#04x}  (0x20[6])")
    bands_hex = " ".join(f"{b:02x}" for b in m.eq_bands)
    print(f"  EQ bands         : {bands_hex}  (0x20[7–16])")
    print(f"  Mic volume       : {m.mic_volume}  (0x20[17])")
    print(f"  Sidetone         : {m.sidetone.name}  (0x20[18]={m.sidetone.value:#04x})")
    print(f"  Audio output     : {m.audio_output.name}  (0x20[19]={m.audio_output.value:#04x})")
    print(f"  ChatMix game     : {m.chatmix_game}  (0x20[20])")
    print(f"  ChatMix chat     : {m.chatmix_chat}  (0x20[21])")
    print(f"  Stream main vol  : {m.stream_main_vol}  (0x20[22])")
    print(f"  Stream aux vol   : {m.stream_aux_vol}  (0x20[24])")
    print(f"  Stream mic vol   : {m.stream_mic_vol}  (0x20[25])")


def _verify_field(endpoint: str, before_val: object, after_val: object, expected: object) -> None:
    ok = str(after_val) == str(expected)
    tag = "OK" if ok else "UNEXPECTED"
    print(f"  {endpoint}: {before_val!r} → {after_val!r}  [{tag}]")
    if not ok:
        print(f"  Expected {expected!r}")


def _no_verify_field(reason: str) -> None:
    print(f"  ({reason} — verify visually or via listen)")


def _require_oled() -> None:
    try:
        import PIL  # noqa: F401
    except ImportError:
        sys.exit(
            "Pillow is required for oled-* commands.\n"
            "Install it with:  pip install 'arctis-hid[oled]'"
        )


def _oled_font(args):
    if getattr(args, "font", ""):
        from PIL import ImageFont
        return ImageFont.truetype(args.font, size=args.font_size)
    return None


# ── Query handlers — TestChecklist §2 ─────────────────────────────────────

def cmd_query(args) -> None:
    with discover() as h:
        _print_status(h.get_status())
        _print_miceq(h.get_mic_eq())
        _sep("Device info")
        print(f"  Firmware         : {h.get_firmware_version()}")
        print(f"  Serial number    : {h.get_serial_number()}")


def cmd_status(args) -> None:
    with discover() as h:
        _print_status(h.get_status())


def cmd_miceq(args) -> None:
    with discover() as h:
        _print_miceq(h.get_mic_eq())


# ── Listen handler — TestChecklist §1 ─────────────────────────────────────

def cmd_listen(args) -> None:
    print("Listening for all events — interact with the headset. Ctrl-C to stop.\n")
    with discover() as h:
        h.on("VolumeEvent",         lambda e: print(f"[Volume]          {e.percent:.1f}%"))
        h.on("BatteryEvent",        lambda e: print(f"[Battery]         headset={e.headset_pct:.0f}%  dock={e.dock_pct:.0f}%"))
        h.on("MicMuteEvent",        lambda e: print(f"[MicMute]         {'muted' if e.muted else 'unmuted'}"))
        h.on("AncModeEvent",        lambda e: print(f"[ANC]             {e.mode.name}"))
        h.on("GainEvent",           lambda e: print(f"[Gain]            {e.level.name}"))
        h.on("ChatMixEvent",        lambda e: print(f"[ChatMix]         game={e.game}  chat={e.chat}"))
        h.on("SidetoneEvent",       lambda e: print(f"[Sidetone]        {e.level.name}"))
        h.on("MicVolumeEvent",      lambda e: print(f"[MicVolume]       {e.level}"))
        h.on("OledBrightnessEvent", lambda e: print(f"[OledBrightness]  {e.level}/10"))
        h.on("TransparencyEvent",   lambda e: print(f"[Transparency]    {e.level}/10"))
        h.on("ConnectivityEvent",   lambda e: print(f"[Connectivity]    mode={e.mode:#04x}  bt={e.bt_active}  wireless={e.wireless}"))
        h.on("WirelessModeEvent",   lambda e: print(f"[WirelessMode]    {e.mode.name}"))
        h.on("BtDefaultEvent",      lambda e: print(f"[BtDefault]       {'on' if e.enabled else 'off'}"))
        h.on("BtAutoMuteEvent",     lambda e: print(f"[BtAutoMute]      {e.mode.name}"))
        h.on("AudioOutputEvent",    lambda e: print(f"[AudioOutput]     {e.output.name}"))
        h.on("StreamVolumesEvent",  lambda e: print(f"[StreamVolumes]   main={e.main}  aux={e.aux}  mic={e.mic}"))
        h.on("EqPresetEvent",       lambda e: print(f"[EqPreset]        index={e.index:#04x}"))
        h.on("EqBandEvent",         lambda e: print(f"[EqBand]          band={e.band}  level={e.level}  (offset={e.level - 20:+d} dB)"))
        h.on("DimTimeoutEvent",     lambda e: print(f"[DimTimeout]      {e.step.name}"))
        h.on("HomeScreenEvent",     lambda e: print(f"[HomeScreen]      {e.mode.name}"))
        h.on("MicLedEvent",         lambda e: print(f"[MicLed]          {e.level}/10"))
        h.on("AutoOffEvent",        lambda e: print(f"[AutoOff]         {e.step.name}"))

        h.start()
        try:
            while True:
                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nStopping…")


# ── Write handlers — TestChecklist §3/4/5 ─────────────────────────────────

def cmd_volume(args) -> None:
    pct = args.pct
    if not 0.0 <= pct <= 100.0:
        sys.exit("volume must be 0–100")
    print(f"Setting volume → {pct:.1f}%…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_volume(pct)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field(
                "0x20[3] volume_pct",
                f"{before.volume_pct:.1f}%",
                f"{after.volume_pct:.1f}%",
                f"{pct:.1f}%",
            )


def cmd_mic_vol(args) -> None:
    level = args.level
    if not 1 <= level <= 10:
        sys.exit("mic-vol must be 1–10")
    print(f"Setting mic volume → {level}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_mic_volume(level)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field("0x20[17] mic_volume", before.mic_volume, after.mic_volume, level)


def cmd_sidetone(args) -> None:
    level_map = {
        "off":    SidetoneLevel.OFF,
        "low":    SidetoneLevel.LOW,
        "medium": SidetoneLevel.MEDIUM,
        "high":   SidetoneLevel.HIGH,
    }
    level = level_map[args.level]
    print(f"Setting sidetone → {args.level.upper()}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_sidetone(level)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field("0x20[18] sidetone", before.sidetone.name, after.sidetone.name, level.name)


def cmd_anc(args) -> None:
    mode_map = {
        "off":          AncMode.OFF,
        "transparency": AncMode.TRANSPARENCY,
        "anc":          AncMode.ANC,
    }
    mode = mode_map[args.mode]
    print(f"Setting ANC mode → {args.mode.upper()}…")
    with discover() as h:
        before = h.get_status() if args.verify else None
        h.set_anc_mode(mode)
        print("Done.")
        if args.verify:
            after = h.get_status()
            _verify_field("0xB0[10] anc_mode", before.anc_mode.name, after.anc_mode.name, mode.name)


def cmd_transparency(args) -> None:
    level = args.level
    if not 1 <= level <= 10:
        sys.exit("transparency level must be 1–10")
    print(f"Setting ANC → TRANSPARENCY + level → {level}…")
    with discover() as h:
        before = h.get_status() if args.verify else None
        h.set_anc_mode(AncMode.TRANSPARENCY)
        h.set_transparency_level(level)
        print("Done.")
        if args.verify:
            after = h.get_status()
            _verify_field(
                "0xB0[10] anc_mode",
                before.anc_mode.name,
                after.anc_mode.name,
                AncMode.TRANSPARENCY.name,
            )
            _no_verify_field("transparency level has no reflected query field")


def cmd_gain(args) -> None:
    level_map = {"low": GainLevel.LOW, "high": GainLevel.HIGH}
    level = level_map[args.level]
    print(f"Setting gain → {args.level.upper()}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_gain(level)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field("0x20[4] gain", before.gain.name, after.gain.name, level.name)


def cmd_oled_brightness(args) -> None:
    level = args.level
    if not 1 <= level <= 10:
        sys.exit("oled-brightness must be 1–10")
    print(f"Setting OLED brightness → {level}/10…")
    with discover() as h:
        before = h.get_status() if args.verify else None
        h.set_oled_brightness(level)
        print("Done.")
        if args.verify:
            after = h.get_status()
            _verify_field("0xB0[11] mic_led_brightness", before.mic_led_brightness, after.mic_led_brightness, level)


def cmd_mic_led(args) -> None:
    level = args.level
    if not 1 <= level <= 10:
        sys.exit("mic-led must be 1–10")
    print(f"Setting mic LED brightness → {level}/10…")
    with discover() as h:
        h.set_mic_led_brightness(level)
        print("Done.")
        if args.verify:
            _no_verify_field("mic LED brightness has no reflected query field")


def cmd_dim_timeout(args) -> None:
    step = _timeout(args.step)
    print(f"Setting dim timeout → {args.step}…")
    with discover() as h:
        h.set_dim_timeout(step)
        print("Done.")
        if args.verify:
            _no_verify_field("dim timeout has no reflected query field")


def cmd_home_screen(args) -> None:
    mode_map = {"detailed": HomeScreenMode.DETAILED, "simple": HomeScreenMode.SIMPLE}
    mode = mode_map[args.mode]
    print(f"Setting home screen → {args.mode.upper()}…")
    with discover() as h:
        h.set_home_screen_mode(mode)
        print("Done.")
        if args.verify:
            _no_verify_field("home screen mode has no reflected query field")


def cmd_auto_off(args) -> None:
    step = _timeout(args.step)
    print(f"Setting auto-off timeout → {args.step}…")
    with discover() as h:
        h.set_auto_off_timeout(step)
        print("Done.")
        if args.verify:
            _no_verify_field("auto-off timeout has no reflected query field")


def cmd_chatmix(args) -> None:
    enabled = args.state == "on"
    print(f"Setting ChatMix → {'enabled' if enabled else 'disabled'}…")
    with discover() as h:
        h.set_chatmix_enabled(enabled)
        print("Done.")
        if args.verify:
            _no_verify_field("ChatMix state has no reflected query field — listen for 0x45 events")


def cmd_wireless_mode(args) -> None:
    mode_map = {"performance": WirelessMode.PERFORMANCE, "extended": WirelessMode.EXTENDED_RANGE}
    mode = mode_map[args.mode]
    print(f"Setting wireless mode → {args.mode.upper()}…")
    with discover() as h:
        before = h.get_status() if args.verify else None
        h.set_wireless_mode(mode)
        print("Done.")
        if args.verify:
            after = h.get_status()
            _verify_field("0xB0[13] wireless_mode", before.wireless_mode.name, after.wireless_mode.name, mode.name)


def cmd_bt_default(args) -> None:
    enabled = args.state == "on"
    print(f"Setting BT default → {'on' if enabled else 'off'}…")
    with discover() as h:
        h.set_bt_default(enabled)
        print("Done.")
        if args.verify:
            _no_verify_field("BT default has no reflected query field")


def cmd_bt_auto_mute(args) -> None:
    mode_map = {"off": BtAutoMute.OFF, "-12db": BtAutoMute.DB_MINUS_12, "full": BtAutoMute.FULL}
    mode = mode_map[args.mode]
    print(f"Setting BT auto-mute → {args.mode.upper()}…")
    with discover() as h:
        h.set_bt_auto_mute(mode)
        print("Done.")
        if args.verify:
            _no_verify_field("BT auto-mute has no reflected query field")


def cmd_audio_output(args) -> None:
    output_map = {"speakers": AudioOutput.SPEAKERS, "stream": AudioOutput.STREAM}
    output = output_map[args.output]
    print(f"Setting audio output → {args.output.upper()}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_audio_output(output)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field("0x20[19] audio_output", before.audio_output.name, after.audio_output.name, output.name)


def cmd_stream_volumes(args) -> None:
    main, aux, mic = args.main, args.aux, args.mic
    for name, val in [("main", main), ("aux", aux), ("mic", mic)]:
        if not 0 <= val <= 100:
            sys.exit(f"stream-volumes {name} must be 0–100")
    print(f"Setting stream volumes → main={main}  aux={aux}  mic={mic}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_stream_volumes(main, aux, mic)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field("0x20[22] stream_main_vol", before.stream_main_vol, after.stream_main_vol, main)
            _verify_field("0x20[24] stream_aux_vol",  before.stream_aux_vol,  after.stream_aux_vol,  aux)
            _verify_field("0x20[25] stream_mic_vol",  before.stream_mic_vol,  after.stream_mic_vol,  mic)


def cmd_eq_preset(args) -> None:
    index = args.index
    print(f"Setting EQ preset → {index:#04x}…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_eq_preset(index)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            _verify_field(
                "0x20[6] eq_preset_index",
                f"{before.eq_preset_index:#04x}",
                f"{after.eq_preset_index:#04x}",
                f"{index:#04x}",
            )


def cmd_eq_bands(args) -> None:
    bands = args.bands
    if len(bands) != 10:
        sys.exit(f"eq-bands requires exactly 10 values, got {len(bands)}")
    for i, b in enumerate(bands):
        if not 0 <= b <= 40:
            sys.exit(f"EQ band {i + 1} must be 0–40 (got {b})")
    bands_hex = " ".join(f"{b:02x}" for b in bands)
    print(f"Setting custom EQ bands → [{bands_hex}]…")
    with discover() as h:
        before = h.get_mic_eq() if args.verify else None
        h.set_eq_bands(bands)
        print("Done.")
        if args.verify:
            after = h.get_mic_eq()
            before_hex = " ".join(f"{b:02x}" for b in before.eq_bands)
            after_hex  = " ".join(f"{b:02x}" for b in after.eq_bands)
            _verify_field("0x20[7–16] eq_bands", before_hex, after_hex, bands_hex)


# ── OLED handlers — TestChecklist §10 ─────────────────────────────────────

def cmd_oled_clear(args) -> None:
    _require_oled()
    print("Clearing OLED display…")
    with discover() as h:
        h.oled.clear()
        print("Done.")


def cmd_oled_release(args) -> None:
    print("Returning OLED control to GG / Sonar…")
    with discover() as h:
        h.oled.release()
        print("Done.")


def cmd_oled_text(args) -> None:
    _require_oled()
    font = _oled_font(args)
    print(f"Drawing text: {args.text!r}  x={args.x}  y={args.y}  invert={args.invert}…")
    with discover() as h:
        h.oled.draw_text(args.text, font=font, x=args.x, y=args.y, invert=args.invert)
        print("Done.")


def cmd_oled_scroll(args) -> None:
    _require_oled()
    font = _oled_font(args)
    print(f"Scrolling text: {args.text!r}  fps={args.fps}  invert={args.invert}…")
    with discover() as h:
        h.oled.scroll_text(args.text, font=font, fps=args.fps, invert=args.invert)
        print("Done.")


def cmd_oled_img(args) -> None:
    _require_oled()
    print(f"Drawing image: {args.path}  threshold={args.threshold}…")
    with discover() as h:
        h.oled.draw_image(args.path, threshold=args.threshold)
        print("Done.")


def cmd_oled_anim(args) -> None:
    _require_oled()
    loops = 0 if args.loops < 0 else args.loops
    print(f"Playing animation: {len(args.frames)} frame(s)  fps={args.fps}  loops={args.loops}…")
    with discover() as h:
        h.oled.play_animation(args.frames, fps=args.fps, loops=loops, threshold=args.threshold)
        print("Done.")


def cmd_oled_gif(args) -> None:
    _require_oled()
    loops = 0 if args.loops < 0 else args.loops
    fps_desc = str(args.fps) if args.fps else "embedded delays"
    print(f"Playing GIF: {args.path}  fps={fps_desc}  loops={args.loops}…")
    with discover() as h:
        h.oled.play_gif(
            args.path,
            fps=args.fps if args.fps else None,
            loops=loops,
            threshold=args.threshold,
        )
        print("Done.")


# ── Edge case handlers — TestChecklist §9 ─────────────────────────────────

def cmd_edge_volume_min(args) -> None:
    print("Edge §9.7: setting volume to 0% (expect raw=0x38)…")
    with discover() as h:
        h.set_volume(0.0)
        after = h.get_mic_eq()
        pct = after.volume_pct
        ok = abs(pct) < 0.5
        print(f"  volume_pct = {pct:.1f}%  [{'OK' if ok else 'UNEXPECTED'}]")


def cmd_edge_volume_max(args) -> None:
    print("Edge §9.8: setting volume to 100% (expect raw=0x00)…")
    with discover() as h:
        h.set_volume(100.0)
        after = h.get_mic_eq()
        pct = after.volume_pct
        ok = abs(pct - 100.0) < 0.5
        print(f"  volume_pct = {pct:.1f}%  [{'OK' if ok else 'UNEXPECTED'}]")


def cmd_edge_sidetone_oob(args) -> None:
    from arctis_hid.devices.nova_pro.constants import CMD_SAVE, CMD_SIDETONE

    val = args.value
    print(f"Edge §9.4: sending raw sidetone byte 0x{val:02X} (bypasses enum validation)…")
    with discover() as h:
        h._transport.write(CMD_SIDETONE, [val])
        h._transport.write(CMD_SAVE)
        after = h.get_mic_eq()
        print(
            f"  0x20[18] sidetone = {after.sidetone.value:#04x} ({after.sidetone.name})"
            "  (observe headset — no crash = pass)"
        )


def cmd_edge_mic_vol_oob(args) -> None:
    from arctis_hid.devices.nova_pro.constants import CMD_MIC_VOL, CMD_SAVE

    val = args.value
    print(f"Edge §9.5-6: sending raw mic volume byte 0x{val:02X} (bypasses range validation)…")
    with discover() as h:
        h._transport.write(CMD_MIC_VOL, [val])
        h._transport.write(CMD_SAVE)
        after = h.get_mic_eq()
        print(
            f"  0x20[17] mic_volume = {after.mic_volume}"
            "  (observe headset — no crash = pass)"
        )


# ── Interactive mode ───────────────────────────────────────────────────────

def _imenu(title: str, options: list[str], is_root: bool = False) -> int | None:
    """Display a numbered menu; return 0-based index or None for back/exit."""
    back_label = "Exit" if is_root else "Back"
    print(f"\n{'─' * 54}")
    print(f"  {title}")
    print(f"{'─' * 54}")
    for i, label in enumerate(options, 1):
        print(f"  {i:>2}.  {label}")
    print(f"   0.  {back_label}")
    print()
    while True:
        try:
            raw = input("  > ").strip()
        except EOFError:
            return None
        if raw == "0":
            return None
        try:
            n = int(raw)
            if 1 <= n <= len(options):
                return n - 1
        except ValueError:
            pass
        print(f"  Enter a number between 0 and {len(options)}.")


def _iask(prompt: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        raw = input(f"  {prompt}{hint}: ").strip()
    except EOFError:
        return default
    return raw if raw else default


def _iask_float(prompt: str, lo: float, hi: float, default: float) -> float:
    while True:
        raw = _iask(prompt, str(default))
        try:
            v = float(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  Enter a number between {lo} and {hi}.")


def _iask_int(prompt: str, lo: int, hi: int, default: int) -> int:
    while True:
        raw = _iask(prompt, str(default))
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  Enter an integer between {lo} and {hi}.")


def _iask_choice(label: str, choices: list[str], default: str | None = None) -> str:
    print(f"  {label}:")
    for i, c in enumerate(choices, 1):
        mark = "  (default)" if c == default else ""
        print(f"    {i:>2}.  {c}{mark}")
    while True:
        try:
            raw = input(f"  > [1-{len(choices)}] ").strip()
        except EOFError:
            return default or choices[0]
        if not raw and default:
            return default
        try:
            n = int(raw)
            if 1 <= n <= len(choices):
                return choices[n - 1]
        except ValueError:
            pass
        print(f"  Enter 1-{len(choices)}.")


def _irun(handler, **kwargs) -> None:
    """Call a cmd_* handler with a fake Namespace, then wait for Enter."""
    try:
        handler(argparse.Namespace(**kwargs))
    except SystemExit as exc:
        if exc.code:
            print(f"  Error: {exc}")
    except Exception as exc:
        print(f"  Error: {exc}")
    input("\n  Press Enter to continue...")


def _isub_query(verify: bool) -> None:
    while True:
        sel = _imenu("Query commands", [
            "All queries  (status + miceq + firmware + serial)",
            "Status only  (0xB0)",
            "Mic/EQ only  (0x20)",
        ])
        if sel is None:
            return
        _irun([cmd_query, cmd_status, cmd_miceq][sel], verify=verify)


def _isub_listen(_verify: bool) -> None:
    print("\n  Event listener — interact with the headset. Ctrl-C to stop.")
    input("  Press Enter to start...\n")
    try:
        cmd_listen(argparse.Namespace(verify=False))
    except Exception as exc:
        print(f"  Error: {exc}")
    input("\n  Press Enter to continue...")


def _isub_audio(verify: bool) -> None:
    while True:
        sel = _imenu("Audio settings", [
            "volume           Set headset volume 0-100%",
            "mic-vol          Set mic volume 1-10",
            "sidetone         Set sidetone level",
            "anc              Set ANC mode",
            "transparency     Set transparency level 1-10",
            "gain             Set mic gain",
            "oled-brightness  Set OLED display brightness 1-10",
            "mic-led          Set mic LED brightness 1-10",
            "audio-output     Set audio output destination",
            "stream-volumes   Set stream volumes (main / aux / mic)",
            "chatmix          Enable or disable ChatMix",
        ])
        if sel is None:
            return
        if sel == 0:
            pct = _iask_float("Volume percent", 0.0, 100.0, 50.0)
            _irun(cmd_volume, pct=pct, verify=verify)
        elif sel == 1:
            v = _iask_int("Mic volume (1-10)", 1, 10, 5)
            _irun(cmd_mic_vol, level=v, verify=verify)
        elif sel == 2:
            c = _iask_choice("Sidetone level", ["off", "low", "medium", "high"])
            _irun(cmd_sidetone, level=c, verify=verify)
        elif sel == 3:
            c = _iask_choice("ANC mode", ["off", "transparency", "anc"])
            _irun(cmd_anc, mode=c, verify=verify)
        elif sel == 4:
            v = _iask_int("Transparency level (1-10)", 1, 10, 5)
            _irun(cmd_transparency, level=v, verify=verify)
        elif sel == 5:
            c = _iask_choice("Gain", ["low", "high"])
            _irun(cmd_gain, level=c, verify=verify)
        elif sel == 6:
            v = _iask_int("OLED brightness (1-10)", 1, 10, 5)
            _irun(cmd_oled_brightness, level=v, verify=verify)
        elif sel == 7:
            v = _iask_int("Mic LED brightness (1-10)", 1, 10, 5)
            _irun(cmd_mic_led, level=v, verify=verify)
        elif sel == 8:
            c = _iask_choice("Audio output", ["speakers", "stream"])
            _irun(cmd_audio_output, output=c, verify=verify)
        elif sel == 9:
            m  = _iask_int("Main stream volume (0-100)", 0, 100, 80)
            a  = _iask_int("Aux stream volume (0-100)",  0, 100, 80)
            mc = _iask_int("Mic stream volume (0-100)",  0, 100, 60)
            _irun(cmd_stream_volumes, main=m, aux=a, mic=mc, verify=verify)
        elif sel == 10:
            c = _iask_choice("ChatMix", ["on", "off"])
            _irun(cmd_chatmix, state=c, verify=verify)


def _isub_display_power(verify: bool) -> None:
    _TCHOICES = ["off", "1", "5", "10", "15", "30", "60"]
    while True:
        sel = _imenu("Display & Power", [
            "dim-timeout  Set OLED dim timeout",
            "home-screen  Set home screen mode",
            "auto-off     Set headset auto-off timeout",
        ])
        if sel is None:
            return
        if sel == 0:
            c = _iask_choice("Dim timeout (minutes; 'off' to disable)", _TCHOICES)
            _irun(cmd_dim_timeout, step=c, verify=verify)
        elif sel == 1:
            c = _iask_choice("Home screen mode", ["detailed", "simple"])
            _irun(cmd_home_screen, mode=c, verify=verify)
        elif sel == 2:
            c = _iask_choice("Auto-off timeout (minutes; 'off' to disable)", _TCHOICES)
            _irun(cmd_auto_off, step=c, verify=verify)


def _isub_connectivity(verify: bool) -> None:
    while True:
        sel = _imenu("Connectivity", [
            "wireless-mode  Set 2.4 GHz wireless mode",
            "bt-default     Set Bluetooth default on/off",
            "bt-auto-mute   Set Bluetooth auto-mute mode",
        ])
        if sel is None:
            return
        if sel == 0:
            c = _iask_choice("Wireless mode", ["performance", "extended"])
            _irun(cmd_wireless_mode, mode=c, verify=verify)
        elif sel == 1:
            c = _iask_choice("BT default", ["on", "off"])
            _irun(cmd_bt_default, state=c, verify=verify)
        elif sel == 2:
            c = _iask_choice("BT auto-mute", ["off", "-12db", "full"])
            _irun(cmd_bt_auto_mute, mode=c, verify=verify)


def _isub_eq(verify: bool) -> None:
    while True:
        sel = _imenu("EQ settings", [
            "eq-preset  Select EQ preset index (0x04 = custom EQ)",
            "eq-bands   Set 10 custom EQ band values (0-40, 20=flat)",
        ])
        if sel is None:
            return
        if sel == 0:
            raw = _iask("Preset index (hex or decimal, e.g. 0x04)", "0x04")
            try:
                idx = int(raw, 0)
            except ValueError:
                print("  Invalid value — use hex (0x..) or decimal.")
                input("  Press Enter to continue...")
                continue
            _irun(cmd_eq_preset, index=idx, verify=verify)
        elif sel == 1:
            print("  Enter 10 band values (0-40, 20=flat/0 dB), space-separated:")
            raw = _iask("Bands", "20 20 20 20 20 20 20 20 20 20")
            try:
                bands = [int(x) for x in raw.split()]
                if len(bands) != 10:
                    raise ValueError(f"need exactly 10, got {len(bands)}")
                for i, b in enumerate(bands):
                    if not 0 <= b <= 40:
                        raise ValueError(f"band {i + 1} out of range: {b}")
            except ValueError as exc:
                print(f"  Invalid input: {exc}")
                input("  Press Enter to continue...")
                continue
            _irun(cmd_eq_bands, bands=bands, verify=verify)


def _isub_oled(verify: bool) -> None:
    while True:
        sel = _imenu("OLED display", [
            "oled-clear    Blank the display",
            "oled-release  Return control to GG/Sonar",
            "oled-text     Draw static text",
            "oled-scroll   Scroll text across the display",
            "oled-img      Draw a static image",
            "oled-anim     Play a frame-by-frame animation",
            "oled-gif      Play a GIF animation",
        ])
        if sel is None:
            return
        if sel == 0:
            _irun(cmd_oled_clear, verify=verify)
        elif sel == 1:
            _irun(cmd_oled_release, verify=verify)
        elif sel == 2:
            text = _iask("Text to display")
            x    = _iask_int("X position (0-127)", 0, 127, 0)
            y    = _iask_int("Y position (0-63)",  0, 63,  0)
            inv  = _iask("Invert? [y/N]", "n").lower() in ("y", "yes")
            font = _iask("Font path (.ttf, blank=default)", "")
            _irun(cmd_oled_text, text=text, x=x, y=y, invert=inv,
                  font=font, font_size=16, verify=verify)
        elif sel == 3:
            text = _iask("Text to scroll")
            fps  = _iask_float("FPS", 1.0, 60.0, 20.0)
            inv  = _iask("Invert? [y/N]", "n").lower() in ("y", "yes")
            font = _iask("Font path (.ttf, blank=default)", "")
            _irun(cmd_oled_scroll, text=text, fps=fps, invert=inv,
                  font=font, font_size=16, verify=verify)
        elif sel == 4:
            path      = _iask("Image file path")
            threshold = _iask_int("Binarize threshold (0-255)", 0, 255, 128)
            _irun(cmd_oled_img, path=path, threshold=threshold, verify=verify)
        elif sel == 5:
            print("  Enter frame image paths one at a time; blank line when done.")
            frames: list[str] = []
            while True:
                fp = _iask(f"Frame {len(frames) + 1} path (blank to finish)", "")
                if not fp:
                    break
                frames.append(fp)
            if not frames:
                input("  No frames entered. Press Enter to continue...")
                continue
            fps       = _iask_float("FPS", 1.0, 60.0, 10.0)
            loops     = _iask_int("Loops (-1=infinite)", -1, 9999, 1)
            threshold = _iask_int("Binarize threshold (0-255)", 0, 255, 128)
            _irun(cmd_oled_anim, frames=frames, fps=fps, loops=loops,
                  threshold=threshold, verify=verify)
        elif sel == 6:
            path      = _iask("GIF file path")
            fps       = _iask_float("FPS (0=use embedded delays)", 0.0, 60.0, 0.0)
            loops     = _iask_int("Loops (-1=infinite)", -1, 9999, 1)
            threshold = _iask_int("Binarize threshold (0-255)", 0, 255, 128)
            _irun(cmd_oled_gif, path=path, fps=fps, loops=loops,
                  threshold=threshold, verify=verify)


def _isub_edge(verify: bool) -> None:
    while True:
        sel = _imenu("Edge cases (S9)", [
            "edge-volume-min    Set volume to 0%  (raw=0x38)",
            "edge-volume-max    Set volume to 100% (raw=0x00)",
            "edge-sidetone-oob  Raw sidetone byte — bypasses enum validation",
            "edge-mic-vol-oob   Raw mic volume byte — bypasses range validation",
        ])
        if sel is None:
            return
        if sel == 0:
            _irun(cmd_edge_volume_min, verify=verify)
        elif sel == 1:
            _irun(cmd_edge_volume_max, verify=verify)
        elif sel == 2:
            raw = _iask("Raw sidetone byte (hex or decimal)", "0x04")
            try:
                val = int(raw, 0)
            except ValueError:
                print("  Invalid value.")
                input("  Press Enter to continue...")
                continue
            _irun(cmd_edge_sidetone_oob, value=val, verify=verify)
        elif sel == 3:
            raw = _iask("Raw mic volume byte (hex or decimal)", "0x00")
            try:
                val = int(raw, 0)
            except ValueError:
                print("  Invalid value.")
                input("  Press Enter to continue...")
                continue
            _irun(cmd_edge_mic_vol_oob, value=val, verify=verify)


def _interactive_mode() -> None:
    verify = False
    categories: list[tuple[str, object]] = [
        ("Query commands",    _isub_query),
        ("Listen for events", _isub_listen),
        ("Audio settings",    _isub_audio),
        ("Display & Power",   _isub_display_power),
        ("Connectivity",      _isub_connectivity),
        ("EQ settings",       _isub_eq),
        ("OLED display",      _isub_oled),
        ("Edge cases",        _isub_edge),
    ]
    print()
    print("  Arctis Nova Pro -- Interactive Test CLI")
    print("  Connect the headset before continuing.")
    while True:
        v_state = "ON" if verify else "OFF"
        options = [label for label, _ in categories]
        options.append(f"Toggle verify after writes  (currently {v_state})")
        sel = _imenu("Main Menu", options, is_root=True)
        if sel is None:
            print("\n  Bye.\n")
            return
        if sel == len(categories):
            verify = not verify
            print(f"\n  Verify after writes is now {'ON' if verify else 'OFF'}.")
        else:
            categories[sel][1](verify)


# ── Argument parser ────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(
        prog="test_cli.py",
        description="Arctis Nova Pro — unified test CLI (covers TestChecklist.md)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Re-query after each write and show before/after field values",
    )
    p.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Launch interactive terminal menu (no subcommand needed)",
    )

    sub = p.add_subparsers(dest="command", required=False)

    # ── Query ──────────────────────────────────────────────────────────────
    sub.add_parser("query",  help="Run all four queries: status + miceq + firmware + serial (§2)")
    sub.add_parser("status", help="Query 0xB0 status packet (§2.1–2.5)")
    sub.add_parser("miceq",  help="Query 0x20 mic/EQ packet (§2.6–2.12)")

    # ── Listen ─────────────────────────────────────────────────────────────
    sub.add_parser("listen", help="Register all event callbacks, block until Ctrl-C (§1)")

    # ── Write — headset/audio ──────────────────────────────────────────────
    sp = sub.add_parser("volume", help="Set headset volume 0–100 (§4)")
    sp.add_argument("--pct", type=float, required=True, help="Volume percent (0–100)")

    sp = sub.add_parser("mic-vol", help="Set mic volume 1–10 (§4.1.5)")
    sp.add_argument("--level", type=int, required=True, metavar="LEVEL", help="1–10")

    sp = sub.add_parser("sidetone", help="Set sidetone level (§4.1.1–4.1.4)")
    sp.add_argument("--level", required=True, choices=["off", "low", "medium", "high"])

    sp = sub.add_parser("anc", help="Set ANC mode (§4.3.1–4.3.3)")
    sp.add_argument("--mode", required=True, choices=["off", "transparency", "anc"])

    sp = sub.add_parser("transparency", help="Set transparency level 1–10; auto-sets ANC mode (§4.3.4–4.3.5)")
    sp.add_argument("--level", type=int, required=True, metavar="LEVEL", help="1–10")

    sp = sub.add_parser("gain", help="Set mic gain (§4.2.8–4.2.9)")
    sp.add_argument("--level", required=True, choices=["low", "high"])

    sp = sub.add_parser("oled-brightness", help="Set OLED display brightness 1–10 (§4.1.6)")
    sp.add_argument("--level", type=int, required=True, metavar="LEVEL", help="1–10")

    sp = sub.add_parser("mic-led", help="Set mic mute LED brightness 1–10 (§4.2.5)")
    sp.add_argument("--level", type=int, required=True, metavar="LEVEL", help="1–10")

    sp = sub.add_parser("audio-output", help="Set audio output destination (§4)")
    sp.add_argument("--output", required=True, choices=["speakers", "stream"])

    sp = sub.add_parser("stream-volumes", help="Set stream output volumes 0–100 each (§4)")
    sp.add_argument("--main", type=int, required=True, help="Main stream volume 0–100")
    sp.add_argument("--aux",  type=int, required=True, help="Aux stream volume 0–100")
    sp.add_argument("--mic",  type=int, required=True, help="Mic stream volume 0–100")

    sp = sub.add_parser("chatmix", help="Enable or disable ChatMix dial (§4 ChatMix)")
    sp.add_argument("--state", required=True, choices=["on", "off"])

    # ── Write — display/power ──────────────────────────────────────────────
    sp = sub.add_parser("dim-timeout", help="Set OLED dim timeout (§4.2.1–4.2.2)")
    sp.add_argument("--step", required=True, choices=list(_TIMEOUT_MAP.keys()),
                    metavar="{off|1|5|10|15|30|60}")

    sp = sub.add_parser("home-screen", help="Set home screen display mode (§4.2.3–4.2.4)")
    sp.add_argument("--mode", required=True, choices=["detailed", "simple"])

    sp = sub.add_parser("auto-off", help="Set headset auto-off timeout (§4.2.6–4.2.7)")
    sp.add_argument("--step", required=True, choices=list(_TIMEOUT_MAP.keys()),
                    metavar="{off|1|5|10|15|30|60}")

    # ── Write — connectivity ───────────────────────────────────────────────
    sp = sub.add_parser("wireless-mode", help="Set 2.4 GHz wireless mode (§4)")
    sp.add_argument("--mode", required=True, choices=["performance", "extended"])

    sp = sub.add_parser("bt-default", help="Set Bluetooth default on/off (§4)")
    sp.add_argument("--state", required=True, choices=["on", "off"])

    sp = sub.add_parser("bt-auto-mute", help="Set Bluetooth auto-mute mode (§4)")
    sp.add_argument("--mode", required=True, choices=["off", "-12db", "full"])

    # ── Write — EQ (§5) ───────────────────────────────────────────────────
    sp = sub.add_parser("eq-preset", help="Select EQ preset index — 0x04=custom (§5)")
    sp.add_argument("--index", type=lambda x: int(x, 0), required=True,
                    help="Preset index (hex or decimal)")

    sp = sub.add_parser("eq-bands", help="Set 10 custom EQ band values, each 0–40 (20=flat) (§5.3)")
    sp.add_argument("--bands", nargs="+", type=int, required=True, metavar="BAND",
                    help="Exactly 10 values, each 0–40 (20=flat/0 dB)")

    # ── OLED (§10) ─────────────────────────────────────────────────────────
    sub.add_parser("oled-clear",   help="Blank the OLED display (§10.3.1)")
    sub.add_parser("oled-release", help="Return OLED control to GG/Sonar (§10.2.1)")

    sp = sub.add_parser("oled-text", help="Draw static text on OLED (§10.4)")
    sp.add_argument("--text",      required=True, help="Text to display")
    sp.add_argument("--x",         type=int,   default=0)
    sp.add_argument("--y",         type=int,   default=0)
    sp.add_argument("--invert",    action="store_true")
    sp.add_argument("--font",      default="", help="Path to .ttf font file")
    sp.add_argument("--font-size", type=int,   default=16)

    sp = sub.add_parser("oled-scroll", help="Scroll text across the OLED display (§10.5)")
    sp.add_argument("--text",      required=True, help="Text to scroll")
    sp.add_argument("--fps",       type=float, default=20.0)
    sp.add_argument("--invert",    action="store_true")
    sp.add_argument("--font",      default="",  help="Path to .ttf font file")
    sp.add_argument("--font-size", type=int,    default=16)

    sp = sub.add_parser("oled-img", help="Draw a static image on OLED (§10.3.3–10.3.7)")
    sp.add_argument("--path",      required=True, help="Path to image file")
    sp.add_argument("--threshold", type=int, default=128)

    sp = sub.add_parser("oled-anim", help="Play a frame-by-frame animation on OLED (§10.6)")
    sp.add_argument("--frames", nargs="+", required=True, help="Image files (one per frame)")
    sp.add_argument("-r", "--fps",       type=float, default=10.0)
    sp.add_argument("-l", "--loops",     type=int,   default=1, help="-1 = infinite")
    sp.add_argument("--threshold",       type=int,   default=128)

    sp = sub.add_parser("oled-gif", help="Play a GIF animation on OLED (§10.7)")
    sp.add_argument("--path",        required=True, help="Path to GIF file")
    sp.add_argument("--fps",         type=float, default=0.0, help="0 = use embedded GIF delays")
    sp.add_argument("-l", "--loops", type=int,   default=1,   help="-1 = infinite")
    sp.add_argument("--threshold",   type=int,   default=128)

    # ── Edge cases (§9) ────────────────────────────────────────────────────
    sub.add_parser("edge-volume-min", help="Set volume to 0%%; verify raw=0x38 (§9.7)")
    sub.add_parser("edge-volume-max", help="Set volume to 100%%; verify raw=0x00 (§9.8)")

    sp = sub.add_parser("edge-sidetone-oob",
                        help="Send raw sidetone byte, bypassing enum validation (§9.4)")
    sp.add_argument("--value", type=lambda x: int(x, 0), required=True,
                    help="Raw byte value (hex or decimal)")

    sp = sub.add_parser("edge-mic-vol-oob",
                        help="Send raw mic volume byte, bypassing range validation (§9.5–9.6)")
    sp.add_argument("--value", type=lambda x: int(x, 0), required=True,
                    help="Raw byte value (hex or decimal)")

    return p


# ── Handler dispatch ───────────────────────────────────────────────────────

_HANDLERS = {
    "query":              cmd_query,
    "status":             cmd_status,
    "miceq":              cmd_miceq,
    "listen":             cmd_listen,
    "volume":             cmd_volume,
    "mic-vol":            cmd_mic_vol,
    "sidetone":           cmd_sidetone,
    "anc":                cmd_anc,
    "transparency":       cmd_transparency,
    "gain":               cmd_gain,
    "oled-brightness":    cmd_oled_brightness,
    "mic-led":            cmd_mic_led,
    "dim-timeout":        cmd_dim_timeout,
    "home-screen":        cmd_home_screen,
    "auto-off":           cmd_auto_off,
    "chatmix":            cmd_chatmix,
    "wireless-mode":      cmd_wireless_mode,
    "bt-default":         cmd_bt_default,
    "bt-auto-mute":       cmd_bt_auto_mute,
    "audio-output":       cmd_audio_output,
    "stream-volumes":     cmd_stream_volumes,
    "eq-preset":          cmd_eq_preset,
    "eq-bands":           cmd_eq_bands,
    "oled-clear":         cmd_oled_clear,
    "oled-release":       cmd_oled_release,
    "oled-text":          cmd_oled_text,
    "oled-scroll":        cmd_oled_scroll,
    "oled-img":           cmd_oled_img,
    "oled-anim":          cmd_oled_anim,
    "oled-gif":           cmd_oled_gif,
    "edge-volume-min":    cmd_edge_volume_min,
    "edge-volume-max":    cmd_edge_volume_max,
    "edge-sidetone-oob":  cmd_edge_sidetone_oob,
    "edge-mic-vol-oob":   cmd_edge_mic_vol_oob,
}


def main() -> None:
    args = build_parser().parse_args()
    if args.interactive:
        _interactive_mode()
        return
    if not args.command:
        build_parser().print_help()
        sys.exit(2)
    _HANDLERS[args.command](args)


if __name__ == "__main__":
    main()
