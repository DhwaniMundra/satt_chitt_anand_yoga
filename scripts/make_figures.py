"""Makes the README's pictures in docs/media/ from the local tours in .local/visualization/ (gitignored):

- figures/hero.png and figures/before_after.png
- gifs/students.gif, gifs/teacher.gif, gifs/two_phones.gif: landscape strips of phones, each playing its own real clip
- iterations/<version>.jpg: every screenshot of one tour on one sheet, for the iteration log

The diagrams are drawn separately by make_diagrams.py. Usage: tools/media-venv/bin/python scripts/make_figures.py
"""

import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from make_diagrams import sora

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "visualization"
TOURS = LOCAL / "tours"
WORK = LOCAL / "work" / "figures"
OUT = ROOT / "docs" / "media"
CREAM, PAPER, MOSS, SAFFRON, INK, MUTED = "#F6F1E7", "#FFFCF6", "#3F5B45", "#C26A2D", "#2B2A26", "#6E6A60"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
FPS = 8
STUDENT_TOUR = TOURS / "v0.4" / "student_tour_small.mp4"
TEACHER_TOUR = TOURS / "v0.4" / "teacher_tour_small.mp4"


def face(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(sora(weight)), size)


def serif(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(SERIF, size)


def phone(shot: Image.Image, height: int) -> Image.Image:
    """A screen with rounded corners in a thin dark bezel, `height` pixels tall."""
    bezel = max(6, height // 90)
    inner = height - 2 * bezel
    shot = shot.convert("RGB").resize((round(shot.width * inner / shot.height), inner), Image.LANCZOS)
    radius = inner // 22
    frame = Image.new("RGBA", (shot.width + 2 * bezel, height), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, height - 1], radius + bezel, fill="#1F1F1C")
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], radius, fill=255)
    frame.paste(shot, (bezel, bezel), mask)
    return frame


