"""Phone screens: the v1 tour's real screenshots, by what they show (SHOTS), and the one card the film redraws.

`screen(name, clock)` gives a 540x1200 screen with its status-bar clock set to the moment for whoever holds the phone:
a real screenshot by its role in SHOTS, or "mock:<name>[:<argument>]". Everything is drawn at S times that size, in
screen units, so `callout()` can cut a card out sharp for an enlargement. `regions(name)` gives a screen's named
cards, each a box in screen units and, on a mock, the smallest text drawn in it, so highlights fit whole cards and
zooms can prove their text is large enough. A region is a box, or ("card", x, y): the card around that point, found
from its colour, so it fits the card exactly.

The demo data's class is seeded to be live whenever the tour runs, so the student's Next class card shows that hour.
The film's class is the Intermediate batch at 8:00 in India (1:30 PM for the student in Sydney), as the teacher's
batches say; that card is redrawn whole (mock_next), in the app's own type and colours, never patched.

Screens with developer text are refused: the debug build's welcome and sign-up show a "Server address" field.
"""

import functools
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import ndimage

from make_video import INK, LINE, MOSS, MOSS_LIGHT, MUTED, PAPER, SAFFRON, framed, wrap
from viz import folder, shot

WHITE = (255, 255, 255)
FONTS = Path(__file__).resolve().parents[2] / "tools" / "fonts"
ROBOTO = FONTS / "Roboto.ttf"  # Google Fonts, OFL; the app's sans
NOTO_SERIF = FONTS / "NotoSerif-Regular.ttf"  # OFL; Android's serif, the app's headings
FALLBACK, SERIF_FALLBACK = ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")
# How each item went, as the app's chips say it (the film's map icons use these colours too).
SCALE = (("Not yet", (188, 180, 166)), ("With effort", (214, 160, 84)), ("Steady", (104, 152, 166)), ("At ease", (46, 108, 126)))

V1 = "v1.0/"
SHOTS = {  # the final tour's screens (scripts/viz.py), by what they show
    "signup": V1 + "release_02_signup.png",
    "today": V1 + "03_today.png", "checkin": V1 + "04_checkin_before.png", "after": V1 + "05_after_class.png",
    "after_items": V1 + "05a_after_class_items.png", "practice": V1 + "07_practice.png", "history": V1 + "08_item_history.png",
    "solo_choose": V1 + "09_solo_choose.png", "solo_item": V1 + "10_solo_item.png", "history_solo": V1 + "12_history_solo.png",
    "ask": V1 + "13_ask.png", "ask_answer": V1 + "14_ask_asana.png", "me": V1 + "16_me.png", "me_shared": V1 + "16b_me_shared.png",
    "solo_running": V1 + "10a_solo_running.png", "practice_after": V1 + "12b_practice_after_solo.png",
    "waiting": V1 + "21_waiting.png", "intake": V1 + "22_intake.png", "intake_poses": V1 + "23_intake_poses.png",
    "thanks": V1 + "23b_intake_thanks.png",
    "batches": V1 + "26_teacher_batches.png",
    "students_waiting": V1 + "27_students_waiting.png", "placed_today": V1 + "27b_neha_today.png",
    "students_placed": V1 + "30b_rohan_moved.png",
    "move": V1 + "30_move_batch.png", "asha_items": V1 + "31_asha_items.png", "feedback_sent": V1 + "32_feedback_sent.png",
    "insights": V1 + "33_insights.png", "class_review": V1 + "34_class_review.png",
}
# The debug build's first screens show a "Server address" field: never these, only the release build's copies.
REFUSED = re.compile(r"(^|/)\d+[a-z]?_(welcome|signup)\.png$")
# Each screen's cards worth picking out, in screen units (540x1200): a box, or ("card", x, y) for the card around a
# point; or ("strips", box, box...): lines of a row, enlarged one under the other without the lines between them (an
# item's title and its strain count, not its trend). Boxes sit in the gaps between rows, so a highlight 8 px outside
# never crosses a line of text or a divider, and a box inside a card keeps 14 units in from its sides, so the card's
# outline stays out of the enlargement's margin.
REGIONS = {
    "signup": {"code": (24, 858, 516, 982), "create": ("card", 100, 1030)},
    "waiting": {"waiting": ("card", 36, 200), "tell": ("card", 60, 352)},
    "thanks": {"thanks": ("card", 24, 1000)},
    "students_waiting": {"intake": (44, 86, 496, 262), "place": (44, 335, 496, 708), "approve": ("card", 70, 675)},
    "placed_today": {"batch": ("card", 36, 400)},
    "batches": {"share": (42, 368, 498, 437), "share_button": (51, 377, 489, 428), "links": (46, 540, 494, 1034)},
    "after": {"mood": ("card", 36, 300), "item": ("card", 36, 560)},
    "after_items": {"strain": ("card", 36, 560)},
    "practice": {"item": ("strips", (50, 493, 372, 523), (50, 550, 372, 601))},  # its title, then strain and the teacher
    "history": {"wrote": ("card", 34, 470), "each": ("card", 34, 700)},
    "solo_choose": {"list": (20, 528, 520, 982)},
    "history_solo": {"solo": (44, 760, 502, 878)},
    "ask": {"about": ("card", 34, 160), "chip": (27, 543, 404, 584)},
    "ask_answer": {"answer": ("card", 34, 600)},
    "me": {"privacy": (44, 349, 496, 582)},
    "asha_items": {"item": ("strips", (50, 565, 372, 595), (50, 623, 372, 651))},
    "feedback_sent": {"wrote": ("card", 34, 500)},
    "insights": {"class": ("card", 34, 560), "link": (46, 574, 246, 610)},
    "class_review": {"strain": ("card", 34, 450)},
    "move": {"picker": (50, 300, 490, 632), "move_button": ("card", 70, 598)},
    "students_placed": {"since": (44, 95, 496, 182)},
}


