"""Render assets/demo.gif from a pre-recorded self-heal transcript.

Pure Python + Pillow — no external recording tools required.
Produces an animated GIF that progressively reveals the terminal session.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# -- Look & feel --------------------------------------------------------------

WIDTH = 960
HEIGHT = 560
PAD_X = 28
PAD_Y = 22
LINE_HEIGHT = 22
FONT_SIZE = 15
BG = (13, 17, 23)                # GitHub-dark
FG = (201, 209, 217)             # primary text
DIM = (139, 148, 158)            # muted
ACCENT_GREEN = (126, 231, 135)
ACCENT_RED = (248, 81, 73)
ACCENT_BLUE = (88, 166, 255)
ACCENT_YELLOW = (210, 153, 34)

FONT_PATHS = [
    "C:/Windows/Fonts/consola.ttf",
    "C:/Windows/Fonts/CascadiaMono.ttf",
    "C:/Windows/Fonts/lucon.ttf",
]


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


# -- Scripted transcript ------------------------------------------------------

# Each entry is (text, color, delay_ms_after_this_line)
# "text" may be multi-line. We split on newlines when rendering.

SCRIPT: list[tuple[str, tuple[int, int, int], int]] = [
    ("$ cat mymod.py",                                          FG,            900),
    ('"""self-heal demo: naive price parser that heals itself."""',  DIM,    150),
    ("",                                                        FG,             50),
    ("from self_heal import repair",                            FG,             80),
    ("from self_heal.llm import GeminiProposer",                FG,            140),
    ("",                                                        FG,             50),
    ("def test_dollars(fn):     assert fn(\"$12.99\") == 12.99",     FG,       120),
    ("def test_dollars_comma(fn): assert fn(\"$1,299.00\") == 1299.0", FG,     120),
    ("def test_rupees(fn):      assert fn(\"\u20b91,299\") == 1299.0",  FG,    180),
    ("",                                                        FG,             50),
    ("@repair(tests=[test_dollars, test_dollars_comma, test_rupees],", ACCENT_YELLOW, 100),
    ("        proposer=GeminiProposer(model=\"gemini-2.5-flash\"))",   ACCENT_YELLOW, 200),
    ("def extract_price(text: str) -> float:",                  FG,            120),
    ("    # Naive: only handles \"$X.YY\"",                     DIM,           100),
    ("    return float(text.replace(\"$\", \"\"))",             FG,            900),
    ("",                                                        FG,             50),
    ("$ python mymod.py",                                       FG,            900),
    ("[self-heal] Attempt 1 failed: ValueError: could not convert string to float: '\u20b91,299'",
                                                                ACCENT_RED,   1100),
    ("[self-heal] Proposing repair...",                         DIM,          1100),
    ("[self-heal] Repair applied, retrying...",                 DIM,           800),
    ("[self-heal] Attempt 2 succeeded after repair.",           ACCENT_GREEN, 1000),
    ("",                                                        FG,             50),
    ("  \u20b91,299  ->  1299.0",                               ACCENT_BLUE,  1200),
    ("  (healed in 2 attempts)",                                DIM,          2500),
]


def render_frame(
    lines: list[tuple[str, tuple[int, int, int]]],
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    _draw_chrome(draw, font)

    # Start below the chrome bar.
    y = PAD_Y + 32
    visible = lines[-_max_visible_lines():]
    for text, color in visible:
        if text == "":
            y += LINE_HEIGHT
            continue
        draw.text((PAD_X, y), text, font=font, fill=color)
        y += LINE_HEIGHT

    return img


def _max_visible_lines() -> int:
    return (HEIGHT - PAD_Y - 32 - PAD_Y) // LINE_HEIGHT


def _draw_chrome(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont) -> None:
    # Window header bar.
    draw.rectangle((0, 0, WIDTH, 30), fill=(22, 27, 34))
    draw.line((0, 30, WIDTH, 30), fill=(48, 54, 61), width=1)
    # Dots
    for i, color in enumerate([(248, 81, 73), (210, 153, 34), (126, 231, 135)]):
        cx = 18 + i * 18
        draw.ellipse((cx - 6, 9, cx + 6, 21), fill=color)
    # Title
    draw.text(
        (WIDTH // 2 - 40, 7),
        "self-heal demo",
        font=font,
        fill=DIM,
    )


def build_gif(output_path: Path) -> None:
    font = _load_font(FONT_SIZE)

    accumulated: list[tuple[str, tuple[int, int, int]]] = []
    frames: list[Image.Image] = []
    durations: list[int] = []

    # Initial blank frame (brief pause before first line appears).
    frames.append(render_frame(accumulated, font))
    durations.append(400)

    for text, color, delay in SCRIPT:
        accumulated.append((text, color))
        frames.append(render_frame(accumulated, font))
        durations.append(delay)

    # Hold on the final frame so the loop doesn't restart too fast.
    frames.append(render_frame(accumulated, font))
    durations.append(2500)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"wrote {output_path}  ({len(frames)} frames, "
          f"{sum(durations) / 1000:.1f}s)")


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assets/demo.gif")
    build_gif(out)
