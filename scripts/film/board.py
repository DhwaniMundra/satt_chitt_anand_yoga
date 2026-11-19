"""The studio's four batches as a board: a card per batch with its days, its time in India, its Meet link, its sequence
(three small figures in its poses) and its students, each a small bust in their colour. A new student can drop into a
batch, and a student can move from one batch to another with the teacher's note. Times match the batches in the
Sheet (content/studio.json): 7:00, 8:00 and 9:00 AM, Monday to Saturday; Pain management at 5:30 PM, Monday,
Wednesday and Friday. Everything registers with film.layout."""

import math

from PIL import Image, ImageDraw

import make_video as mv
from make_video import ease
from . import figures, layout
from .chrome import CREAM, INK, LINE, MOSS, MUTED, PAPER, SAFFRON, pill, tint

# (name, days, time, three poses from its curriculum, content/curriculum.json)
BATCHES = (("Beginner", "Mon to Sat", "7:00 AM IST", ("tadasana", "vrikshasana", "vajrasana")),
           ("Intermediate", "Mon to Sat", "8:00 AM IST", ("trikonasana", "virabhadrasana", "utkatasana")),
           ("Advanced", "Mon to Sat", "9:00 AM IST", ("padmasana", "sarvangasana", "halasana")),
           ("Pain management", "Mon, Wed, Fri", "5:30 PM IST", ("sectional", "pavanamuktasana", "setu")))
ROWS = ("days", "time", "link", "sequence")
SINCE = "since Today"  # under a moved student, as their card on the teacher's Students says
AREA = (72, 130, 1848, 800)  # the cards' row, inside the picture above the caption bar
GAP = 28
CARD_W = (AREA[2] - AREA[0] - 3 * GAP) / 4
# Who is in which batch at the start, as in the demo data, by colour: the Intermediate students are the ones on the
# map (Sydney, Dubai, California); the others are only seen here. "rohan" moves from Beginner to Intermediate after a review; "neha"
# joins Pain management.
NEUTRAL = {"rohan": (70, 128, 140), "advanced": (150, 110, 140), "pain": (176, 112, 108)}
MEMBERS = {"Beginner": ("rohan",), "Intermediate": ("sydney", "dubai", "california"), "Advanced": ("advanced",),
           "Pain management": ("pain",)}
FIGURE = figures.Person("board", (110, 118, 104), (190, 150, 118), hair=(60, 50, 44))
BUST = 44  # a bust's width
SLOT = 76  # from one bust to the next: room for the review's ring round one, 8 px clear of the next


def card_box(k: int) -> tuple:
    x0 = AREA[0] + k * (CARD_W + GAP)
    return x0, AREA[1], x0 + CARD_W, AREA[3]


def member_point(batch: str, k: int) -> tuple:
    """Where the k-th student of `batch` sits: on the card's bottom row, left to right."""
    x0, y0, _, _ = card_box([b[0] for b in BATCHES].index(batch))
    return x0 + 34 + BUST / 2 + k * SLOT, y0 + 520


def bust(draw: ImageDraw.ImageDraw, x: float, y: float, color: tuple, name: str, amount: float = 1.0) -> tuple:
    """A student as a small bust centred on (x, y): a head over rounded shoulders, in their colour."""
    head, shoulders = tint((196, 156, 120), amount, PAPER), tint(color, amount, PAPER)
    draw.pieslice([x - 22, y - 2, x + 22, y + 42], 180, 360, fill=shoulders)
    draw.ellipse([x - 12, y - 30, x + 12, y - 6], fill=head)
    box = (x - 22, y - 30, x + 22, y + 20)
    layout.add(name, "icon", box)
    return box


