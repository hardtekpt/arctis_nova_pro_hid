from __future__ import annotations

import itertools
import time
from pathlib import Path
from typing import Union

from ...core.transport import HidTransport
from ...exceptions import DeviceIOError
from ..base import AbstractOled
from . import constants as C

try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL = True
except ImportError:
    _PIL = False

# Pure pixel bytes: 128 columns × (64 pixels / 8 bits) = 1024 bytes
BITMAP_SIZE = C.OLED_WIDTH * (C.OLED_HEIGHT // 8)


def _require_pil() -> None:
    if not _PIL:
        raise ImportError("Install Pillow: pip install 'arctis-hid[oled]'")


def _open_image(src: Union["Image.Image", str, Path]) -> "Image.Image":
    if isinstance(src, (str, Path)):
        return Image.open(src)
    return src


def encode_frame(img: "Image.Image", threshold: int = 128) -> bytes:
    """Convert a PIL image to the 128×64 column-major 1-bit bitmap.

    Pixel layout (from ggoled): columns left-to-right, within each column
    bits run top-to-bottom packed LSB-first (bit 0 = y=0 = top).
    """
    img = img.resize((C.OLED_WIDTH, C.OLED_HEIGHT), Image.LANCZOS).convert("L")
    pixels = img.load()
    bpc = C.OLED_HEIGHT // 8  # bytes per column = 8
    buf = bytearray(BITMAP_SIZE)
    for x in range(C.OLED_WIDTH):
        for y in range(C.OLED_HEIGHT):
            if pixels[x, y] >= threshold:
                buf[x * bpc + y // 8] |= 1 << (y % 8)
    return bytes(buf)


class ArctisNovaProOled(AbstractOled):
    """OLED controller for the Arctis Nova Pro Wireless.

    Protocol confirmed via ggoled (https://github.com/JerwuQu/ggoled):
      - 0x93 feature report, 1024 bytes, column-major 1-bit bitmap, two 64-px chunks.
      - 0x95 interrupt write returns control to GG / Sonar.
    """

    def __init__(self, transport: HidTransport) -> None:
        self._transport = transport

    # ── AbstractOled ───────────────────────────────────────────────────────

    @property
    def width(self) -> int:
        return C.OLED_WIDTH

    @property
    def height(self) -> int:
        return C.OLED_HEIGHT

    def draw_raw(self, bitmap: bytes) -> None:
        """Send a pre-encoded column-major 1-bit bitmap (1024 bytes)."""
        if len(bitmap) != BITMAP_SIZE:
            raise ValueError(f"bitmap must be {BITMAP_SIZE} bytes, got {len(bitmap)}")
        self._send_frame(bitmap)

    def clear(self) -> None:
        """Blank the display (all pixels off)."""
        self._send_frame(bytes(BITMAP_SIZE))

    def release(self) -> None:
        """Return OLED control to GG / Sonar."""
        self._transport.write(C.CMD_OLED_RELEASE)

    # ── High-level drawing API ─────────────────────────────────────────────

    def draw_image(
        self,
        image: Union["Image.Image", str, Path],
        threshold: int = 128,
    ) -> None:
        """Draw a static image. Accepts a PIL Image or a file path (PNG, JPG, GIF…)."""
        _require_pil()
        self._send_frame(encode_frame(_open_image(image).convert("RGBA"), threshold))

    def draw_text(
        self,
        text: str,
        font: "ImageFont.FreeTypeFont | ImageFont.ImageFont | None" = None,
        x: int = 0,
        y: int = 0,
        invert: bool = False,
    ) -> None:
        """Render text onto the display.

        font: PIL ImageFont object (FreeType or bitmap), or None for the built-in default.
        invert: swap foreground/background (white text on black vs black on white).
        """
        _require_pil()
        bg, fg = (255, 0) if invert else (0, 255)
        canvas = Image.new("L", (C.OLED_WIDTH, C.OLED_HEIGHT), color=bg)
        draw = ImageDraw.Draw(canvas)
        if font is None:
            font = _default_font()
        draw.text((x, y), text, fill=fg, font=font)
        self._send_frame(encode_frame(canvas))

    def scroll_text(
        self,
        text: str,
        font: "ImageFont.FreeTypeFont | ImageFont.ImageFont | None" = None,
        fps: float = 20.0,
        invert: bool = False,
    ) -> None:
        """Scroll text across the display from right to left (one full pass)."""
        _require_pil()
        if font is None:
            font = _default_font()
        bbox = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        full_w = text_w + 2 * C.OLED_WIDTH
        bg, fg = (255, 0) if invert else (0, 255)
        canvas = Image.new("L", (full_w, C.OLED_HEIGHT), bg)
        ImageDraw.Draw(canvas).text(
            (C.OLED_WIDTH, (C.OLED_HEIGHT - text_h) // 2),
            text, fill=fg, font=font,
        )

        delay = 1.0 / fps
        for offset in range(full_w - C.OLED_WIDTH + 1):
            crop = canvas.crop((offset, 0, offset + C.OLED_WIDTH, C.OLED_HEIGHT))
            self._send_frame(encode_frame(crop))
            time.sleep(delay)

    def play_animation(
        self,
        frames: list,
        fps: float = 10.0,
        loops: int = 1,
        threshold: int = 128,
    ) -> None:
        """Play a sequence of PIL Images (or file paths) as an animation.

        loops=0 plays forever.
        """
        _require_pil()
        bitmaps = [encode_frame(_open_image(f).convert("RGBA"), threshold) for f in frames]
        delay = 1.0 / fps
        for _ in (range(loops) if loops > 0 else itertools.count()):
            for bm in bitmaps:
                self._send_frame(bm)
                time.sleep(delay)

    def play_gif(
        self,
        path: Union[str, Path],
        fps: float | None = None,
        loops: int = 1,
        threshold: int = 128,
    ) -> None:
        """Play a GIF animation.

        fps: override per-frame delay; None uses the GIF's embedded delays.
        loops=0 plays forever.
        """
        _require_pil()
        gif = Image.open(path)
        frames: list[bytes] = []
        delays: list[float] = []
        while True:
            frames.append(encode_frame(gif.copy().convert("RGBA"), threshold))
            delays.append(gif.info.get("duration", 100) / 1000.0)
            try:
                gif.seek(gif.tell() + 1)
            except EOFError:
                break

        for _ in (range(loops) if loops > 0 else itertools.count()):
            for bm, gdelay in zip(frames, delays):
                self._send_frame(bm)
                time.sleep(1.0 / fps if fps else gdelay)

    # ── Internals ──────────────────────────────────────────────────────────

    def _send_frame(self, bitmap: bytes) -> None:
        """Split a 128-wide bitmap into two 64-column 0x93 feature reports."""
        bpc = C.OLED_HEIGHT // 8          # bytes per column = 8
        half_w = C.OLED_REPORT_SPLIT_SZ   # 64

        for chunk in range(C.OLED_REPORTS_PER_FRAME):
            dst_x = chunk * half_w
            col_bytes = bytearray()
            for x in range(dst_x, dst_x + half_w):
                start = x * bpc
                col_bytes.extend(bitmap[start: start + bpc])

            # payload = everything after the report-ID byte; total report = 1024 bytes
            payload = bytearray(C.OLED_REPORT_SIZE - 1)
            payload[0] = C.CMD_OLED_DRAW
            payload[1] = dst_x
            payload[2] = 0           # dst_y (always 0 — full-height chunk)
            payload[3] = half_w      # chunk width = 64
            payload[4] = C.OLED_HEIGHT  # padded height = 64 (multiple of 8)
            payload[5: 5 + len(col_bytes)] = col_bytes
            self._send_report(bytes(payload))

    def _send_report(self, payload: bytes) -> None:
        """Write a feature-report payload with exponential-backoff retry (like ggoled)."""
        for attempt in range(10):
            try:
                self._transport.write_feature_report(C.REPORT_ID, payload)
                return
            except DeviceIOError:
                if attempt == 9:
                    raise
                time.sleep((attempt + 1) ** 2 / 1000.0)


def _default_font() -> "ImageFont.ImageFont":
    try:
        return ImageFont.load_default(size=16)
    except TypeError:
        return ImageFont.load_default()