def intake_regions(top: float) -> dict:
    """The intake's regions, from where its chosen food chip (the screen's largest moss shape) starts: a line more or
    less in the text above it moves them all. The line about where the answers go sits under the fixed title."""
    return {"consent": (24, 163, 516, top - 226), "body": (24, top - 222, 516, top - 125),
            "food": (24, top - 118, 516, top + 152), "pain": (24, top + 158, 516, top + 421),
            "foodpain": (24, top - 118, 516, top + 421)}
S = 3  # screens are drawn at three times 540x1200, so a card enlarged beside the phone stays sharp
SCREEN = (540, 1200)
BAR = 54  # the status bar's height, in screen units
DP = 540 / 411.43  # screen units per dp (and per sp): a 1080-pixel-wide phone at 420 dpi


def up(v):
    """Screen units to pixels of an S-times image: a box or a list of points."""
    if v and isinstance(v[0], (tuple, list)):
        return [(x * S, y * S) for x, y in v]
    return [c * S for c in v]


@functools.lru_cache(maxsize=48)
def roboto(size: int, weight: int = 400) -> ImageFont.FreeTypeFont:
    if not ROBOTO.exists():
        return ImageFont.truetype(FALLBACK, size)
    face = ImageFont.truetype(str(ROBOTO), size)
    face.set_variation_by_axes([weight, 100])
    return face


@functools.lru_cache(maxsize=16)
def serif(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(NOTO_SERIF) if NOTO_SERIF.exists() else SERIF_FALLBACK, size)


class Pen:
    """ImageDraw in screen units (540x1200), on an image S times that size."""

    def __init__(self, image: Image.Image):
        self.image, self.d = image, ImageDraw.Draw(image)

    def rectangle(self, box, fill=None, outline=None, width=1):
        self.d.rectangle(up(box), fill=fill, outline=outline, width=round(width * S))

    def rounded_rectangle(self, box, radius, fill=None, outline=None, width=1):
        self.d.rounded_rectangle(up(box), radius * S, fill=fill, outline=outline, width=round(width * S))

    def ellipse(self, box, fill=None, outline=None, width=1):
        self.d.ellipse(up(box), fill=fill, outline=outline, width=round(width * S))

    def line(self, points, fill=None, width=1, joint=None):
        self.d.line(up(points), fill=fill, width=round(width * S), joint=joint)

    def polygon(self, points, fill=None, outline=None):
        self.d.polygon(up(points), fill=fill, outline=outline)

    def text(self, xy, s, size, weight=400, fill=INK, serif_=False, anchor="la", spacing=0.0):
        face = serif(round(size * S)) if serif_ else roboto(round(size * S), weight)
        if not spacing:
            self.d.text(up(xy), s, font=face, fill=fill, anchor=anchor)
            return
        x, y = up(xy)  # letter-spaced, left-anchored: one character at a time
        for ch in s:
            self.d.text((x, y), ch, font=face, fill=fill, anchor=anchor)
            x += face.getlength(ch) + spacing * S


