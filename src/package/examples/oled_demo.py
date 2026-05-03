"""OLED display demo — mirrors the ggoled CLI feature set.

Usage:
    # requires: pip install 'arctis-hid[oled]'

    python oled_demo.py brightness 3
    python oled_demo.py text "Hello, World!"
    python oled_demo.py img cool_image.png
    python oled_demo.py anim frame1.png frame2.png frame3.png
    python oled_demo.py anim --fps 10 --loops 20 frame1.png frame2.png frame3.png
    python oled_demo.py gif animation.gif
    python oled_demo.py gif --fps 15 animation.gif
    python oled_demo.py release
"""

import argparse
import sys

from arctis_hid import discover


def cmd_brightness(args: argparse.Namespace) -> None:
    level = args.level
    if not 1 <= level <= 10:
        sys.exit("brightness must be 1–10")
    with discover() as h:
        h.set_oled_brightness(level)
        print(f"Brightness set to {level}")


def cmd_text(args: argparse.Namespace) -> None:
    font = None
    if args.font:
        from PIL import ImageFont
        font = ImageFont.truetype(args.font, size=args.font_size)
    with discover() as h:
        h.oled.draw_text(args.text, font=font, x=args.x, y=args.y, invert=args.invert)
        print(f"Text drawn: {args.text!r}")


def cmd_scroll(args: argparse.Namespace) -> None:
    font = None
    if args.font:
        from PIL import ImageFont
        font = ImageFont.truetype(args.font, size=args.font_size)
    with discover() as h:
        h.oled.scroll_text(args.text, font=font, fps=args.fps, invert=args.invert)
        print("Scroll complete")


def cmd_img(args: argparse.Namespace) -> None:
    with discover() as h:
        h.oled.draw_image(args.path, threshold=args.threshold)
        print(f"Image drawn: {args.path}")


def cmd_anim(args: argparse.Namespace) -> None:
    loops = 0 if args.loops < 0 else args.loops
    with discover() as h:
        h.oled.play_animation(
            args.frames,
            fps=args.fps,
            loops=loops,
            threshold=args.threshold,
        )
        print("Animation complete")


def cmd_gif(args: argparse.Namespace) -> None:
    loops = 0 if args.loops < 0 else args.loops
    with discover() as h:
        h.oled.play_gif(
            args.path,
            fps=args.fps if args.fps else None,
            loops=loops,
            threshold=args.threshold,
        )
        print("GIF complete")


def cmd_release(args: argparse.Namespace) -> None:
    with discover() as h:
        h.oled.release()
        print("OLED control returned to GG / Sonar")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Arctis Nova Pro OLED demo")
    sub = p.add_subparsers(dest="command", required=True)

    # brightness
    b = sub.add_parser("brightness", help="Set OLED brightness (1–10)")
    b.add_argument("level", type=int)

    # text
    t = sub.add_parser("text", help="Draw static text")
    t.add_argument("text")
    t.add_argument("--font", default="", help="Path to .ttf font file")
    t.add_argument("--font-size", type=int, default=16)
    t.add_argument("--x", type=int, default=0)
    t.add_argument("--y", type=int, default=0)
    t.add_argument("--invert", action="store_true")

    # scroll
    s = sub.add_parser("scroll", help="Scroll text across the display")
    s.add_argument("text")
    s.add_argument("--font", default="")
    s.add_argument("--font-size", type=int, default=16)
    s.add_argument("--fps", type=float, default=20.0)
    s.add_argument("--invert", action="store_true")

    # img
    i = sub.add_parser("img", help="Draw a static image (PNG, JPG, …)")
    i.add_argument("path")
    i.add_argument("--threshold", type=int, default=128)

    # anim
    a = sub.add_parser("anim", help="Play a frame-by-frame animation")
    a.add_argument("frames", nargs="+", help="Image files (one per frame)")
    a.add_argument("-r", "--fps", type=float, default=10.0)
    a.add_argument("-l", "--loops", type=int, default=1, help="-1 = loop forever")
    a.add_argument("--threshold", type=int, default=128)

    # gif
    g = sub.add_parser("gif", help="Play a GIF animation")
    g.add_argument("path")
    g.add_argument("--fps", type=float, default=0.0, help="0 = use embedded GIF delays")
    g.add_argument("-l", "--loops", type=int, default=1, help="-1 = loop forever")
    g.add_argument("--threshold", type=int, default=128)

    # release
    sub.add_parser("release", help="Return OLED control to GG / Sonar")

    return p


def main() -> None:
    args = build_parser().parse_args()
    handlers = {
        "brightness": cmd_brightness,
        "text": cmd_text,
        "scroll": cmd_scroll,
        "img": cmd_img,
        "anim": cmd_anim,
        "gif": cmd_gif,
        "release": cmd_release,
    }
    handlers[args.command](args)


if __name__ == "__main__":
    main()