def icon(draw: ImageDraw.ImageDraw, kind: str, x: float, y: float, color: tuple) -> None:
    """A row's small icon centred on (x, y): a calendar, a clock, a camera."""
    if kind == "days":
        draw.rounded_rectangle([x - 12, y - 10, x + 12, y + 12], 4, outline=color, width=3)
        draw.line([(x - 12, y - 3), (x + 12, y - 3)], fill=color, width=3)
        for dx in (-6, 6):
            draw.line([(x + dx, y - 15), (x + dx, y - 8)], fill=color, width=3)
    elif kind == "time":
        draw.ellipse([x - 12, y - 12, x + 12, y + 12], outline=color, width=3)
        draw.line([(x, y - 7), (x, y), (x + 6, y + 4)], fill=color, width=3, joint="curve")
    elif kind == "link":
        draw.rounded_rectangle([x - 13, y - 8, x + 4, y + 8], 3, fill=color)
        draw.polygon([(x + 5, y - 2), (x + 13, y - 7), (x + 13, y + 7), (x + 5, y + 2)], fill=color)


def card(canvas: Image.Image, k: int, shown: float, rows: dict, t: float, lit: float = 0.0) -> None:
    """Batch k's card, faded in by `shown`, each row by rows[row]; `lit` rings it in saffron."""
    if shown <= 0:
        return
    name, days, time, poses = BATCHES[k]
    draw = ImageDraw.Draw(canvas)
    box = card_box(k)
    edge = tint(SAFFRON, lit * shown, tint(LINE, shown)) if lit > 0 else tint(LINE, shown)
    draw.rounded_rectangle(box, 22, fill=tint(PAPER, shown), outline=edge, width=3 if lit <= 0 else 4)
    panel = f"batch {name}"
    layout.add(panel, "panel", box)
    x0, y0, x1, y1 = box
    layout.text(draw, (x0 + 30, y0 + 50), name, mv.font(36, serif=True), tint(MOSS, shown), "lm", name=f"{panel} name",
                owner=panel, container=box)
    for i, (row, words) in enumerate((("days", days), ("time", time), ("link", "Meet link"))):
        amount = rows.get(row, 0.0) * shown
        if amount > 0:
            y = y0 + 116 + i * 50
            icon(draw, row, x0 + 44, y, tint(SAFFRON if row == "link" else MUTED, amount))
            layout.text(draw, (x0 + 72, y), words, mv.font(25, 500), tint(INK, amount), "lm", name=f"{panel} {row}", owner=panel,
                        container=box)
    amount = rows.get("sequence", 0.0) * shown
    if amount > 0:
        layout.text(draw, (x0 + 30, y0 + 266), "Sequence", mv.font(22, 600), tint(MUTED, amount), "lm", name=f"{panel} sequence",
                    owner=panel, container=box)
        floor = y0 + 418
        draw.line([(x0 + 30, floor + 2), (x1 - 30, floor + 2)], fill=tint(LINE, amount), width=3)
        slot = (CARD_W - 60) / 3
        for j, pose in enumerate(poses):
            person = figures.Person(f"board{k}{j}", tint(FIGURE.shirt, amount, PAPER), tint(FIGURE.skin, amount, PAPER),
                                    tint(FIGURE.hair, amount, PAPER), tint(FIGURE.pants, amount, PAPER))
            angles = figures.moving(person, ((pose, 99.0),), t)
            cx = x0 + 30 + slot * (j + 0.5)
            figures.draw_figure(draw, person, angles, cx + centring(angles, FIGURE_H), floor, FIGURE_H)
            layout.add(f"{panel} pose {j}", "icon", (cx - slot / 2 + 6, floor - 1.15 * FIGURE_H, cx + slot / 2 - 6, floor))
    draw.line([(x0 + 30, y0 + 450), (x1 - 30, y0 + 450)], fill=tint(LINE, shown), width=2)


FIGURE_H = 100


def centring(angles: tuple, height: float) -> float:
    """How far to move a figure's x so its whole shape, not its pelvis, sits on the slot's middle: lying and folded
    poses reach far to one side."""
    j = figures.skeleton(angles, height)
    planted = max(0.0, math.cos(math.radians(angles[0]))) * (j["foot_a"][0] + j["foot_b"][0]) / 2
    xs = [x for x, _ in j.values()]
    head = figures.HEAD * height
    left, right = min(min(xs), j["head"][0] - head), max(max(xs), j["head"][0] + head)
    return planted - (left + right) / 2


def colour(key: str) -> tuple:
    from . import rooms  # the people with homes on the map keep their colours here

    return rooms.PEOPLE[key].person.shirt if key in rooms.PEOPLE else NEUTRAL[key]