class Mock:
    """A screen with a card redrawn whole over a real screenshot, so everything around it is the app's own."""

    def __init__(self, base: str):
        self.base = base
        self.image = real(base).copy()
        self.draw = Pen(self.image)
        self.regions: dict = {}

    def region(self, name: str, box: tuple, smallest: int) -> None:
        """A card worth highlighting, and the smallest text in it."""
        self.regions[name] = (box, smallest)

    def para(self, x, y, s, size, width, color, leading):
        face, words = roboto(round(size * S)), s.split()
        for row in wrap(words, face, width * S):
            self.draw.text((x, y), " ".join(words[i] for i in row), size, 400, color)
            y += size * leading
        return y


# The film's Next class: the Intermediate batch, Thursday at 8:00 in India, 55 minutes, live from 1:30 PM in Sydney.
NEXT = {"batch": "Intermediate", "when": "Today · 1:30 PM · 55 min"}


def moss_card(name: str) -> tuple:
    """The largest moss shape on a real screen (a Next class card, a chosen chip): its box, in screen units."""
    pixels = np.asarray(Image.open(source(name)).convert("RGB").resize(SCREEN, Image.LANCZOS), dtype=np.int16)
    mask = np.abs(pixels - np.array(MOSS)).sum(axis=2) < 24
    labels, _ = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    ys, xs = np.nonzero(labels == sizes.argmax())
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def mock_next(name: str = "today") -> Mock:
    """The student's Next class card, redrawn whole at the film's class time over screen `name` ("today", or
    "checkin" with the mood check-in open inside it). The card keeps its place, size and parts: the label and Live now
    pill, the batch name, the time, the batch's line, then the Join button or the check-in, which is the screenshot's
    own (faces and words, no time in it). Offsets from the card's top were measured on the screenshot's own card."""
    m = Mock(name)
    x0, y0, x1, y1 = moss_card(name)
    edge = 1.3  # the card's 1 dp outline, outside its fill
    inner = paper_card(name, (x0, y0, x1, y1)) if name == "checkin" else None
    if inner:  # with its 1 dp outline
        inner = (inner[0] - 2, inner[1] - 2, inner[2] + 2, inner[3] + 2)
    piece = real(name).crop(tuple(round(v * S) for v in inner)) if inner else None
    m.draw.rectangle([x0 - 6, y0 - 6, x1 + 6, y1 + 6], fill=m.image.getpixel((round((x0 - 10) * S), round((y0 + 40) * S))))
    m.draw.rounded_rectangle([x0 - edge, y0 - edge, x1 + edge, y1 + edge], 16 * DP, fill=MOSS, outline=LINE, width=edge)
    left, right = x0 + 21, x1 - 21
    m.draw.text((left, y0 + 36.5), "NEXT CLASS", 13 * DP, 500, MOSS_LIGHT, anchor="lm", spacing=0.4 * DP)
    words = roboto(round(13 * DP * S), 500).getlength("Live now") / S
    m.draw.rounded_rectangle([right - words - 32, y0 + 21, right, y0 + 52], 15.5, fill=SAFFRON)
    m.draw.text((right - (words + 32) / 2, y0 + 36.5), "Live now", 13 * DP, 500, WHITE, anchor="mm")
    m.draw.text((left, y0 + 83.4), NEXT["batch"], 26 * DP, serif_=True, fill=WHITE, anchor="lm")
    m.draw.text((left, y0 + 130.4), NEXT["when"], 17 * DP, 400, MOSS_LIGHT, anchor="lm")
    about = "For a steady practice: sun salutations, standing poses, twists and backbends, longer holds."
    m.para(left, y0 + 157, about, round(15 * DP), right - left, MOSS_LIGHT, leading=29 / round(15 * DP))
    if piece is None:
        top = y0 + 222.5
        m.draw.rounded_rectangle([left, top, right, top + 73.5], 36.75, fill=SAFFRON)
        label = "Join class"
        w = roboto(round(16 * DP * S), 600).getlength(label) / S
        cx, cy = (left + right) / 2 + 16 * DP, top + 36.75
        m.draw.text((cx, cy), label, 16 * DP, 600, WHITE, anchor="mm")
        camera(m.draw, cx - w / 2 - 8 * DP - 12 * DP, cy)
        m.region("join", (left, top, right, top + 73.5), 0)
    else:
        m.image.paste(piece, (round(inner[0] * S), round(inner[1] * S)))
        m.region("mood", inner, 0)
        cx, cy = inner[0] + 2 + 60 + 3 * 80, inner[1] + 2 + 98  # the fourth face, 🙂: five 56 dp faces across the card
        m.region("face", (cx - 37, cy - 37, cx + 37, cy + 37), 0)
    m.region("next", (x0, y0, x1, y1), 0)
    return m


