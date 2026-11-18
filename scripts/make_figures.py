"""Makes the media committed in docs/media/ from the local tours in .local/visualization/ (gitignored):

- figures/: the hero image and before-and-after pairs
- gifs/: short feature GIFs for the README, cut from the tour recordings
- iterations/: one contact sheet of screenshots per version, for the iteration log

Usage: python3 scripts/make_figures.py
"""

import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "visualization"
TOURS = LOCAL / "tours"
OUT = ROOT / "docs" / "media"
CREAM, MOSS, SAFFRON, INK, MUTED = "#F6F1E7", "#3F5B45", "#C26A2D", "#2B2A26", "#6E6A60"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# Feature GIFs: name, source recording, start and length in seconds, speed.
GIFS = (
    ("join_and_check_in", TOURS / "v0.4" / "student_tour_small.mp4", 22.0, 7.5, 1.0),
    ("breathe", TOURS / "v0.4" / "student_tour_small.mp4", 43.4, 10.2, 1.0),
    ("ask", TOURS / "v0.4" / "student_tour_small.mp4", 57.4, 9.0, 1.0),
    ("hindi", TOURS / "v0.4" / "student_tour_small.mp4", 69.5, 9.5, 1.0),
    ("teacher_shares_link", TOURS / "v0.4" / "teacher_tour_small.mp4", 26.5, 9.5, 1.0),
    ("two_phones", LOCAL / "two_phones_v0.4.mp4", 44.0, 88.0, 4.0),
)
# Contact sheets: version folder and a caption.
SHEETS = (
    ("v0.1", "v0.1, first tour: the findings are in docs/iterations/v0.1.md"),
    ("v0.2", "v0.2: after the first round of fixes"),
    ("v0.4", "v0.4: after the code review and the Marathi notes"),
    ("v0.4-two-phones", "v0.4: two phones, one server (teacher and students, in order)"),
)


def phone(path: Path, height: int) -> Image.Image:
    """A screenshot with rounded corners and a thin dark bezel, `height` pixels tall."""
    shot = Image.open(path).convert("RGB")
    shot = shot.resize((round(shot.width * height / shot.height), height), Image.LANCZOS)
    bezel = 10
    radius = height // 22
    frame = Image.new("RGBA", (shot.width + 2 * bezel, shot.height + 2 * bezel), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, frame.height - 1], radius + bezel, fill="#1F1F1C")
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], radius, fill=255)
    frame.paste(shot, (bezel, bezel), mask)
    return frame


def place(canvas: Image.Image, item: Image.Image, xy: tuple[int, int]) -> None:
    """Pastes `item` with a soft shadow."""
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    alpha = item.split()[3].point(lambda a: 70 if a else 0)
    shadow.paste((0, 0, 0, 255), (xy[0] + 14, xy[1] + 22), alpha)
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(22)))
    canvas.alpha_composite(item, xy)


def wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def hero() -> None:
    """The README's first image. hero_teacher and hero_today were taken at a quiet hour, so they show the regular
    8:00 AM class rather than the tour's extra class 20 minutes ahead."""
    shots = TOURS / "v0.4"
    canvas = Image.new("RGBA", (2400, 1350), CREAM)
    draw = ImageDraw.Draw(canvas)
    draw.text((120, 260), "Satt Chitt Anand", font=ImageFont.truetype(SERIF, 104), fill=MOSS)
    draw.text((124, 410), "TRUTH · CONSCIOUSNESS · BLISS", font=ImageFont.truetype(SANS_BOLD, 30), fill=SAFFRON)
    body = ImageFont.truetype(SANS, 38)
    text = ("An app for an online yoga studio and its students: today's class and its Google Meet link, "
            "one-tap check-ins, sharing to the class WhatsApp group, and a practice assistant (Gemma 4) "
            "that answers in English, Hindi and Marathi.")
    for i, line in enumerate(wrap(draw, text, body, 860)):
        draw.text((124, 500 + i * 56), line, font=body, fill=INK)
    draw.text((124, 1180), "Screens from v0.4, synthetic demo data", font=ImageFont.truetype(SANS, 26), fill=MUTED)
    for name, x, y in (("hero_teacher", 1080, 170), ("hero_today", 1470, 90), ("08_ask_answer", 1860, 170)):
        place(canvas, phone(shots / f"{name}.png", 1080), (x, y))
    canvas.convert("RGB").save(OUT / "figures" / "hero.png", optimize=True)