def draw(canvas: Image.Image, t: float, cards: tuple = (1, 1, 1, 1), rows: dict | None = None, lit: str = "",
         arrive: float = -1.0, move: float = -1.0, note: float = -1.0, since: float = 0.0, look: float = -1.0) -> None:
    """The board at time t: each card and its students faded in by `cards`, its rows by `rows` (all shown if None),
    `lit` the batch ringed in saffron. `arrive` (0 to 1) brings the new student down into Pain management; `move` (0 to 1) takes a Beginner student to Intermediate, `note` (0 to 1) the teacher's note along
    with them, then "since" under them faded in by `since`. `look` (0 to 1) runs a soft ring over every student in
    turn: the teacher's review."""
    rows = {r: 1.0 for r in ROWS} if rows is None else rows
    for k, (name, *_) in enumerate(BATCHES):
        card(canvas, k, cards[k], rows, t, 1.0 if lit == name else 0.0)
    draw_ = ImageDraw.Draw(canvas)
    everyone = []
    for batch, keys in MEMBERS.items():
        k = [b[0] for b in BATCHES].index(batch)
        for i, key in enumerate(keys):
            if key == "rohan" and move >= 0:
                continue
            everyone.append((key, member_point(batch, i), cards[k]))
    if move >= 0:  # from Beginner to Intermediate in a low arc along the students' row, landing after the three there
        a, b = member_point("Beginner", 0), member_point("Intermediate", len(MEMBERS["Intermediate"]))
        p = ease(move)
        at = (a[0] + (b[0] - a[0]) * p, a[1] + (b[1] - a[1]) * p - 36 * math.sin(math.pi * p))
        everyone.append(("rohan", at, 1.0))
        if 0 < note < 1.05:  # the teacher's note goes with them, just above their right shoulder, then fades
            q = ease(min(note, 1.0))
            nx = a[0] + (b[0] - a[0]) * q
            message(canvas, (nx + 38, a[1] - 36 * math.sin(math.pi * q) - 44), min(1.0, note * 4, (1.05 - note) * 8))
        if since > 0:
            pill(draw_, b[0] + 20, b[1] + 78, SINCE, 22, MOSS, PAPER, LINE, "since", since, "mm", 600)
    if arrive >= 0:  # the new student, dropping into Pain management's row
        b = member_point("Pain management", len(MEMBERS["Pain management"]))
        p = ease(arrive)
        everyone.append(("kolkata", (b[0], b[1] - 40 * (1 - p)), min(1.0, arrive * 2)))
    for i, (key, (x, y), amount) in enumerate(everyone):
        if amount > 0:
            bust(draw_, x, y, colour(key), f"student {key}", amount)
            if look >= 0 and abs(look * (len(everyone) + 1) - i - 0.5) < 0.5:  # one at a time, clear of head and shoulders
                draw_.rounded_rectangle([x - 31, y - 40, x + 31, y + 29], 12, outline=SAFFRON, width=3)
                layout.add("review ring", "highlight", (x - 31, y - 40, x + 31, y + 29))


def message(canvas: Image.Image, at: tuple, opacity: float) -> None:
    """The teacher's note in flight, as on the map: a small card of lines."""
    w, h = 46, 32
    note = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(note)
    d.rounded_rectangle([1, 1, w - 2, h - 2], 8, fill=mv.SAFFRON_LIGHT, outline=SAFFRON, width=2)
    for k in range(3):
        d.line([(10, 9 + k * 7), (w - (10 if k < 2 else 20), 9 + k * 7)], fill=SAFFRON, width=2)
    note.putalpha(note.getchannel("A").point(lambda v: int(v * max(0.0, opacity))))
    x, y = round(at[0] - w / 2), round(at[1] - h / 2)
    canvas.paste(note, (x, y), note)
    layout.add("flying note", "icon", (x, y, x + w, y + h))


def picture(t: float, **state) -> Image.Image:
    canvas = Image.new("RGB", (mv.W, mv.H), CREAM)
    draw(canvas, t, **state)
    return canvas
