"""Portfolio figures from the tour screenshots: a hero image and before/after pairs, into docs/media/figures/.

Usage: python3 scripts/make_figures.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
OUT = MEDIA / "figures"
CREAM, MOSS, SAFFRON, INK, MUTED = "#F6F1E7", "#3F5B45", "#C26A2D", "#2B2A26", "#6E6A60"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


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


def hero(version: str) -> None:
    shots = MEDIA / version
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
    draw.text((124, 1180), f"Screens from {version}, synthetic demo data", font=ImageFont.truetype(SANS, 26), fill=MUTED)
    for name, x, y in (("12_teacher_classes", 1080, 170), ("03_today", 1470, 90), ("08_ask_answer", 1860, 170)):
        place(canvas, phone(shots / f"{name}.png", 1080), (x, y))
    canvas.convert("RGB").save(OUT / "hero.png", optimize=True)


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
    canvas.convert("RGB").save(OUT / f"{name}.png", optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hero("v0.2")
    before_after(
        "signup_v0.1_v0.2", MEDIA / "v0.1" / "02_signup_login_hidden.png", MEDIA / "v0.2" / "02_signup.png",
        "v0.1: a returning student had to scroll past the whole sign-up form to find 'Log in'.",
        "v0.2: 'Create account' and 'Log in' sit side by side above the form.",
    )
    before_after(
        "ask_hindi_v0.1_v0.2", MEDIA / "v0.1" / "10_ask_hindi_food_miss.png", MEDIA / "v0.2" / "11_ask_hindi.png",
        "v0.1: asked in Hindi, 'What should I eat before class?' uses an inflected verb the notes' keywords did "
        "not list, so the assistant found no notes and said it did not know.",
        "v0.2: inflected Hindi and Marathi forms added to the notes' keywords; a test now covers every suggested "
        "question in all three languages.",
    )
    print(f"figures in {OUT}")


if __name__ == "__main__":
    main()