def shadow(size: tuple[int, int]) -> Image.Image:
    pad = 40
    layer = Image.new("RGBA", (size[0] + 2 * pad, size[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle([pad + 6, pad + 14, pad + size[0] + 6, pad + size[1] + 14], 40, fill=(0, 0, 0, 60))
    return layer.filter(ImageFilter.GaussianBlur(16))


def place(canvas: Image.Image, item: Image.Image, xy: tuple[int, int], drop: Image.Image | None = None) -> None:
    drop = drop or shadow(item.size)
    canvas.alpha_composite(drop, (xy[0] - 40, xy[1] - 40))
    canvas.alpha_composite(item, xy)


def wrap(text: str, font: ImageFont.FreeTypeFont, width: int) -> list[str]:
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if measure.textlength(trial, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = trial
    return lines + [line]


def frames(name: str, source: Path, start: float, seconds: float, speed: float = 1.0) -> list[Path]:
    """A clip cut from a recording into PNG frames at FPS, cached in WORK."""
    folder = WORK / "clips" / name
    if not folder.exists() or not any(folder.iterdir()):
        folder.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(seconds), "-i", str(source),
                        # Sampling at FPS / speed plays back `speed` times faster at FPS. (setpts does not work on
                        # the two-phone recording: its timestamps come from joining two recordings.)
                        "-vf", f"fps={FPS / speed}", str(folder / "%04d.png")], check=True)
    return sorted(folder.glob("*.png"))


def write_gif(name: str, pictures: list[Image.Image]) -> None:
    folder = WORK / "gif" / name
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    for i, picture in enumerate(pictures):
        picture.convert("RGB").save(folder / f"{i:04d}.png")
    chain = ("split[a][b];[a]palettegen=max_colors=160:stats_mode=diff[p];"
             "[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(folder / "%04d.png"),
                    "-filter_complex", chain, "-loop", "0", str(OUT / "gifs" / f"{name}.gif")], check=True)


def strip(name: str, title: str, panels: list[tuple], seconds: float = 10.0) -> None:
    """A row of phones under a title, each with a caption; each phone loops its own clip, or shows a still."""
    width, phone_h, top = 1500, 640, 120
    gap = width // len(panels)
    sources = [frames(*p[2]) if p[2][1].suffix == ".mp4" else [p[2][1]] for p in panels]
    stills = {k: phone(Image.open(src[0]), phone_h) for k, src in enumerate(sources) if len(src) == 1}
    sample = next(iter(stills.values()), None) or phone(Image.open(sources[0][0]), phone_h)
    drop = shadow(sample.size)
    base = Image.new("RGBA", (width, top + phone_h + 140), CREAM)
    draw = ImageDraw.Draw(base)
    draw.text((50, 36), title, font=serif(46), fill=MOSS)
    for k, (label, note, _) in enumerate(panels):
        cx = gap * k + gap // 2
        draw.text((cx, top + phone_h + 34), label, font=face(26, 700), fill=MOSS, anchor="ma")
        draw.text((cx, top + phone_h + 72), note, font=face(21, 400), fill=MUTED, anchor="ma")
    pictures = []
    for i in range(int(seconds * FPS)):
        canvas = base.copy()
        for k, source in enumerate(sources):
            item = stills.get(k) or phone(Image.open(source[i % len(source)]), phone_h)
            place(canvas, item, (gap * k + gap // 2 - item.width // 2, top), drop)
        pictures.append(canvas)
    write_gif(name, pictures)


def two_phones() -> None:
    """The two-phone recording beside the story it tells."""
    width, phone_h, top = 1500, 680, 70
    clip = frames("two_phones", LOCAL / "two_phones_v0.4.mp4", 44.0, 94.0, 5.0)  # to the teacher's Insights
    base = Image.new("RGBA", (width, phone_h + 2 * top), CREAM)
    draw = ImageDraw.Draw(base)
    draw.text((60, 90), "Two phones,", font=serif(50), fill=MOSS)
    draw.text((60, 150), "one server", font=serif(50), fill=MOSS)
    steps = ("The teacher pastes the Meet link and shares it.",
             "A student signs up with the group code and joins.",
             "One tap before class, one after.",
             "The teacher sees the check-in arrive.")
    y = 260
    for n, step in enumerate(steps, 1):
        draw.ellipse([60, y, 100, y + 40], fill=SAFFRON)
        draw.text((80, y + 20), str(n), font=face(22, 700), fill="white", anchor="mm")
        for row, line in enumerate(wrap(step, face(24), 470)):
            draw.text((120, y + 4 + row * 34), line, font=face(24), fill=INK)
        y += 100
    draw.text((60, phone_h + 2 * top - 50), "Real recording, sped up 5x. Test people only.", font=face(19), fill=MUTED)
    labels = ("Teacher", "Student")
    drop = None
    pictures = []
    for path in clip:
        canvas = base.copy()
        both = Image.open(path).convert("RGB")
        half = both.width // 2
        for k in range(2):
            item = phone(both.crop((k * half, 0, (k + 1) * half, both.height)), phone_h)
            drop = drop or shadow(item.size)
            x = 690 + k * (item.width + 70)
            place(canvas, item, (x, top), drop)
        pictures.append(canvas)
    for picture in pictures:
        d = ImageDraw.Draw(picture)
        for k, label in enumerate(labels):
            d.text((690 + k * (drop.width - 80 + 70) + (drop.width - 80) // 2, top - 36), label.upper(), font=face(20, 700),
                   fill=SAFFRON, anchor="ma")
    write_gif("two_phones", pictures)


def hero() -> None:
    """The README's first image. hero_teacher and hero_today were taken at a quiet hour, so they show the regular
    8:00 AM class rather than the tour's extra class 20 minutes ahead."""
    shots = TOURS / "v0.4"
    canvas = Image.new("RGBA", (2400, 1350), CREAM)
    draw = ImageDraw.Draw(canvas)
    draw.text((120, 250), "Satt Chitt Anand", font=serif(104), fill=MOSS)
    draw.text((124, 400), "TRUTH · CONSCIOUSNESS · BLISS", font=face(30, 700), fill=SAFFRON)
    text = ("A yoga studio app, made for the way one class already works: live on Google Meet every morning, "
            "talking on WhatsApp, in English, Hindi and Marathi.")
    for i, line in enumerate(wrap(text, face(40), 860)):
        draw.text((124, 490 + i * 60), line, font=face(40), fill=INK)
    draw.text((124, 1180), "Screens from v0.4, synthetic demo data", font=face(26), fill=MUTED)
    for name, x, y in (("hero_teacher", 1080, 170), ("hero_today", 1470, 90), ("08_ask_answer", 1860, 170)):
        item = phone(Image.open(shots / f"{name}.png"), 1080)
        canvas.alpha_composite(shadow(item.size).resize((item.width + 80, item.height + 80)), (x - 40, y - 40))
        canvas.alpha_composite(item, (x, y))
    canvas.convert("RGB").save(OUT / "figures" / "hero.png", optimize=True)


def before_after() -> None:
    """Two findings from the first tour, each as a before and after pair, side by side."""
    pairs = (
        ("Finding 'Log in'", TOURS / "v0.1" / "02_signup_login_hidden.png", TOURS / "v0.2" / "02_signup.png",
         "Below the whole form", "Side by side, on top"),
        ("A Hindi question", TOURS / "v0.1" / "10_ask_hindi_food_miss.png", TOURS / "v0.2" / "11_ask_hindi.png",
         "No notes found", "The right notes"),
    )
    phone_h, top = 900, 150
    canvas = Image.new("RGBA", (2400, top + phone_h + 140), CREAM)
    draw = ImageDraw.Draw(canvas)
    for p, (title, before, after, before_note, after_note) in enumerate(pairs):
        x0 = 80 + p * 1180
        draw.text((x0, 40), title, font=serif(52), fill=MOSS)
        for k, (path, tag, note, color) in enumerate(((before, "BEFORE · v0.1", before_note, MUTED), (after, "AFTER · v0.2", after_note, MOSS))):
            item = phone(Image.open(path), phone_h)
            x = x0 + k * 540
            place(canvas, item, (x, top))
            draw.text((x + item.width // 2, top + phone_h + 30), tag, font=face(24, 700), fill=color, anchor="ma")
            draw.text((x + item.width // 2, top + phone_h + 68), note, font=face(24), fill=INK, anchor="ma")
    canvas.convert("RGB").save(OUT / "figures" / "before_after.png", optimize=True)


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
    draw.text((16, 24), caption, font=face(28, 700), fill=MOSS)
    for k, (tile, file) in enumerate(zip(tiles, files, strict=True)):
        x, y = 16 + (k % cols) * (width + 16), 80 + (k // cols) * (tile_h + 44)
        canvas.paste(tile, (x, y))
        draw.text((x, y + tile.height + 6), file.stem.replace("_", " "), font=face(16), fill=MUTED)
    canvas.save(OUT / "iterations" / f"{version}.jpg", quality=82, optimize=True)


def main() -> None:
    if not TOURS.is_dir():
        raise SystemExit(f"{TOURS} is missing: run scripts/capture_tour.py first")
    for folder in ("figures", "gifs", "iterations"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    hero()
    before_after()
    strip("students", "For students", [
        ("Join, one tap first", "how do you feel?", ("join", STUDENT_TOUR, 22.0, 7.5)),
        ("Breathe", "a circle to follow", ("breathe", STUDENT_TOUR, 43.4, 10.2)),
        ("Ask", "answers from the notes", ("ask", STUDENT_TOUR, 57.4, 9.0)),
        ("In Hindi or Marathi", "the whole app", ("hindi", STUDENT_TOUR, 69.5, 9.5)),
    ])
    strip("teacher", "For the teacher", [
        ("Share the class link", "straight to WhatsApp", ("share", TEACHER_TOUR, 26.5, 9.5)),
        ("Approve students", "or let the group code do it", ("students", TOURS / "v0.4" / "15_students.png")),
        ("See how classes went", "demo data", ("insights", TOURS / "v0.4" / "16_insights_demo_data.png")),
    ])
    two_phones()
    for version, caption in (("v0.1", "v0.1, first tour: the findings are in docs/iterations/v0.1.md"),
                             ("v0.2", "v0.2: after the first round of fixes"),
                             ("v0.4", "v0.4: after the code review and the Marathi notes"),
                             ("v0.4-two-phones", "v0.4: two phones, one server (teacher and students, in order)")):
        sheet(version, caption)
    print(f"media in {OUT}")


if __name__ == "__main__":
    main()