def paper_card(name: str, around: tuple) -> tuple:
    """The light card inside the moss card (the check-in's), in screen units."""
    pixels = np.asarray(screen(name), dtype=np.int16)
    x0, y0, x1, y1 = around
    patch = pixels[y0:y1, x0:x1]
    mask = np.abs(patch - np.array(PAPER)).sum(axis=2) < 18
    labels, _ = ndimage.label(mask)
    sizes = np.bincount(labels.ravel())
    sizes[0] = 0
    ys, xs = np.nonzero(labels == sizes.argmax())
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1


def camera(draw: Pen, x: float, y: float) -> None:
    """Material's Videocam icon, 24 dp, centred on (x, y)."""
    s = DP
    draw.rounded_rectangle([x - 9 * s, y - 6 * s, x + 4 * s, y + 6 * s], 1.5 * s, fill=WHITE)
    draw.polygon([(x + 4 * s, y - 2 * s), (x + 9 * s, y - 6 * s), (x + 9 * s, y + 6 * s), (x + 4 * s, y + 2 * s)], fill=WHITE)


def chat(t: float) -> Image.Image:
    """The class's group chat as it is without the app: the morning's link first, then messages arriving at the
    bottom, the newest always there, until the link has gone off the top. Large enough to read beside the room."""
    base = "v0.6-ondevice/20_today_en.png"
    image = Image.open(shot(base)).convert("RGB")
    image = image.resize((image.width * S, image.height * S), Image.LANCZOS)
    draw = Pen(image)
    draw.rectangle([0, 0, 540, 1200], fill=image.getpixel((6 * S, 100 * S)))
    messages = (("Teacher", "Today's class: meet.google.com/xyz-abcd-efg", True), ("Meera", "Good morning, everyone!", False),
                ("Rohan", "Running late today", False), ("Asha", "Namaste, all", False), ("Kavita", "Is it Hatha today?", False),
                ("Sunil", "Thank you ji", False), ("Meera", "Can someone send the link again?", False),
                ("Rohan", "Link please?", False))
    shown = messages[: min(len(messages), 3 + int(t * 2.2))]
    face = roboto(32 * S, 450)
    y = 1180
    for who, text, link in reversed(shown):  # every word at least 30 units, 20 px on the film's phone
        words = text.split()
        rows = [" ".join(words[i] for i in row) for row in wrap(words, face, 430 * S)]
        height = 74 + 44 * len(rows)
        y -= height
        if y + height > 156:
            draw.rounded_rectangle([18, y, 500, y + height - 14], 20, fill=(214, 236, 214) if link else PAPER, outline=LINE)
            draw.text((36, y + 10), who, 30, 700, MOSS if link else MUTED)
            for k, row in enumerate(rows):
                draw.text((36, y + 50 + k * 44), row, 32, 450)
    draw.rectangle([0, 0, 540, 156], fill=(228, 222, 210))
    draw.ellipse([22, 74, 78, 130], fill=(190, 182, 168))
    draw.text((94, 66), "Class group", 32, 700)
    draw.text((94, 108), "Teacher, Meera, Rohan…", 30, 400, MUTED)
    return image.resize(SCREEN, Image.LANCZOS)