def before_after(name: str, before: Path, after: Path, before_note: str, after_note: str) -> None:
    """Two phones side by side under their captions. Captions are English only: no font here shapes Devanagari."""
    height = 1000
    left, right = phone(before, height), phone(after, height)
    label, note = ImageFont.truetype(SANS_BOLD, 34), ImageFont.truetype(SANS, 28)
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    captions = [wrap(measure, text, note, item.width) for item, text in ((left, before_note), (right, after_note))]
    top = 110 + max(len(c) for c in captions) * 38 + 40
    canvas = Image.new("RGBA", (left.width + right.width + 360, top + height + 80), CREAM)
    draw = ImageDraw.Draw(canvas)
    for item, x, title, lines, color in ((left, 120, "BEFORE", captions[0], MUTED), (right, 240 + left.width, "AFTER", captions[1], MOSS)):
        draw.text((x, 50), title, font=label, fill=color)
        for i, line in enumerate(lines):
            draw.text((x, 100 + i * 38), line, font=note, fill=INK)
        place(canvas, item, (x, top))
    canvas.convert("RGB").save(OUT / "figures" / f"{name}.png", optimize=True)


def gif(name: str, source: Path, start: float, seconds: float, speed: float) -> None:
    """A looping GIF, 300 px wide (two phones: 600), 10 frames a second."""
    width = 600 if name == "two_phones" else 300
    chain = (f"setpts=PTS/{speed},fps=10,scale={width}:-1:flags=lanczos,split[a][b];"
             "[a]palettegen=max_colors=128:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(start), "-t", str(seconds), "-i", str(source),
                    "-filter_complex", chain, "-loop", "0", str(OUT / "gifs" / f"{name}.gif")], check=True)


def sheet(version: str, caption: str) -> None:
    """Every numbered screenshot of one tour in a grid, as a JPEG small enough to commit."""
    files = sorted((TOURS / version).glob("[0-9]*.png"))
    cols, width = 8, 260
    tiles = [Image.open(f).convert("RGB") for f in files]
    tiles = [t.resize((width, round(t.height * width / t.width)), Image.LANCZOS) for t in tiles]
    tile_h = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    canvas = Image.new("RGB", (cols * (width + 16) + 16, rows * (tile_h + 44) + 90), CREAM)
    draw = ImageDraw.Draw(canvas)
    draw.text((16, 24), caption, font=ImageFont.truetype(SANS_BOLD, 28), fill=MOSS)
    small = ImageFont.truetype(SANS, 16)
    for k, (tile, file) in enumerate(zip(tiles, files, strict=True)):
        x, y = 16 + (k % cols) * (width + 16), 80 + (k // cols) * (tile_h + 44)
        canvas.paste(tile, (x, y))
        draw.text((x, y + tile.height + 6), file.stem.replace("_", " "), font=small, fill=MUTED)
    canvas.save(OUT / "iterations" / f"{version}.jpg", quality=82, optimize=True)


def main() -> None:
    if not TOURS.is_dir():
        raise SystemExit(f"{TOURS} is missing: run scripts/capture_tour.py first")
    for folder in ("figures", "gifs", "iterations"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    hero()
    before_after(
        "signup_v0.1_v0.2", TOURS / "v0.1" / "02_signup_login_hidden.png", TOURS / "v0.2" / "02_signup.png",
        "v0.1: a returning student had to scroll past the whole sign-up form to find 'Log in'.",
        "v0.2: 'Create account' and 'Log in' sit side by side above the form.",
    )
    before_after(
        "ask_hindi_v0.1_v0.2", TOURS / "v0.1" / "10_ask_hindi_food_miss.png", TOURS / "v0.2" / "11_ask_hindi.png",
        "v0.1: asked in Hindi, 'What should I eat before class?' uses an inflected verb the notes' keywords did "
        "not list, so the assistant found no notes and said it did not know.",
        "v0.2: inflected Hindi and Marathi forms added to the notes' keywords; a test now covers every suggested "
        "question in all three languages.",
    )
    for spec in GIFS:
        gif(*spec)
    for spec in SHEETS:
        sheet(*spec)
    print(f"media in {OUT}")


if __name__ == "__main__":
    main()
