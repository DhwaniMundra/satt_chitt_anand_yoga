"""What sits over the pictures: the title's masthead, the caption bar with the chapters, a principle's few words, and
the muted look of the "before". Everything drawn here registers with film.layout."""

import functools

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

import make_video as mv
from make_video import tint
from . import layout

CREAM, PAPER, INK, MUTED, FAINT, LINE = mv.CREAM, mv.PAPER, mv.INK, mv.MUTED, mv.FAINT, mv.LINE
MOSS, SAFFRON, W, H = mv.MOSS, mv.SAFFRON, mv.W, mv.H
SAGE, SAGE_FILL = (96, 126, 100), (232, 238, 228)
QUIET = (138, 131, 119)  # the chapters not playing: 3.7:1 on the bar
# The caption bar, 170 px: the progress line on top; the caption centred in its band; then, at least 28 px below the
# caption's lowest glyph, the chapters, lighter, with their own margin under them.
VIEW_H = 910  # the picture above the bar
CAPTION_Y = 954  # the caption band's middle (the band runs from the progress line to about 994)
CHAPTER_Y = 1018
DEVANAGARI = "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"  # shaped by raqm: matras, conjuncts


@functools.lru_cache(maxsize=4)
def devanagari(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(DEVANAGARI, size, layout_engine=ImageFont.Layout.RAQM)


def masthead(draw: ImageDraw.ImageDraw, name: float, motto: float, plain: float) -> None:
    """The name in Devanagari and in English, "Yoga Studio", the motto, and what the app is."""
    for words, face, color, y, amount in (
        ("सत्·चित्·आनन्द", devanagari(46), SAFFRON, 196, name),  # the studio's own spelling, with the half-न
        ("Satt Chitt Anand", mv.font(120, serif=True), MOSS, 304, name),
        ("Yoga Studio", mv.font(48, serif=True), MOSS, 406, name),
        ("TRUTH  ·  CONSCIOUSNESS  ·  BLISS", mv.font(28, 700), SAFFRON, 490, motto),
        ("A practice tracker for a small online yoga class", mv.font(40, 500), INK, 612, plain),
    ):
        if amount > 0:
            layout.text(draw, (W // 2, y), words, face, tint(color, amount), "mm", name=words[:20])


def mute(image: Image.Image, amount: float) -> Image.Image:
    """The "before" look: colour drained and contrast softened by `amount` (0 to 1)."""
    if amount <= 0:
        return image
    image = ImageEnhance.Color(image).enhance(1 - 0.85 * amount)
    return ImageEnhance.Contrast(image).enhance(1 - 0.18 * amount)


def pill(draw: ImageDraw.ImageDraw, x: float, y: float, words: str, size: int, color: tuple, fill: tuple, edge: tuple | None,
         name: str, amount: float = 1.0, anchor: str = "lt", weight: int = 600) -> tuple:
    """Words on a rounded backing; (x, y) is the pill's left top, or its centre with anchor "mm". Returns its box."""
    face = mv.font(size, weight)
    width, height = face.getlength(words) + 2 * round(size * 0.7), round(size * 1.75)
    if anchor == "mm":
        x, y = x - width / 2, y - height / 2
    box = (x, y, x + width, y + height)
    draw.rounded_rectangle(box, height // 2, fill=tint(fill, amount), outline=tint(edge, amount) if edge else None, width=2)
    layout.add(name, "label", box)
    layout.text(draw, (x + width / 2, y + height / 2), words, face, tint(color, amount), "mm", name=name + " text", owner=name,
                container=box)
    return box


def chip(canvas: Image.Image, text: str, amount: float, x: float, y: float) -> None:
    """A principle's few words, quiet (sage on a pale fill, no outline), placed by the beat near what shows it."""
    if amount > 0:
        pill(ImageDraw.Draw(canvas), x, y, text, 24, SAGE, SAGE_FILL, None, "principle", amount, weight=600)


def caption_rows(names: list, face, width: int = 1500) -> list:
    """The caption's rows, as lists of word indexes: one row if it fits; two rows broken where both fit, after
    punctuation if any such break exists, as even as possible; longer lines wrapped plainly."""
    if face.getlength(" ".join(names)) <= width:
        return [list(range(len(names)))]
    fits = []
    for i in range(1, len(names)):
        a, b = face.getlength(" ".join(names[:i])), face.getlength(" ".join(names[i:]))
        if a <= width and b <= width:
            fits.append((names[i - 1][-1] not in ',.:;?!"\u201d', abs(a - b), i))
    if not fits:
        return mv.wrap(names, face, width)
    i = min(fits)[2]
    return [list(range(i)), list(range(i, len(names)))]


def caption_bar(canvas: Image.Image, words: list, chapters: tuple, chapter: str, progress: float, amount: float = 1.0) -> None:
    """The words being spoken, (word, said) pairs, darkening as they are said and faded in by `amount`, above the
    chapters and the progress."""
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, VIEW_H, W, H], fill=PAPER)
    draw.rectangle([0, VIEW_H, W, VIEW_H + 4], fill=LINE)
    draw.rectangle([0, VIEW_H, round(W * progress), VIEW_H + 4], fill=MOSS)
    layout.add("bar", "bar", (0, VIEW_H, W, H))
    slot = (W - 2 * 120) / len(chapters)
    for i, name in enumerate(chapters):
        on = name == chapter
        layout.text(draw, (120 + slot * (i + 0.5), CHAPTER_Y), name, mv.font(22, 600 if on else 400), MOSS if on else QUIET, "mm",
                    name=f"chapter {name}", owner="bar")
    if not words or amount <= 0:
        return
    face = mv.font(38, 600)
    space = face.getlength(" ")
    names = [w for w, _ in words]
    rows = caption_rows(names, face)
    row = max((r for r in rows if words[r[0]][1]), key=rows.index, default=rows[0])
    shown = [words[i] for i in row]
    x = W / 2 - (sum(face.getlength(w) for w, _ in shown) + space * (len(shown) - 1)) / 2
    for k, (word, said) in enumerate(shown):
        layout.text(draw, (x, CAPTION_Y), word, face, tint(INK if said else FAINT, amount, PAPER), "lm", name=f"caption {k}",
                    owner="bar")
        x += face.getlength(word) + space