MOCKS = {"next": mock_next}


@functools.lru_cache(maxsize=8)
def real(name: str) -> Image.Image:
    """A tour screenshot by its role in SHOTS, at S times 540x1200. Refuses the debug build's welcome and sign-up."""
    path = SHOTS[name]
    if REFUSED.search(path):
        raise ValueError(f"{path} is the debug build's, with its Server address field; use the release build's copy")
    if not source(name).exists():  # still to be shot: a blank screen naming it, which the layout check fails
        image = Image.new("RGB", (SCREEN[0] * S, SCREEN[1] * S), (246, 241, 231))
        Pen(image).text((270, 600), f"to come: {Path(path).stem}", 22, 600, MUTED, anchor="mm")
        return image
    image = Image.open(source(name)).convert("RGB").resize((SCREEN[0] * S, SCREEN[1] * S), Image.LANCZOS)
    for box in softened(name):  # what must never be legible: the class's group code, typed in
        x0, y0, x1, y1 = (round(v * S) for v in box)
        m = 10 * S  # blurred on the field's own fill and blended in through a feathered edge, so it has no outline
        patch = Image.new("RGB", (x1 - x0 + 2 * m, y1 - y0 + 2 * m), image.getpixel((x0, y0)))
        patch.paste(image.crop((x0, y0, x1, y1)), (m, m))
        for _ in range(3):
            patch = patch.filter(ImageFilter.GaussianBlur(6 * S))
        mask = Image.new("L", patch.size, 0)
        ImageDraw.Draw(mask).rectangle([m, m, m + x1 - x0, m + y1 - y0], fill=255)
        image.paste(patch, (x0 - m, y0 - m), mask.filter(ImageFilter.GaussianBlur(3 * S)))
    return image


SOFTENED = {"signup": "Group code"}  # a field whose typed value is blurred, by its label


def softened(name: str) -> list:
    """Where a screen's secret values are, in screen units: the value line of the field labelled SOFTENED[name], from
    the UI dump (between its label and the hint under it), or where the sign-up's code field sits if there is no
    dump."""
    label = SOFTENED.get(name)
    if not label:
        return []
    path = source(name).with_suffix(".xml")
    if not path.exists():
        return [(40, 888, 330, 940)]
    nodes = [(n, [int(v) / 2 for v in re.findall(r"\d+", n.get("bounds", ""))]) for n in ET.parse(path).getroot().iter("node")]
    found = []
    for node, box in nodes:
        if "EditText" in node.get("class", "") and any((n.get("text") or "").startswith(label) and b[1] == box[1]
                                                       for n, b in nodes):
            found.append((box[0] + 8, box[1] + 24, box[0] + (box[2] - box[0]) * 0.65, box[3] - 34))
    return found or [(40, 888, 330, 940)]


def missing(name: str) -> bool:
    """Whether a real screen is still to be shot."""
    return not name.startswith("mock:") and not source(name).exists()


def source(name: str) -> Path:
    """Where screen `name` is: a version's tour (scripts/viz.py), or a pull request's shots beside v1's."""
    path = SHOTS[name]
    return shot(path) if path.startswith("v") else folder("v1") / "screens" / path


@functools.lru_cache(maxsize=8)
def drawn(name: str) -> tuple:
    """A screen without its clock, at S times: (image, its regions)."""
    if name.startswith("mock:"):
        kind, *argument = name[5:].split(":")
        mock = MOCKS[kind](*argument)
        return mock.image, mock.regions
    return real(name).copy(), {}


@functools.lru_cache(maxsize=96)
def regions(name: str) -> dict:
    """The screen's named regions: (box, the smallest text in it, or 0 on a real screen)."""
    found = dict(drawn(name)[1])
    if name == "intake":
        found.update({key: (box, 0) for key, box in intake_regions(moss_card(name)[1]).items()})
    for key, spec in REGIONS.get(name, {}).items():
        if spec[0] == "strips":  # picked out on the phone as one box round them all
            boxes = spec[1:]
            spec = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        found[key] = (card_at(name, *spec[1:]) if spec[0] == "card" else spec, 0)
    return found


def strips(name: str, region: str) -> tuple:
    """A region's lines to enlarge one under the other, if it is ("strips", ...)."""
    spec = REGIONS.get(name, {}).get(region, ("",))
    return spec[1:] if spec[0] == "strips" else ()


@functools.lru_cache(maxsize=64)
def card_at(name: str, x: int, y: int) -> tuple:
    """The card around screen point (x, y): the box of the area of that pixel's colour joined to it, in screen units."""
    pixels = np.asarray(screen(name), dtype=np.int16)
    seed = pixels[y, x]
    labels, _ = ndimage.label(np.abs(pixels - seed).sum(axis=2) <= 6)
    ys, xs = np.nonzero(labels == labels[y, x])
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


@functools.lru_cache(maxsize=24)
def callout(name: str, box: tuple, size: tuple) -> Image.Image:
    """The screen's `box` (screen units) at `size` pixels, cut from the S-times drawing so it stays sharp."""
    return drawn(name)[0].crop(tuple(round(v * S) for v in box)).resize(size, Image.LANCZOS)


def status_bar(image: Image.Image, clock: str) -> Image.Image:
    """The status bar redrawn whole, as demo mode shows it: `clock`, the moment for whoever holds the phone, at the
    left; full Wi-Fi and battery at the right; on the bar's own colour."""
    draw = ImageDraw.Draw(image)
    bar = image.getpixel((8, 4))
    draw.rectangle([0, 0, 540, BAR], fill=bar)
    ink = (60, 60, 58)
    draw.text((28, 32), clock, font=roboto(17, 500), fill=ink, anchor="lm")
    draw.pieslice([462, 22, 490, 50], 225, 315, fill=ink)  # Wi-Fi: a quarter fan, point down
    draw.rounded_rectangle([494, 24, 503, 41], 2, fill=ink)  # the battery, full
    draw.rectangle([497, 22, 500, 24], fill=ink)
    return image


@functools.lru_cache(maxsize=96)
def screen(name: str, clock: str = "") -> Image.Image:
    """The screen at 540x1200, with its status bar showing `clock`."""
    image = drawn(name)[0].resize(SCREEN, Image.LANCZOS)
    return status_bar(image, clock) if clock else image


@functools.lru_cache(maxsize=48)
def phone(name: str, height: int, clock: str = "") -> Image.Image:
    """The screen in a phone frame, `height` pixels tall."""
    return framed(screen(name, clock), height)


@functools.lru_cache(maxsize=48)
def ink(name: str) -> np.ndarray:
    """Where a screen has words, icons, faces or chips: pixels far from the background around them (a 15-unit median),
    in shapes the size of a word or a chip, so card fills, outlines, dividers and the rims of dark cards, bars and
    long buttons don't count, while their words do."""
    a = np.asarray(screen(name), dtype=np.int16)
    mask = np.abs(a - ndimage.median_filter(a, size=(15, 15, 1))).sum(axis=2) > 160
    labels, _ = ndimage.label(mask)
    for k, (rows, cols) in enumerate(ndimage.find_objects(labels), start=1):
        h, w = rows.stop - rows.start, cols.stop - cols.start
        if w > 160 or (h > 60 and w > 60):
            mask[labels == k] = False
    return mask


@functools.lru_cache(maxsize=48)
def marks(name: str) -> np.ndarray:
    """Anything drawn on a screen, the faint outlines of cards, fields and chips too: pixels off the background around
    them."""
    a = np.asarray(screen(name), dtype=np.int16)
    return np.abs(a - ndimage.median_filter(a, size=(15, 15, 1))).sum(axis=2) > 20


MOCK_CARDS = ("next",)  # a mock's regions that are its redrawn card, whole


def is_card(name: str, region: str) -> bool:
    """Whether a region is a whole card: found from its colour, or a mock's redrawn card."""
    return REGIONS.get(name, {}).get(region, ("",))[0] == "card" or (name.startswith("mock:") and region in MOCK_CARDS)


@functools.lru_cache(maxsize=96)
def content(name: str, region: str) -> tuple:
    """The box of what a region holds, in screen units. A card found from its colour is itself the content, its 1 dp
    outline included; in a box, everything off the box's own background colour (the most common one in it), so cards
    and chips inside it count whole, edges and all."""
    x0, y0, x1, y1 = (round(v) for v in regions(name)[region][0])
    if is_card(name, region):
        return x0 - 2, y0 - 2, x1 + 2, y1 + 2
    patch = np.asarray(screen(name), dtype=np.int16)[y0:y1, x0:x1]
    colours, counts = np.unique(patch.reshape(-1, 3) // 4, axis=0, return_counts=True)
    ys, xs = np.nonzero(np.abs(patch // 4 - colours[counts.argmax()]).sum(axis=2) * 4 > 20)
    if not len(xs):
        return x0, y0, x1, y1
    return x0 + int(xs.min()), y0 + int(ys.min()), x0 + int(xs.max()) + 1, y0 + int(ys.max()) + 1


def corner(name: str, region: str) -> float:
    """A whole card's corner radius, in screen units: a redrawn card's own (16 dp, and its outline), or, on a real
    screen, from where its fill starts along its row k units down: there the arc is r - sqrt(2rk - k^2) in."""
    if name.startswith("mock:"):
        return 16 * DP + 1.3
    a = np.asarray(screen(name), dtype=np.int16)
    x0, y0, x1, _ = (round(v) for v in regions(name)[region][0])
    k = 2
    fill = a[y0 + k + 1, (x0 + x1) // 2]
    row = np.abs(a[y0 + k, x0:x1] - fill).sum(axis=1) <= 12
    x = float(np.argmax(row)) if row.any() else 4.0
    return x + k + math.sqrt(2 * x * k)


def ring_box(name: str, region: str, pad: float) -> tuple:
    """Where a highlight's stroke goes: `pad` units outside the region's content all round."""
    x0, y0, x1, y1 = content(name, region)
    return x0 - pad, y0 - pad, x1 + pad, y1 + pad


@functools.lru_cache(maxsize=96)
def ring_clearance(name: str, region: str, pad: float, clear: float, inner: float) -> list:
    """What keeps a highlight from having a ring `pad` units out from the region's content, with `clear` units clear
    outside it and words at least `inner` units inside it: anything drawn between the content and that clear space
    (another card, a chip, a pill, a field), words too near the stroke, an element of the screen's UI dump there, or
    the stroke landing inside a card (on a fill that is not the page's) rather than around one."""
    found = []
    x0, y0, x1, y1 = content(name, region)
    rx0, ry0, rx1, ry1 = ring_box(name, region, pad)
    c = clear
    zone = (max(0, round(rx0 - c)), max(0, round(ry0 - c)), min(SCREEN[0], round(rx1 + c)), min(SCREEN[1], round(ry1 + c)))
    around = marks(name)[zone[1]:zone[3], zone[0]:zone[2]].copy()
    around[max(0, y0 - zone[1]):y1 - zone[1], max(0, x0 - zone[0]):x1 - zone[0]] = False
    if around.any():
        found.append("something drawn within the ring's clear space")
    words = ink(name)[round(ry0):round(ry1), round(rx0):round(rx1)].copy()
    i = round(inner)
    words[i:-i, i:-i] = False
    if words.any():
        found.append(f"words inside it within {inner:.0f} units of the stroke")
    for box, what in elements(name):
        inside = box[0] >= x0 - 1 and box[1] >= y0 - 1 and box[2] <= x1 + 1 and box[3] <= y1 + 1
        holds = box[0] <= rx0 and box[1] <= ry0 and box[2] >= rx1 and box[3] >= ry1
        if holds:
            found.append(f"the ring sits inside '{what}'")
        elif not inside and near(box, (rx0, ry0, rx1, ry1), c):
            found.append(f"the ring within {clear:.0f} units of '{what}'")
    a = np.asarray(screen(name), dtype=np.int16)
    under = np.concatenate([a[max(0, round(ry0)):round(ry1), max(0, round(rx0))].reshape(-1, 3),
                            a[max(0, round(ry0)), max(0, round(rx0)):round(rx1)].reshape(-1, 3)])
    if np.abs(np.median(under, axis=0) - page(name)).sum() > 12:
        found.append("the ring lands inside a card")
    return found


def near(a: tuple, b: tuple, gap: float) -> bool:
    """Whether box a comes within `gap` of box b (overlapping included)."""
    return a[0] < b[2] + gap and b[0] < a[2] + gap and a[1] < b[3] + gap and b[1] < a[3] + gap


@functools.lru_cache(maxsize=48)
def page(name: str) -> np.ndarray:
    """A screen's page colour, that cards sit on: down its left margin, outside the cards."""
    return np.median(np.asarray(screen(name), dtype=np.int16)[BAR + 20:1080, 4:10].reshape(-1, 3), axis=0)


def dump(name: str) -> Path:
    """Where a real screen's UI dump is, beside it; a mock ("mock:next:today") uses its base screen's."""
    parts = name.split(":")
    base = (parts[2] if len(parts) > 2 else "today") if name.startswith("mock:") else name
    return source(base).with_suffix(".xml")


@functools.lru_cache(maxsize=64)
def elements(name: str) -> tuple:
    """The screen's elements from its UI dump, if it has one: (box in screen units, what it says or is). Only what
    can be seen as a thing: words, a description, something tappable or a field; not the screen-sized containers,
    and not the system's bars, which the film draws itself."""
    path = dump(name)
    if not path.exists():
        return ()
    root = ET.parse(path).getroot()
    scale = SCREEN[0] / 1080
    found = []
    for node in root.iter("node"):
        numbers = [int(v) for v in re.findall(r"-?\d+", node.get("bounds", ""))]
        if len(numbers) != 4 or node.get("package", "").startswith("com.android.systemui"):
            continue
        box = tuple(v * scale for v in numbers)
        w, h = box[2] - box[0], box[3] - box[1]
        if w <= 1 or h <= 1 or w * h > 0.4 * SCREEN[0] * SCREEN[1] or node.get("scrollable") == "true" or box[3] <= BAR:
            continue
        what = node.get("text") or node.get("content-desc") or ""
        if what or node.get("clickable") == "true" or node.get("checkable") == "true" or "EditText" in node.get("class", ""):
            found.append((box, what or node.get("class", "").split(".")[-1]))
    return tuple(found)


@functools.lru_cache(maxsize=96)
def cuts(name: str, crop: tuple) -> list:
    """The elements a zoom's crop slices: one it neither holds whole nor sits inside, where the crop's edge crosses
    something drawn of it (a row's empty padding may be cut; its words, its chip or its outline may not)."""
    found = []
    drawn_ = marks(name)
    x0, y0, x1, y1 = crop
    for box, what in elements(name):
        held = box[0] >= x0 - 1 and box[1] >= y0 - 1 and box[2] <= x1 + 1 and box[3] <= y1 + 1
        holds = box[0] <= x0 + 1 and box[1] <= y0 + 1 and box[2] >= x1 - 1 and box[3] >= y1 - 1
        if held or holds or not near(box, crop, 0):
            continue
        bx0, by0, bx1, by1 = (max(0, round(v)) for v in (max(box[0], x0), max(box[1], y0), min(box[2], x1), min(box[3], y1)))
        edges = []
        for v, lo, hi in ((x0, box[0], box[2]), (x1, box[0], box[2])):
            if lo < v < hi:
                edges.append(drawn_[by0:by1, min(round(v), SCREEN[0] - 1)])
        for v, lo, hi in ((y0, box[1], box[3]), (y1, box[1], box[3])):
            if lo < v < hi:
                edges.append(drawn_[min(round(v), SCREEN[1] - 1), bx0:bx1])
        if any(e.any() for e in edges):
            found.append(what)
    return found
