"""The film for Satt Chitt Anand v0.9, as an animated story (about two and a half minutes, 1920x1080, narrated): how the
class works without the app and what gets lost, in muted colour; then the app as v0.9 has it: the four batches; joining
with the group code, the intake and the teacher's approval into a batch; the class, how it felt and how each item went;
the teacher's review and feedback; the weeks that follow, with solo practice and a move between batches; Ask; and
what goes to the teacher's Sheet and what stays on the phone.

Figures, homes, the world, the batches, the camera, the music, the caption bar and the layout check come from
scripts/film/; the phone screens are the v0.9 tour's screenshots (scripts/film/screens.py). Every clock agrees with the
batches' times: the class is the Intermediate batch at 8:00 in India, on Thursday 19 November. The voice is
make_video's (Kokoro), so the captions follow it word by word. Everything drawn registers its box, and --qa fails if
anything collides (film/layout.py has the rules).

    tools/media-venv/bin/python scripts/make_advert.py --qa            # the layout check on every frame, QA frames
    tools/media-venv/bin/python scripts/make_advert.py --storyboard    # a frame per beat, with its line
    tools/media-venv/bin/python scripts/make_advert.py                 # the film, its captions, checked as drawn

Writes .local/visualization/viz_v0.9/satt_chitt_anand_film_1080p.mp4, a 720p copy under 30 MB to send
(satt_chitt_anand_film_720p.mp4), satt_chitt_anand_film.srt, and film/ for the checks.
"""

import argparse
import functools
import math
import multiprocessing
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable
from zoneinfo import ZoneInfo

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

import make_video as mv
from film import board, camera, chrome, figures, layout, music, rooms, screens, world
from film.chrome import CREAM, INK, LINE, MOSS, MUTED, PAPER, SAFFRON, VIEW_H, W, H, pill, tint
from make_video import BEZEL, MOSS_LIGHT, SAFFRON_LIGHT, SATT, ease, font, place_phone
from viz import folder

mv.WORK = mv.LOCAL / "work" / "advert"  # voice clips are cached here, apart from the tour's
FILM = folder("v0.9") / "satt_chitt_anand_film_1080p.mp4"
CHECKS = folder("v0.9") / "film"
SURYA = "[Surya Namaskar](/sˈʊɹjə nʌməskˈɑɹ/)"  # Kokoro's own guess runs the words together
ASANA = "[asana](/ˈɑsənə/)"
FPS = 30
LEAD, GAP, TAIL = 0.3, 0.25, 0.4
CHANGE = 0.8  # seconds to cross from one beat to the next
FADE = 0.25  # within a beat, from a phone to a map or the board and back: out and in through the background
SHADOW = 110
CHAPTERS = ("Before", "Batches", "Joining", "The class", "After class", "Over the weeks", "Ask", "Privacy")
PHONE_CX, PHONE_H, PHONE_TOP = 470, 840, 40
ZOOM_AREA = (760, 120, 1872, VIEW_H - 24)  # where a phone's highlighted card is shown enlarged
ROOM = (1000, 120, 1872, VIEW_H - 24)  # a room beside a phone
DOT, NIGHT = (186, 200, 180), (128, 136, 148)
LABEL_SIZE = 22
PAD, CLEAR = 20, 12  # a callout keeps PAD px of the card's own surroundings around its content, at least CLEAR of it empty
IST = ZoneInfo("Asia/Kolkata")


def ist(day: int, hour: int, minute: int) -> datetime:
    """A moment of November 2026, in India's time."""
    return datetime(2026, 11, day, hour, minute, tzinfo=IST)


# The moments the phones show, all from the batches' times (Beginner 7:00, Intermediate 8:00, Advanced 9:00 and Pain
# management 5:30 PM in India, each under an hour) and what the screens say. A new student in Kolkata signs up on
# Tuesday 17 Nov at 10:40 and waits; at 4:10 PM the teacher places them, and at 4:18 their next class is "Tomorrow ·
# 5:30 PM", starting "in 1 d 1 h". The class is Thursday 19 Nov at 8:00 (Sydney 1:30 PM); the teacher shares the
# links before it, and reviews it and writes feedback after the morning's classes; in the afternoon, after the
# student's evening practice in Sydney, they move a student between batches; all outside class hours.
SIGNUP = ist(17, 10, 40)
APPROVED = ist(17, 16, 10)
CLASS = world.CLASS_AT
SHARED = ist(19, 7, 50)
LIVE = ist(19, 8, 1)  # Sydney 1:31 PM: the class is live
AFTER = ist(19, 8, 57)  # Sydney 2:27 PM, just after the class
REVIEW = ist(19, 10, 15)
MOVED = ist(19, 14, 10)  # Sydney 7:40 PM, after the solo session there
EVENING = ist(19, 13, 40)  # Sydney 7:10 PM: practice, history, solo, Ask


def colour(key: str) -> tuple:
    """A person's colour: their shirt, as in their room."""
    return rooms.PEOPLE[key].person.shirt


# ---------- the world ----------

WORLD = world.View()
INDIA = world.View(81.0 - world.CENTRE, 21.0, 24.0)  # the teacher and the student in Kolkata, a long way apart
CLASS_CAST = ("teacher",) + rooms.STUDENTS
JOIN_CAST = ("teacher", "kolkata")
EVERYONE = {k: 1.0 for k in CLASS_CAST}
ALL_ARCS = {k: 1.0 for k in rooms.STUDENTS}


def label_text(key: str, moment: datetime, roles: bool = False) -> str:
    """A home's label: its place and time at `moment`, after who lives there with `roles`."""
    place = world.PLACES[key]
    who = f"{'Teacher' if key == 'teacher' else 'Student'}  ·  " if roles else ""
    return f"{who}{place.name}  ·  {place.time(moment)}"


@functools.lru_cache(maxsize=32)
def labels_for(view: world.View, keys: tuple, moment: datetime, roles: bool) -> dict:
    face = font(LABEL_SIZE, 600)
    widths = {k: face.getlength(label_text(k, moment, roles)) + 2 * round(LABEL_SIZE * 0.7) for k in keys}
    return world.place_labels(view, world.SIZE, keys, widths, round(LABEL_SIZE * 1.75),
                              (layout.SAFE, 150, W - layout.SAFE, VIEW_H - 16))


FLIGHT_SIZE = {"reaction": (64, 26), "strain": (90, 26)}  # anything else is a message, (46, 32)
STRAINED = ("sydney", "california")  # in Thursday's review, Asha and Priya flagged strain


def flight(picture: Image.Image, at: tuple, kind: str, opacity: float, avoid: list, sent: bool = False) -> None:
    """Something travelling along an arc: the invite, everyone's reactions, the teacher's feedback; not drawn where it
    would cover a home or a label (in `avoid`)."""
    w, h = FLIGHT_SIZE.get(kind, (46, 32))
    x, y = at
    box = (x - w / 2, y - h / 2, x + w / 2, y + h / 2)
    if opacity <= 0.02 or (not sent and any(layout.hits(box, other, 6) for other in avoid)):
        return
    icon = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(icon)
    if kind in ("reaction", "strain"):  # how each item went: dots in the scale's colours, and a flag for strain
        draw.rounded_rectangle([0, 0, w - 1, h - 1], h // 2, fill=PAPER, outline=LINE, width=2)
        for k, (_, color) in enumerate(screens.SCALE[1:]):
            draw.ellipse([10 + k * 17, h / 2 - 6, 22 + k * 17, h / 2 + 6], fill=color)
        if kind == "strain":
            draw.line([(67, 5), (67, 21)], fill=mv.DANGER, width=3)
            draw.polygon([(68, 5), (81, 9), (68, 14)], fill=mv.DANGER)
    else:  # a message: the invite with the group code, or feedback
        draw.rounded_rectangle([1, 1, w - 2, h - 2], 8, fill=SAFFRON_LIGHT if kind == "feedback" else PAPER,
                               outline=SAFFRON, width=2)
        for k in range(3):
            draw.line([(10, 9 + k * 7), (w - (10 if k < 2 else 20), 9 + k * 7)], fill=SAFFRON, width=2)
    icon.putalpha(icon.getchannel("A").point(lambda v: int(v * opacity)))
    picture.paste(icon, (round(box[0]), round(box[1])), icon)
    layout.add(f"{'sent' if sent else 'flying'} {kind}", "icon", box)


TOP_FADE = 130


@functools.cache
def top_fade() -> Image.Image:
    return Image.linear_gradient("L").resize((W, TOP_FADE)).point(lambda v: round(255 - v))


def map_frame(lit: dict, arcs: dict, flights: tuple = (), sun: float | None = None, labels: bool = True,
              cast: tuple = CLASS_CAST, moment: datetime = CLASS, view: world.View = WORLD, roles: bool = False,
              sent: tuple = ()) -> Image.Image:
    """The map, with each home of `cast` as a pin: `lit` and `arcs` map a place to how lit or drawn it is, `flights`
    are (from, to, how far, kind), one end always the teacher, and `sent` (place, kind, opacity) shows something
    just sent above a pin. Labels give each place's time at `moment` (after who lives there, with `roles`), where
    world.place_labels finds room; things in flight leave a pin's edge, fade in over their first 40 px and out over
    their last, and never cover a pin."""
    canvas = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(canvas)
    world.draw_map(draw, view, DOT, NIGHT, sun)
    canvas.paste(CREAM, (0, 0, W, TOP_FADE), top_fade())  # the dots fade out towards the top, so the map has no edge
    for key, drawn in arcs.items():
        world.draw_arc(draw, world.arc(view, "teacher", key), drawn, tint(SAFFRON, 0.8))
    keys = tuple(k for k in cast if lit.get(k, 0) > 0)
    spots = labels_for(view, cast, moment, roles) if labels else {}
    avoid = []
    for key in keys:  # leader lines first, beneath the pins: from the tip, or the head's edge, to the label
        x, y = view.xy(world.PLACES[key].lon, world.PLACES[key].lat)
        if key in spots and spots[key][1]:
            draw.line(world.leader(spots[key][0], x, y), fill=tint(MUTED, lit[key]), width=2)
    for key in keys:
        x, y = view.xy(world.PLACES[key].lon, world.PLACES[key].lat)
        box = world.draw_home(draw, x, y, tint(colour(key), lit[key]), PAPER, PAPER)
        layout.add(f"home {key}", "marker", box)
        avoid.append(box)
        if labels and 0 <= x <= W and 0 <= y <= VIEW_H and key not in spots:
            layout.problem(f"no room for the label of {key}")
        if key in spots:
            avoid.append(spots[key][0])
            pill(draw, spots[key][0][0], spots[key][0][1], label_text(key, moment, roles), LABEL_SIZE, INK, PAPER, LINE,
                 f"label {key}", lit[key])
            other = world.misread(view, world.SIZE, key, *spots[key], cast)
            if other:
                layout.problem(f"the label of {key} reads as {other}'s: its anchor is nearer that pin")
    for a, b, p, kind in flights:
        if 0 < p < 1:
            points = world.arc(view, "teacher", b if a == "teacher" else a, 64)
            if a != "teacher":
                points = points[::-1]
            start, end = world.PIN_R + 26, world.length(points) - world.PIN_R - 26
            d = start + (end - start) * p
            opacity = ease(min((d - start) / 40, (end - d) / 40, 1.0))
            flight(canvas, world.at_distance(points, d), kind, opacity, avoid)
    for key, kind, opacity in sent:  # just above the pin's head, before it leaves
        x, y = world.head(view, key, world.SIZE)
        flight(canvas, (x, y - world.PIN_R - 30), kind, opacity, avoid, sent=True)
    return canvas


def home_point(key: str, view: world.View = WORLD) -> tuple:
    """Where a home's pin head is on the picture."""
    return world.head(view, key, world.SIZE)


def answers(since: float) -> dict:
    """Everyone's answers after class: each shows above its home for 0.7 s, half a second after the one before, then
    flies to the teacher for 1.2 s; Asha's and Priya's carry the strain flag."""
    kinds = {k: "strain" if k in STRAINED else "reaction" for k in rooms.STUDENTS}
    sent = tuple((k, kinds[k], ease((since - 0.5 * i) / 0.3) * (1 - ease((since - 0.5 * i - 0.6) / 0.2)))
                 for i, k in enumerate(rooms.STUDENTS))
    flights = tuple((k, "teacher", (since - 0.5 * i - 0.7) / 1.2, kinds[k]) for i, k in enumerate(rooms.STUDENTS))
    return {"sent": sent, "flights": flights}


# ---------- phones and rooms ----------


@functools.lru_cache(maxsize=8)
def card_shadow(size: tuple[int, int]) -> Image.Image:
    shadow = Image.new("RGBA", (size[0] + 140, size[1] + 140), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([70, 82, 70 + size[0], 82 + size[1]], 26, fill=(0, 0, 0, 55))
    return shadow.filter(ImageFilter.GaussianBlur(18))


def owner_words(who: str, when: str = "") -> str:
    """ "Teacher · India · Thu 7:50 AM": whose phone, where, and when there, if `when`."""
    return f"{'Teacher' if who == 'teacher' else 'Student'}  ·  {world.PLACES[who].name}" + (f"  ·  {when}" if when else "")


def owner_label(draw: ImageDraw.ImageDraw, x: float, y: float, who: str, when: str = "") -> tuple:
    """Whose phone this is, where they are and their day and time (`when`), with a dot in their colour."""
    words = owner_words(who, when)
    box = pill(draw, x, y, "     " + words, LABEL_SIZE, INK, PAPER, LINE, "phone owner", weight=700)
    draw.ellipse([box[0] + 10, box[1] + 8, box[0] + 32, box[1] + 30], fill=colour(who))
    return box


def to_canvas(origin: tuple, picture: Image.Image, box: tuple) -> tuple:
    """A box in screen pixels, where it is on the canvas."""
    s = (picture.height - 2 * BEZEL) / 1200
    return tuple(origin[i % 2] + BEZEL + v * s for i, v in enumerate(box))


SCALE_ON_PHONE = (PHONE_H - 2 * BEZEL) / 1200  # canvas pixels per screen unit
STROKE = 4
RING_GAP = {True: 10, False: 12}  # px from a whole card's edge to its ring, or from words in a box
RING_INNER = (12 + STROKE) / SCALE_ON_PHONE  # words keep 12 px clear inside the stroke...
RING_CLEAR = 8 / SCALE_ON_PHONE  # ...and everything else 8 px clear outside it
SOFT = 6  # units from the content to a spotlight's soft edge, so the things next to it stay dimmed
BLUR = 3.5  # px: how much the spotlight softens what it dims


def ring_pad(name: str, region: str) -> float:
    return (RING_GAP[screens.is_card(name, region)] + STROKE) / SCALE_ON_PHONE


def ring_ok(name: str, region: str) -> bool:
    """Whether a region can have a ring: round a whole thing, nothing within its clear space."""
    return not screens.ring_clearance(name, region, ring_pad(name, region), RING_CLEAR, RING_INNER)


def highlight(canvas: Image.Image, origin: tuple, picture: Image.Image, name: str, region: str, amount: float) -> tuple:
    """What a region holds, picked out on the phone: the rest of the screen dimmed warmly, round it the same distance
    everywhere. A saffron ring marks the edge only round a whole card or a group of whole things, 10 to 12 px out,
    with words 12 px inside it and nothing else within 8 px outside it; where that does not fit (stacked cards, a
    form's rows, part of a card), the dimming's edge is soft and there is no ring. What is dimmed is also lightly
    blurred, so nothing outside the focus (another card's numbers) can be read; the blur stops 10 px outside the
    focus, so the focus itself stays sharp."""
    stroke = ring_ok(name, region)
    ring = to_canvas(origin, picture, screens.ring_box(name, region, ring_pad(name, region) if stroke else SOFT))
    if amount > 0:
        screen_box = tuple(round(v) for v in to_canvas(origin, picture, (0, 0, 540, 1200)))
        soften = Image.new("L", canvas.size, 0)
        draw = ImageDraw.Draw(soften)  # inside the bezel, and below the status bar, whose clock stays legible
        top = round(to_canvas(origin, picture, (0, screens.BAR, 0, 0))[1])
        draw.rounded_rectangle([screen_box[0] + 6, top, screen_box[2] - 6, screen_box[3] - 6], 28, fill=int(255 * amount))
        draw.rounded_rectangle([ring[0] - 6, ring[1] - 6, ring[2] + 6, ring[3] + 6], 14, fill=0)
        canvas.paste(canvas.crop(screen_box).filter(ImageFilter.GaussianBlur(BLUR)), screen_box[:2],
                     soften.filter(ImageFilter.GaussianBlur(2)).crop(screen_box))
        mask = Image.new("L", canvas.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle(to_canvas(origin, picture, (0, 0, 540, 1200)), 34, fill=int(130 * amount))
        draw.rounded_rectangle(ring, 16 if stroke else 10, fill=0)
        if not stroke:
            mask = mask.filter(ImageFilter.GaussianBlur(4))
        veil = Image.new("RGBA", canvas.size, CREAM + (0,))
        veil.putalpha(mask)
        canvas.alpha_composite(veil)
        if stroke:
            ImageDraw.Draw(canvas).rounded_rectangle(ring, 16, outline=SAFFRON + (int(255 * amount),), width=STROKE)
            layout.add("highlight", "highlight", ring)
    return ring


@functools.lru_cache(maxsize=64)
def edge_clear(name: str, box: tuple, size: tuple, radius: float) -> bool:
    """Whether a callout's outer CLEAR px, inside its rounded corners, are all one colour: nothing of its content
    reaches its edge."""
    a = np.asarray(screens.callout(name, box, size), dtype=np.int16)
    inside = np.asarray(mv.rounded_mask(size, round(radius))) > 128
    band = np.zeros(inside.shape, bool)
    band[:CLEAR], band[-CLEAR:], band[:, :CLEAR], band[:, -CLEAR:] = True, True, True, True
    pixels = a[band & inside]
    return (np.abs(pixels - np.median(pixels, axis=0)).sum(axis=1) > 24).mean() < 0.002


def enlarged(name: str, region: str, area: tuple, most: float) -> tuple:
    """A region's content cut out to fit `area`, at most `most` times its size: a whole card cut at its own edge, or
    a box's content with PAD px of what is around it. Returns (the cut in screen units, its size in pixels, the
    scale, its corner radius in pixels). Fails the layout check if the content reaches within CLEAR px of the cut's
    edge, or the cut slices an element of the screen's UI dump."""
    card = screens.is_card(name, region)
    if card:  # inside its soft, antialiased edge, so the cut is all card
        x0, y0, x1, y1 = (v + d for v, d in zip(screens.regions(name)[region][0], (1.5, 1.5, -1.5, -1.5), strict=True))
    else:
        x0, y0, x1, y1 = screens.content(name, region)
    pad = 0 if card else PAD
    s = min((area[2] - area[0] - 2 * pad) / (x1 - x0), (area[3] - area[1] - 2 * pad) / (y1 - y0), most)
    box = (x0 - pad / s, y0 - pad / s, x1 + pad / s, y1 + pad / s)
    size = (round((x1 - x0) * s + 2 * pad), round((y1 - y0) * s + 2 * pad))
    radius = (screens.corner(name, region) + 1) * s if card else 22
    if not edge_clear(name, box, size, radius):
        layout.problem(f"callout '{region}' on {name}: content within {CLEAR} px of its edge")
    for what in screens.cuts(name, tuple(round(v, 1) for v in box)):
        layout.problem(f"callout '{region}' on {name}: its edge slices '{what}'")
    return box, size, s, radius


def card_on(canvas: Image.Image, piece: Image.Image, rect: tuple, opacity: float, radius: float = 22) -> None:
    """An enlarged piece of a screen as a card with a soft shadow, at `rect`, faded in by `opacity`, its corners
    rounded by `radius` (a whole card's own); a light piece gets a thin outline, a dark card none."""
    rx0, ry0, rx1, ry1 = (round(v) for v in rect)
    size = (max(rx1 - rx0, 2), max(ry1 - ry0, 2))
    r = max(2, round(radius * size[0] / piece.width))
    shadow = card_shadow(size)
    if opacity < 1:
        shadow = shadow.copy()
        shadow.putalpha(shadow.getchannel("A").point(lambda v: int(v * opacity)))
    canvas.alpha_composite(shadow, (rx0 - 70, ry0 - 70))
    mask = mv.rounded_mask(size, r)
    if opacity < 1:
        mask = mask.point(lambda v: int(v * opacity))
    canvas.paste(piece.resize(size, Image.LANCZOS), (rx0, ry0), mask)
    edge = np.asarray(piece, dtype=np.int16)[[0, -1]].mean()
    if edge > 200:
        ImageDraw.Draw(canvas).rounded_rectangle([rx0, ry0, rx0 + size[0] - 1, ry0 + size[1] - 1], r,
                                                 outline=LINE + (int(255 * opacity),), width=2)
    layout.add("zoom", "phone", (rx0, ry0, rx1, ry1))


STRIP_GAP = 8  # screen units between the lines of a "strips" enlargement


@functools.lru_cache(maxsize=16)
def stacked(name: str, region: str, area: tuple, most: float) -> tuple:
    """A "strips" region's lines enlarged one under the other on their row's own fill, PAD px round them: (the
    picture, its size). Fails the layout check if a line's box slices words above or below it, or an element."""
    lines = screens.strips(name, region)
    x0, x1 = min(b[0] for b in lines), max(b[2] for b in lines)
    total = sum(b[3] - b[1] for b in lines) + STRIP_GAP * (len(lines) - 1)
    s = min((area[2] - area[0] - 2 * PAD) / (x1 - x0), (area[3] - area[1] - 2 * PAD) / total, most)
    size = (round((x1 - x0) * s + 2 * PAD), round(total * s + 2 * PAD))
    piece = Image.new("RGB", size, screens.screen(name).getpixel((x0 - 4, lines[0][1] + 2)))
    y = PAD
    drawn = screens.marks(name)
    for b in lines:
        part = screens.callout(name, (x0, b[1], x1, b[3]), (round((x1 - x0) * s), round((b[3] - b[1]) * s)))
        piece.paste(part, (PAD, round(y)))
        y += (b[3] - b[1] + STRIP_GAP) * s
        if drawn[b[1], x0:x1].any() or drawn[b[3] - 1, x0:x1].any():
            layout.problem(f"callout '{region}' on {name}: a line's box slices words at {b[1]}-{b[3]}")
        for what in screens.cuts(name, (x0, b[1], x1, b[3])):
            layout.problem(f"callout '{region}' on {name}: its edge slices '{what}'")
    return piece, size


def zoom_card(canvas: Image.Image, name: str, region: str, ring: tuple, amount: float) -> Callable | None:
    """The highlighted content enlarged beside the phone; it grows in from the edge of the right half, level with the
    content on the phone, so it never passes over the phone. Once it has settled, returns where a box of the screen
    (screen units) is on it."""
    if screens.strips(name, region):
        piece, (w, h) = stacked(name, region, ZOOM_AREA, 2.4)
        left = ZOOM_AREA[0] + (ZOOM_AREA[2] - ZOOM_AREA[0] - w) / 2
        top = min(max((ring[1] + ring[3]) / 2 - h / 2, ZOOM_AREA[1]), ZOOM_AREA[3] - h)
        if amount > 0:
            start = (ZOOM_AREA[0], ring[1], ZOOM_AREA[0] + ring[2] - ring[0], ring[3])
            rect = tuple(a + (b - a) * amount for a, b in zip(start, (left, top, left + w, top + h), strict=True))
            card_on(canvas, piece, rect, min(1.0, amount * 3))
        return None
    box, (w, h), s, radius = enlarged(name, region, ZOOM_AREA, 2.4)
    area = ZOOM_AREA
    left = area[0] + (area[2] - area[0] - w) / 2
    top = min(max((ring[1] + ring[3]) / 2 - h / 2, area[1]), area[3] - h)
    if amount <= 0:
        return None
    start = (area[0], ring[1], area[0] + ring[2] - ring[0], ring[3])  # the ring's size, at the right half's edge
    rect = tuple(a + (b - a) * amount for a, b in zip(start, (left, top, left + w, top + h), strict=True))
    card_on(canvas, screens.callout(name, box, (w, h)), rect, min(1.0, amount * 3), radius)
    if amount < 1:
        return None
    return lambda b: (left + (b[0] - box[0]) * s, top + (b[1] - box[1]) * s, left + (b[2] - box[0]) * s, top + (b[3] - box[1]) * s)


TAP = 1.1  # seconds a tap shows


def tap(canvas: Image.Image, target: tuple, since: float) -> None:
    """A tap on `target` (a button, a face, a chip, as a box on the canvas): a ring of its own shape (a pill round a
    button, a circle round a face) at least 8 px out from it, that grows a little, holds and fades."""
    if not 0 <= since <= TAP:
        return
    p = since / TAP
    x0, y0, x1, y1 = target
    grow = 8 + 6 * ease(min(1.0, p * 2.5))
    box = [round(x0 - grow), round(y0 - grow), round(x1 + grow), round(y1 + grow)]
    around = np.asarray(canvas.crop(box).convert("L"), dtype=float)
    around[round(y0) - box[1]:round(y1) - box[1], round(x0) - box[0]:round(x1) - box[0]] = np.nan
    under = np.nanmean(around)  # what the ring sits on, not what it rings: moss on a light screen, white on a dark card
    ring = Image.new("RGBA", (box[2] - box[0] + 1, box[3] - box[1] + 1), (0, 0, 0, 0))
    ImageDraw.Draw(ring).rounded_rectangle([0, 0, ring.width - 1, ring.height - 1], min(ring.width, ring.height) / 2,
                                           outline=(MOSS if under > 140 else (255, 255, 255)) + (int(230 * min(1.0, (1 - p) * 3)),),
                                           width=4)
    canvas.alpha_composite(ring, (box[0], box[1]))


def inside(a: tuple, b: tuple) -> bool:
    return a[0] >= b[0] and a[1] >= b[1] and a[2] <= b[2] and a[3] <= b[3]


def label_place(who: str, when: str = "") -> tuple:
    """Where a phone's owner label goes, and a film label after it."""
    width = font(LABEL_SIZE, 700).getlength("     " + owner_words(who, when)) + 2 * round(LABEL_SIZE * 0.7)
    x = PHONE_CX + screens.phone("waiting", PHONE_H).width // 2 + 26
    return x, PHONE_TOP + 8, x + width + 14


def labels(canvas: Image.Image, who: str, principle: str, when: str = "", amount: float = 1.0) -> None:
    """The owner label, with their day and time, and a principle or film label after it."""
    x, y, after = label_place(who, when)
    owner_label(ImageDraw.Draw(canvas), x, y, who, when)
    if principle:
        chrome.chip(canvas, principle, amount, after, y)


def phone_frame(name: str, who: str, moment: datetime, region: str = "", since: float = 9.0, principle: str = "",
                touch: str = "", tapped: float = -1.0, right: Image.Image | None = None) -> Image.Image:
    """`who`'s phone at `moment` and its owner, what a region holds picked out (`since` seconds ago) and enlarged
    beside it, or `right` (a room) beside it instead; `touch` is a region tapped `tapped` seconds ago."""
    clock = world.PLACES[who].clock(moment)
    canvas = Image.new("RGBA", (W, H), CREAM + (255,))
    if right is not None:
        canvas.paste(right, ROOM[:2])
    picture = screens.phone(name, PHONE_H, clock)
    origin = place_phone(canvas, picture, PHONE_CX, PHONE_TOP, SHADOW)
    layout.add("phone", "phone", (origin[0], origin[1], origin[0] + picture.width, origin[1] + picture.height))
    if screens.missing(name):
        layout.problem(f"screen {screens.SHOTS[name]} is still to be shot")
    on_zoom = None
    if region and region in screens.regions(name):
        ring = highlight(canvas, origin, picture, name, region, ease((since - 0.1) / 0.4))
        on_zoom = zoom_card(canvas, name, region, ring, ease((since - 0.3) / 0.5))
    if touch and touch in screens.regions(name):
        target = screens.regions(name)[touch][0]
        tap(canvas, to_canvas(origin, picture, target), tapped)
        if on_zoom and region and inside(target, screens.content(name, region)):  # and on the enlargement, where it reads
            tap(canvas, on_zoom(target), tapped)
    labels(canvas, who, principle, world.PLACES[who].time(moment))
    return canvas.convert("RGB")


CLOSE = (300, 150, 1620, VIEW_H - 40)  # where a close-up of a card goes


def close_up(name: str, who: str, moment: datetime, region: str, since: float, touch: str = "",
             tapped: float = -1.0) -> Image.Image:
    """One card of a screen, close up and alone, for what must not be shown around it (the teacher's name and story
    sit under the student's waiting card); `touch` is a region inside it tapped `tapped` seconds ago."""
    canvas = Image.new("RGBA", (W, H), CREAM + (255,))
    if screens.missing(name):
        layout.problem(f"screen {screens.SHOTS[name]} is still to be shot")
    box, (w, h), s, radius = enlarged(name, region, CLOSE, 3.2)
    left, top = (CLOSE[0] + CLOSE[2] - w) / 2, (CLOSE[1] + CLOSE[3] - h) / 2
    grow = 0.9 + 0.1 * ease(since / 0.5)
    cx, cy = left + w / 2, top + h / 2
    rect = (cx - w * grow / 2, cy - h * grow / 2, cx + w * grow / 2, cy + h * grow / 2)
    card_on(canvas, screens.callout(name, box, (w, h)), rect, ease(since / 0.3), radius)
    if touch:
        bx0, by0, bx1, by1 = screens.regions(name)[touch][0]
        tap(canvas, (left + (bx0 - box[0]) * s, top + (by0 - box[1]) * s, left + (bx1 - box[0]) * s, top + (by1 - box[1]) * s), tapped)
    owner_label(ImageDraw.Draw(canvas), left, top - 66, who, world.PLACES[who].time(moment))
    return canvas.convert("RGB")


def room_picture(key: str, angles: tuple, size: tuple, hour: float | None = None) -> Image.Image:
    picture = Image.new("RGB", size, CREAM)
    rooms.draw_room(picture, (0, 0, *size), rooms.PEOPLE[key], angles, hour=hour)
    return picture


TILES = rooms.grid_boxes((layout.SAFE, 110, W - layout.SAFE, VIEW_H - 16), 16)


def grid(t: float, sequence: tuple, dim: float = 0.0, wince: float = 0.0, wonder: float = 0.0,
         moment: datetime = CLASS) -> Image.Image:
    """The class as a call at `moment`: each home in its tile, everyone moving through `sequence` at time t."""
    canvas = Image.new("RGB", (W, H), CREAM)
    draw = ImageDraw.Draw(canvas)
    for key, (x0, y0, x1, y1) in TILES.items():
        home = rooms.PEOPLE[key]
        joints = rooms.draw_room(canvas, (x0, y0, x1, y1), home, figures.moving(home.person, sequence, t), figure=0.66)
        draw.rounded_rectangle([x0, y0, x1, y1], 18, outline=SAFFRON if key == "teacher" else LINE, width=5 if key == "teacher" else 2)
        place = world.PLACES[key]
        words = f"{'Teacher' if key == 'teacher' else 'Student'}  ·  {place.name}  ·  {place.time(moment)}"
        pill(draw, x0 + 14, y0 + 14, words, LABEL_SIZE, INK, PAPER, LINE, f"tile {key}")
        if key == "sydney" and wince > 0:  # a strain at the knee, that no one in the call can see
            kx, ky = joints["knee_a"]
            for k in range(3):
                a = math.radians(-60 + k * 30)
                draw.line([(kx + 30 * math.cos(a), ky - 30 + 30 * math.sin(a)), (kx + 58 * math.cos(a), ky - 30 + 58 * math.sin(a))],
                          fill=mv.DANGER, width=round(7 * wince))
            draw.ellipse([kx - 16, ky - 16, kx + 16, ky + 16], outline=mv.DANGER, width=round(5 * wince))
            layout.add("strain mark", "icon", (kx - 16, ky - 90, kx + 60, ky + 16))
        if key == "sydney":
            head = joints["head"]
    if dim > 0:
        canvas = Image.blend(canvas, Image.new("RGB", (W, H), CREAM), 0.75 * dim)
        layout.ITEMS[:] = [i for i in layout.ITEMS if not i.name.startswith("tile")]  # faded out under the veil
        pill(ImageDraw.Draw(canvas), W / 2, 79, "Call ended", 26, PAPER, INK, INK, "call ended", dim, "mm")
    if wonder > 0:  # the strained student's question that never gets asked, over the veil so it reads
        draw = ImageDraw.Draw(canvas)
        hx, hy = head
        bubble = (hx + 44, hy - 76, hx + 144, hy + 14)
        draw.ellipse(bubble, fill=tint(PAPER, wonder), outline=tint(INK, wonder), width=3)
        draw.ellipse([hx + 24, hy - 12, hx + 38, hy + 2], fill=tint(PAPER, wonder), outline=tint(INK, wonder), width=2)
        layout.add("question bubble", "label", bubble)
        layout.text(draw, ((bubble[0] + bubble[2]) / 2, (bubble[1] + bubble[3]) / 2), "?", font(54, 700), tint(INK, wonder),
                    "mm", name="question mark", owner="question bubble", container=bubble)
    return canvas


KNEEL = (("vajrasana", 99.0),)
STAND = (("tadasana", 99.0),)
SEATED = figures.POSES["seated"]
PRACTICE = (("tadasana", 0.2), ("virabhadrasana", 0.8), ("trikonasana", 0.8))  # from the Intermediate sequence
TRYING = (("tadasana", 0.5), ("vrikshasana", 1.4), ("tadasana", 0.2), ("trikonasana", 1.4), ("tadasana", 9.0))  # the intake's poses
SOLO = (("vajrasana", 99.0),)  # kneeling through the hold, as the stopwatch runs


# ---------- steps within a beat ----------


@dataclass(frozen=True)
class Step:
    start: float  # in the beat's time
    kind: str  # steps of one kind cut from one to the next (a phone's screens); of different kinds, they fade
    draw: Callable  # the picture, by seconds since the step started


def play(steps: tuple, t: float) -> Image.Image:
    """The step on at beat time t; across a change of kind, out and in through the background."""
    k = max((i for i, s in enumerate(steps) if s.start <= t), default=0)
    step = steps[k]
    picture = step.draw(t - step.start)
    amount = 1.0
    if k and steps[k - 1].kind != step.kind:
        amount = min(amount, (t - step.start) / FADE)
    if k + 1 < len(steps) and steps[k + 1].kind != step.kind:
        amount = min(amount, (steps[k + 1].start - t) / FADE)
    if amount < 1:
        picture = Image.blend(Image.new("RGB", picture.size, CREAM), picture, ease(amount))
    return picture


def on_phone(who: str, name: str, moment: datetime, region: str = "", principle: str = "", touch: str = "",
             at: float = 0.8, room: Callable | None = None) -> Callable:
    """A step's picture: `who`'s phone at `moment` on screen `name`, `region` picked out, `touch` tapped `at` seconds
    in, or a room beside it drawn by `room` (seconds in to a picture)."""
    return lambda since: phone_frame(name, who, moment, region, since, principle, touch, since - at if touch else -1.0,
                                     room(since) if room else None)


def in_room(key: str, sequence: tuple, moment: datetime) -> Callable:
    """`key`'s room beside their phone, its person moving through `sequence`, its window lit for `moment`."""
    size, hour = (ROOM[2] - ROOM[0], ROOM[3] - ROOM[1]), world.PLACES[key].hour(moment)
    return lambda since: room_picture(key, figures.moving(rooms.PEOPLE[key].person, sequence, since), size, hour)


def said(key: str, line: int, word: str) -> float:
    """When `word` starts in line `line` of beat `key`, in the beat's own time."""
    return mv.said_at(placed_beat(key), line, word)


def line_start(key: str, line: int) -> float:
    return placed_beat(key).line_starts[line]


def line_end(key: str, line: int) -> float:
    placed = placed_beat(key)
    return placed.line_starts[line] + placed.line_seconds[line]


def placed_beat(key: str) -> mv.Placed:
    return next(p for p in PLAN if p.scene.key == key)


# ---------- the beats: each draws its picture at time t (seconds into the beat) ----------


def b_title(t: float) -> Image.Image:
    canvas = Image.new("RGB", (W, H), CREAM)
    chrome.masthead(ImageDraw.Draw(canvas), ease((t - 0.1) / 0.8), ease((t - 0.8) / 0.6), ease((t - 1.4) / 0.6))
    return canvas


def b_link(t: float) -> Image.Image:
    """Before: the class link pushed up the group chat in California at 6:20 PM, as the messages arrive."""
    canvas = Image.new("RGBA", (W, H), CREAM + (255,))
    canvas.paste(room_picture("california", SEATED, (ROOM[2] - ROOM[0], ROOM[3] - ROOM[1])), ROOM[:2])
    picture = mv.framed(screens.status_bar(screens.chat(t), "6:20"), PHONE_H)
    origin = place_phone(canvas, picture, PHONE_CX, PHONE_TOP, SHADOW)
    layout.add("phone", "phone", (origin[0], origin[1], origin[0] + picture.width, origin[1] + picture.height))
    labels(canvas, "california", "")
    return canvas.convert("RGB")


def b_shape(t: float) -> Image.Image:
    return grid(t, KNEEL, wince=ease((t - 0.8) / 0.4))


def b_lost(t: float) -> Image.Image:
    return grid(t, STAND, dim=ease((t - 0.3) / 0.6), wonder=1 - ease((t - 1.6) / 1.2), moment=CLASS + timedelta(minutes=55))


FORGOTTEN = (("Which asana hurt?", "sydney", 0, -100), ("Try a folded blanket", "teacher", 200, 40),
             ("Practised 20 minutes", "dubai", 0, -84), ("Was it Trikonasana?", "california", 0, -100))  # (x, y) from home


def b_forgot(t: float) -> Image.Image:
    """Days pass over the map; what was said drifts up from each home and fades."""
    canvas = map_frame(EVERYONE, {}, sun=world.CENTRE + 30 - 360 * t / 14.0, labels=False)  # slow, its edge soft
    draw = ImageDraw.Draw(canvas)
    for k, (words, key, dx, dy) in enumerate(FORGOTTEN):
        x, y = home_point(key)
        fade = max(0.0, 1 - abs(t - 0.6 - k * 0.5) / 1.1)
        if fade > 0.05:
            pill(draw, x + dx, y + dy - 24 * max(0.0, t - k * 0.5), words, LABEL_SIZE, MUTED, PAPER, LINE, f"said {key}", fade,
                 "mm", 500)
    return canvas


def b_turn(t: float) -> Image.Image:
    return map_frame(EVERYONE, {}, labels=False)  # the same homes; colour comes back as the beat's muting lifts


def b_batches(t: float) -> Image.Image:
    """The four batches, each card as it is named; then its days, time, Meet link and sequence as each is said."""
    names = ("Beginner", "Intermediate", "Advanced", "Pain")
    cards = tuple(ease((t - 0.1 * k) / 0.4) for k in range(4))
    times = [said("batches", 0, n) - 0.1 for n in names] + [line_start("batches", 1) - 0.2]
    lit = next((board.BATCHES[k][0] for k in range(4) if times[k] <= t < times[k + 1]), "")
    rows = {"days": 1.0, "time": 1.0} | {row: ease((t - said("batches", 1, word) + 0.1) / 0.4)
                                         for row, word in (("link", "Meet"), ("sequence", "sequence"))}
    return board.picture(t, cards=cards, rows=rows, lit=lit)


@functools.cache
def signup_steps() -> tuple:
    return (Step(0.0, "map", lambda since: map_frame(
                {"teacher": 1.0, "kolkata": 1.0}, {"kolkata": 1.0}, (("teacher", "kolkata", (since - 0.2) / 1.3, "invite"),),
                cast=JOIN_CAST, moment=SIGNUP, view=INDIA, roles=True)),
            Step(1.9, "phone kolkata", on_phone("kolkata", "signup", SIGNUP, "code", touch="create",
                                                at=line_end("signup", 0) - 1.9 - 0.4)))


def b_signup(t: float) -> Image.Image:
    """The group's invite, with its code, reaches a new student in Kolkata; they sign up with it."""
    return play(signup_steps(), t)


@functools.cache
def intake_steps() -> tuple:
    later = SIGNUP.replace(minute=46)
    return (Step(0.0, "close kolkata", lambda since: close_up("waiting", "kolkata", later, "waiting", since, "tell", since - 1.0)),
            Step(said("intake", 0, "age") - 0.5, "phone kolkata", on_phone("kolkata", "intake", later, "body")),
            Step(said("intake", 0, "food") - 0.5, "phone kolkata", on_phone("kolkata", "intake", later, "foodpain")),
            Step(line_start("intake", 1), "phone kolkata", on_phone("kolkata", "intake_poses", later,
                                                                   room=in_room("kolkata", TRYING, later))),
            Step(line_start("intake", 2), "phone kolkata", on_phone("kolkata", "intake", later, "consent")),
            Step(said("intake", 2, "Then"), "close kolkata", lambda since: close_up("thanks", "kolkata", later, "thanks", since)))


def b_intake(t: float) -> Image.Image:
    """From the waiting card, close up (the teacher's name and story sit under it): about you, food and pain, the
    poses tried at home, the line about where the answers go; then the thanks, close up too."""
    return play(intake_steps(), t)




@functools.cache
def approve_steps() -> tuple:
    approves = said("approve", 0, "approves") - 0.2
    return (Step(0.0, "phone teacher", on_phone("teacher", "students_waiting", APPROVED, "intake")),
            Step(approves, "phone teacher", on_phone("teacher", "students_waiting", APPROVED, "place", touch="approve", at=1.0)),
            Step(max(line_end("approve", 0) + 0.15, approves + 1.0 + TAP + 0.2), "board",
                 lambda since: board.picture(since, lit="Pain management", arrive=(since - 0.3) / 0.9)))


def b_approve(t: float) -> Image.Image:
    """The teacher reads the intake on the student's waiting card, then approves into the batch it points to,
    preselected, on the same card; the student drops into Pain management."""
    return play(approve_steps(), t)


def b_placed(t: float) -> Image.Image:
    return on_phone("kolkata", "placed_today", APPROVED.replace(minute=18), "batch")(t)


@functools.cache
def share_steps() -> tuple:
    chip = "Fits how the class works"
    return (Step(0.0, "phone teacher", on_phone("teacher", "batches", SHARED, "links", chip)),
            Step(said("share", 0, "on") - 0.2, "phone teacher", on_phone("teacher", "batches", SHARED, "share", chip,
                                                                         touch="share_button", at=0.6)))


def b_share(t: float) -> Image.Image:
    """A batch's link shared on WhatsApp from the app; each batch's everyday Meet link, with its time."""
    return play(share_steps(), t)


def b_world(t: float) -> Image.Image:
    lit = {"teacher": ease(t / 0.6)} | {k: ease((t - 0.8 - 0.5 * i) / 0.6) for i, k in enumerate(rooms.STUDENTS)}
    arcs = {k: ease((t - 0.9 - 0.5 * i) / 0.8) for i, k in enumerate(rooms.STUDENTS)}
    canvas = map_frame(lit, arcs)
    chrome.chip(canvas, "The teacher at the centre", ease((t - 0.8) / 0.5), layout.SAFE, layout.SAFE)
    return canvas


@functools.cache
def join_steps() -> tuple:
    joined = line_start("join", 1)
    return (Step(0.0, "phone sydney", on_phone("sydney", "mock:next:today", LIVE, "next", touch="join", at=joined)),
            Step(joined + TAP + 0.1, "phone sydney", on_phone("sydney", "mock:next:checkin", LIVE, "mood", touch="face", at=1.1)))


def b_join(t: float) -> Image.Image:
    """The student's Today: their batch and its next class, live; Join, and how they feel before it."""
    return play(join_steps(), t)


def b_practice(t: float) -> Image.Image:
    return grid(t, PRACTICE, moment=LIVE)


@functools.cache
def react_steps() -> tuple:
    chip = "How it felt, not how it looked"
    return (Step(0.0, "phone sydney", on_phone("sydney", "after", AFTER, "mood", chip)),
            Step(said("react", 0, "give"), "phone sydney", on_phone("sydney", "after", AFTER, "item", chip)),
            Step(line_start("react", 1), "phone sydney", on_phone("sydney", "after_items", AFTER, "strain", chip)))


def b_react(t: float) -> Image.Image:
    """After class: the mood now, one tap per item, the strain flag and a note."""
    return play(react_steps(), t)


@functools.cache
def review_steps() -> tuple:
    return (Step(0.0, "map", lambda since: map_frame(EVERYONE, ALL_ARCS, **answers(since + 0.4), moment=AFTER)),
            Step(2.3, "phone teacher", on_phone("teacher", "insights", REVIEW, "class", touch="link", at=0.8)),
            Step(3.6, "phone teacher", on_phone("teacher", "class_review", REVIEW, "strain")))


def b_review(t: float) -> Image.Image:
    return play(review_steps(), t)


@functools.cache
def feedback_steps() -> tuple:
    later = REVIEW.replace(minute=20)
    end = max(line_end("feedback", 0) + 0.2, said("feedback", 0, "about") + 3.4)
    return (Step(0.0, "phone teacher", on_phone("teacher", "asha_items", later, "item")),
            Step(said("feedback", 0, "about"), "phone teacher", on_phone("teacher", "feedback_sent", later, "wrote")),
            Step(end, "map", lambda since: map_frame(EVERYONE, {"sydney": 1.0}, (("teacher", "sydney", since / 1.2, "feedback"),),
                                                     moment=later)))


def b_feedback(t: float) -> Image.Image:
    """The student's items, the teacher's word on one, and it on its way to Sydney."""
    return play(feedback_steps(), t)


WEEKS = 1.2  # days going by on the map


@functools.cache
def weeks_steps() -> tuple:
    chip = "A rhythm to return to"

    def passing(since: float) -> Image.Image:  # days going by, the sun across the map; the chip where it stays after
        canvas = map_frame(EVERYONE, ALL_ARCS, sun=world.CENTRE + 30 - 360 * since / 0.6, labels=False)
        chrome.chip(canvas, chip, ease((since - 0.2) / 0.4), *label_place("sydney", world.PLACES["sydney"].time(EVENING))[2:],
                    PHONE_TOP + 8)
        return canvas

    return (Step(0.0, "map", passing),
            Step(WEEKS, "phone sydney", on_phone("sydney", "practice", EVENING, "item", chip)),
            Step(said("weeks", 0, "what") - 0.2, "phone sydney", on_phone("sydney", "history", EVENING, "wrote", chip)),
            Step(line_start("weeks", 1), "phone sydney", on_phone("sydney", "history", EVENING, "each", chip)))


def b_weeks(t: float) -> Image.Image:
    """Weeks go by; Practice has each item's trend and the teacher's word; an item opens to its history."""
    return play(weeks_steps(), t)


@functools.cache
def solo_steps() -> tuple:
    later = EVENING.replace(minute=50)
    return (Step(0.0, "phone sydney", on_phone("sydney", "solo_choose", later, "list")),
            Step(said("solo", 0, "stopwatch") - 0.3, "phone sydney", on_phone("sydney", "solo_running", later,
                                                                             room=in_room("sydney", SOLO, later))),
            Step(said("solo", 0, "It"), "phone sydney", on_phone("sydney", "history_solo", later.replace(hour=14, minute=1), "solo")))


def b_solo(t: float) -> Image.Image:
    """Practice on one's own: items chosen, each timed with a stopwatch (the student holds Vajrasana at home), and
    the session in the item's history."""
    return play(solo_steps(), t)


@functools.cache
def move_steps() -> tuple:
    look, moved = said("move", 0, "and") - 0.2, line_end("move", 0) + 0.2
    return (Step(0.0, "board", lambda since: board.picture(since, arrive=1.0, look=(since - 0.2) / (look - 0.4))),
            Step(look, "phone teacher", on_phone("teacher", "move", MOVED, "picker", touch="move_button", at=moved - look - 0.7)),
            Step(moved, "board", lambda since: board.picture(since, lit="Intermediate", arrive=1.0, move=(since - 0.1) / 1.0,
                                                             note=(since - 0.2) / 1.0)),
            Step(line_start("move", 1), "phone teacher", on_phone("teacher", "students_placed", MOVED.replace(minute=41), "since")))


def b_move(t: float) -> Image.Image:
    """The teacher looks over each student; moves one up to Intermediate with a note; the card then says since when."""
    return play(move_steps(), t)


ASKED = EVENING.replace(hour=14, minute=45)  # Sydney 8:15 PM


@functools.cache
def ask_steps() -> tuple:
    label = "Gemma  ·  on this phone"
    return (Step(0.0, "phone sydney", on_phone("sydney", "ask", ASKED, "about", label)),
            Step(line_start("ask", 1), "phone sydney", on_phone("sydney", "ask", ASKED, "chip", label, touch="chip", at=0.5)),
            Step(line_start("ask", 1) + 0.9, "phone sydney", on_phone("sydney", "ask_answer", ASKED.replace(minute=46), "answer",
                                                                      label)))


def b_ask(t: float) -> Image.Image:
    """Ask, on the phone: what it knows; a suggested question tapped; the answer, from the student's own practice."""
    return play(ask_steps(), t)


SHEET = (1080, 110, 1872, 700)  # the teacher's Google Sheet, its Dashboard a tab inside it
DASHBOARD = (1112, 420, 1840, 668)
KEPT = (560, 640, 1010, 860)  # what stays on the phone
GOES = ("The intake", "Check-ins and moods", "How each item went", "Notes on items", "Solo practice")


def chip_box(i: int) -> tuple:
    """Where the Sheet's i-th chip settles: two columns under its title."""
    x = SHEET[0] + 32 + (i % 2) * 384
    y = SHEET[1] + 75 + (i // 2) * 64
    return x, y


def b_privacy(t: float) -> Image.Image:
    """What goes where: the phone on the left, on Practice (after the evening's solo session) while the practice and
    the intake leave it, then on the health notes, which stay, until one is shared; the teacher's Sheet on the right,
    each kind of practice flying into it as it is said, the shared note after it; the Sheet's Dashboard with the
    intake only as counts."""
    canvas = Image.new("RGBA", (W, H), CREAM + (255,))
    goes, kept, shared, counts = (said("privacy", 0, "intake") - 0.2, line_start("privacy", 1), said("privacy", 1, "shares"),
                                  line_start("privacy", 2))
    before = "practice_after" if not screens.missing("practice_after") else "practice"  # 07 until 12b is shot
    name = before if t < kept - 0.15 else "me" if t < shared - 0.3 else "me_shared"
    now = ASKED.replace(minute=50)
    picture = screens.phone(name, PHONE_H, world.PLACES["sydney"].clock(now))
    origin = place_phone(canvas, picture, 290, PHONE_TOP, SHADOW)
    layout.add("phone", "phone", (origin[0], origin[1], origin[0] + picture.width, origin[1] + picture.height))
    if screens.missing(name):
        layout.problem(f"screen {screens.SHOTS[name]} is still to be shot")
    draw = ImageDraw.Draw(canvas)
    owner_label(draw, origin[0] + picture.width + 26, PHONE_TOP + 8, "sydney", world.PLACES["sydney"].time(now))
    # What stays on the phone, from the second line; one note leaves it when the student shares it.
    stay = ease((t - kept + 0.1) / 0.5)
    if stay > 0:
        panel(draw, KEPT, "Stays on the phone", tint(PAPER, stay), tint(SAFFRON, stay), tint(SAFFRON, stay), stay)
        for i, words in enumerate(("Gemma chat", "Health notes, unless shared")):
            pill(draw, KEPT[0] + 32, KEPT[1] + 82 + i * 58, words, 24, tint(INK, stay), tint(SAFFRON_LIGHT, stay), None, f"stays {i}",
                 stay)
    # The Sheet: each kind of practice flies in as a message and lands as its chip.
    panel(draw, SHEET, "The teacher’s Google Sheet", MOSS_LIGHT, MOSS, MOSS)
    for i, words in enumerate((*GOES, "A shared note")):
        start = (origin[0] + picture.width + 30, origin[1] + (300 if i < len(GOES) else 500))
        leave = goes + 0.45 * i if i < len(GOES) else shared + 0.2
        p = (t - leave) / 0.9
        end = chip_box(i)
        if 0 < p < 1:  # to the Sheet's edge, level with where it lands, so it never crosses the Sheet's words
            q = ease(p)
            x = start[0] + (SHEET[0] - 34 - start[0]) * q
            y = start[1] + (end[1] + 21 - start[1]) * q - 60 * math.sin(math.pi * q)
            board.message(canvas, (x, y), min(1.0, p * 5, (1 - p) * 5))
        elif p >= 1:
            pill(draw, *end, words, 24, INK, SAFFRON_LIGHT if i == len(GOES) else PAPER, SAFFRON if i == len(GOES) else LINE,
                 f"goes {i}", ease((p - 1) * 0.9 / 0.3))
    # The Sheet's Dashboard: the intake, only as counts.
    show = ease((t - counts + 0.1) / 0.5)
    if show > 0:
        panel(draw, DASHBOARD, "Dashboard", tint(PAPER, show), tint(MOSS, show), tint(MOSS, show), show)
        layout.text(draw, (DASHBOARD[0] + 32, DASHBOARD[1] + 92), "Pain areas from the intake, as counts", font(24, 500),
                    tint(MUTED, show), "lm", name="dashboard note", owner="panel Dashboard", container=DASHBOARD)
        for i, (area, n) in enumerate((("Knee", 3), ("Back", 1))):
            y = DASHBOARD[1] + 150 + i * 52
            layout.text(draw, (DASHBOARD[0] + 32, y), area, font(24, 600), tint(INK, show), "lm", name=f"count {area}",
                        owner="panel Dashboard", container=DASHBOARD)
            draw.rounded_rectangle([DASHBOARD[0] + 140, y - 12, DASHBOARD[0] + 140 + 90 * n * ease((t - counts - 0.3) / 0.6), y + 12],
                                   12, fill=tint(MOSS, show))
            layout.text(draw, (DASHBOARD[0] + 150 + 90 * 3 + 16, y), str(n), font(24, 700), tint(MOSS, show), "lm",
                        name=f"count {area} n", owner="panel Dashboard", container=DASHBOARD)
    return canvas.convert("RGB")


def panel(draw: ImageDraw.ImageDraw, box: tuple, title: str, fill: tuple, edge: tuple, ink: tuple, amount: float = 1.0) -> None:
    """A titled box of the privacy picture, its words registered with it."""
    draw.rounded_rectangle(box, 22, fill=fill, outline=edge, width=3)
    name = f"panel {title.split()[0] if title.startswith('Dash') else title}"
    layout.add(name, "panel", box)
    layout.text(draw, (box[0] + 32, box[1] + 40), title, font(30, 700), ink, "lm", name=name + " title", owner=name, container=box)


def b_end(t: float) -> Image.Image:
    canvas = Image.new("RGB", (W, H), CREAM)
    chrome.masthead(ImageDraw.Draw(canvas), ease((t - 0.1) / 0.8), ease((t - 0.5) / 0.6), ease((t - 0.8) / 0.6))
    return canvas


@dataclass(frozen=True)
class Beat:
    key: str
    chapter: str
    lines: tuple
    draw: Callable
    least: float  # the shortest it can be: its animation's length
    still: float  # the moment shown on the storyboard
    muted: Callable = lambda t: 0.0  # the "before" look, by time
    enter: tuple = ()  # zoom in from the beat before, through (its point, this beat's point); else a change through cream
    steps: Callable | None = None  # its steps, for a QA frame as each settles
    pauses: tuple = ()  # (line, seconds): a longer gap after that line, for a card to be read


BEFORE = lambda t: 1.0  # noqa: E731
PHONE_POINT = (PHONE_CX, 460)
BEATS = (
    Beat("title", "", (f"{SATT}. Truth, consciousness, bliss.",), b_title, 3.4, 2.4),
    Beat("before_link", "Before", ("Today, the class link gets buried in the group chat.",), b_link, 3.5, 3.0, BEFORE),
    Beat("before_shape", "Before", ("On Meet, the teacher sees the shape of each pose, not how it felt.",), b_shape, 3.8, 2.0, BEFORE),
    Beat("before_lost", "Before", ("When the call ends, whatever someone felt goes unsaid.",), b_lost, 3.2, 1.0, BEFORE),
    Beat("before_forgot", "Before", ("And from week to week, nothing is remembered.",), b_forgot, 3.4, 1.1, BEFORE),
    Beat("turn", "Before", (f"{SATT} keeps the class as it is, and adds what was missing.",), b_turn, 4.0, 1.4,
         lambda t: 1 - ease((t - 0.6) / 1.6)),
    Beat("batches", "Batches", ("The class runs in four batches: Beginner, Intermediate, Advanced, and Pain management.",
                                "Each has its own days, time, Meet link and sequence."), b_batches, 9.0, 9.4),
    Beat("signup", "Joining", ("New students sign up with the class's group code, which keeps strangers out.",), b_signup, 4.5, 3.4,
         steps=signup_steps),
    Beat("intake", "Joining", ("Then they tell the teacher their age, height and weight, food, and any pain.",
                               "And how six poses feel.", "The answers go to the teacher, to place them in a batch. Then they wait."),
         b_intake, 10.0, 1.4, steps=intake_steps, pauses=((0, 0.8),)),
    Beat("approve", "Joining", ("The teacher reads them on the waiting card, and approves the student into the batch they point to.",),
         b_approve, 7.2, 1.6, steps=approve_steps),
    Beat("placed", "Joining", ("Their Today now names their batch.",), b_placed, 3.0, 2.0),
    Beat("share", "The class", ("The teacher shares each batch's link on WhatsApp.",), b_share, 4.0, 3.4, steps=share_steps),
    Beat("world", "The class", ("Intermediate starts in India at eight. Its students join from wherever they are.",), b_world, 4.5, 3.0),
    Beat("join", "The class", ("Today shows a student's batch and its next class.", "They join the Meet, and say how they feel."),
         b_join, 6.4, 1.6, enter=(home_point("sydney"), PHONE_POINT), steps=join_steps),
    Beat("practice", "The class", ("Then they practise together.",), b_practice, figures.length(PRACTICE) + 0.4, 4.0),
    Beat("react", "After class", ("After class, they say how they feel now, and give each item one tap, from not yet to at ease.",
                                  "If something hurt, they flag strain or pain, and can add a note."),
         b_react, 9.0, 5.0, enter=(((TILES["sydney"][0] + TILES["sydney"][2]) / 2, (TILES["sydney"][1] + TILES["sydney"][3]) / 2),
                                    PHONE_POINT), steps=react_steps),
    Beat("review", "After class", ("The teacher's review of the class shows strain and pain first.",), b_review, 6.0, 5.0,
         steps=review_steps),
    Beat("feedback", "After class", (f"Then the teacher writes to each student about each {ASANA}.",), b_feedback, 6.2, 3.8,
         steps=feedback_steps),
    Beat("weeks", "Over the weeks", ("Over the weeks, Practice shows how each item has gone, and what the teacher wrote.",
                                     "Each item opens to its history."), b_weeks, 7.0, 4.0, steps=weeks_steps),
    Beat("solo", "Over the weeks", ("Students can also practise on their own, with a stopwatch for each item. It joins the same "
                                    "history.",), b_solo, 6.0, 3.6, steps=solo_steps),
    Beat("move", "Over the weeks", ("Every few weeks, the teacher reviews each student, and can move them to another batch, with "
                                    "a note.", "Their card then shows the batch, and since when."), b_move, 9.0, 8.4,
         steps=move_steps, pauses=((0, 1.2),)),
    Beat("ask", "Ask", ("On phones with enough memory, Ask is Gemma, on the phone itself.",
                        f'"How is my {SURYA} going?" gets an answer from the student\'s own practice.'), b_ask, 10.0, 8.0,
         steps=ask_steps),
    Beat("privacy", "Privacy", ("The intake and the practice go to the teacher's Google Sheet.",
                                "The Gemma chat and health notes stay on the phone, unless the student shares a note.",
                                "On the Sheet's dashboard, the intake shows only as counts."), b_privacy, 12.0, 12.6),
    Beat("end", "", (), b_end, 3.0, 2.0),
)


# ---------- timing, frames, sound ----------

PLAN: list[mv.Placed] = []


def curly(word: str) -> str:
    """A word as the captions print it: typographic quotes and apostrophes."""
    word = re.sub(r'^"', "“", word)
    word = re.sub(r'"(?=[^\w]*$)', "”", word)
    return word.replace("'", "’")


def picture_at(k: int, t: float) -> Image.Image:
    """Beat k's picture at its time t, in its colour or the muted "before"."""
    beat = PLAN[k].scene
    return chrome.mute(beat.draw(t), beat.muted(t))


def compose(index: int) -> tuple:
    """Frame `index` and whether it is mid-change between beats."""
    t_total = index / FPS
    total = PLAN[-1].start + PLAN[-1].seconds
    k = max(i for i, p in enumerate(PLAN) if p.start <= t_total)
    placed, t = PLAN[k], t_total - PLAN[k].start
    layout.reset()
    picture = picture_at(k, t)
    changing = k > 0 and t < CHANGE
    if changing:
        items, problems = list(layout.ITEMS), list(layout.PROBLEMS)
        layout.reset()
        before = picture_at(k - 1, PLAN[k - 1].seconds)
        a_point, b_point = placed.scene.enter or ((W / 2, VIEW_H / 2), (W / 2, VIEW_H / 2))
        p = t / CHANGE
        zoom, old_on, scale, new_on = camera.stages(p, bool(placed.scene.enter))
        # Only the picture on screen counts, its elements moved with it; the old one is gone before the new one shows.
        seen = [(i, a_point, zoom) for i in layout.ITEMS] if old_on > 0 else [(i, b_point, scale) for i in items]
        layout.ITEMS[:] = [layout.Item(i.name, i.kind, camera.scaled(i.box, at, s), i.owner,
                                       camera.scaled(i.container, at, s) if i.container else None, round(i.size * s),
                                       abs(s - 1) > 0.001)
                           for i, at, s in seen]
        layout.PROBLEMS[:] = layout.PROBLEMS if old_on > 0 else problems
        picture = camera.change(before, a_point, picture, b_point, p, CREAM, bool(placed.scene.enter))
    words, fade = mv.spoken(placed, t, gaps=True)
    chrome.caption_bar(picture, [(curly(w), s) for w, s in words], CHAPTERS, placed.scene.chapter, t_total / total, fade)
    return picture, changing


FAILURES = CHECKS / "layout_failures.txt"  # the layout check's failures as the film is drawn, one line each


def frame(index: int) -> bytes:
    """Frame `index` as RGB bytes, the layout check run on it as it is drawn (its failures added to FAILURES)."""
    picture, changing = compose(index)
    found = failures(index, changing)
    if found:
        with open(FAILURES, "a") as out:
            out.write("\n".join(found) + "\n")
    return picture.tobytes()


def film() -> None:
    """The film, checked frame by frame as it is drawn, then the QA frames."""
    total = PLAN[-1].start + PLAN[-1].seconds
    mv.WORK.mkdir(parents=True, exist_ok=True)
    CHECKS.mkdir(parents=True, exist_ok=True)
    FAILURES.write_text("")
    picture, sound = mv.WORK / "film_picture.mp4", mv.WORK / "film_sound.wav"
    mv.render_picture(picture, int(total * FPS), frame)
    mv.soundtrack(sound, total, PLAN, music=lambda seconds: music.music(seconds, (0.05, PLAN[-1].start + 0.1)), volume=0.1)
    mv.mux(picture, sound, total, FILM, FILM.with_name(FILM.name.replace("_1080p", "_720p")))
    captions = FILM.with_name(FILM.stem.replace("_1080p", "") + ".srt")
    mv.subtitles(captions, PLAN)
    captions.write_text("\n".join(" ".join(curly(w) for w in row.split(" ")) for row in captions.read_text().split("\n")))
    print(f"wrote {FILM}: {total:.1f} s", flush=True)
    found = [line for line in FAILURES.read_text().split("\n") if line]
    print("\n".join(sorted(found)) if found else "layout check: no failures", flush=True)
    print(f"layout check: {len(found)} failures in {int(total * FPS)} frames (every frame, as drawn)", flush=True)
    qa_frames()


# ---------- checks: the layout check, QA frames, the storyboard ----------


def check_frame(index: int) -> list:
    """The layout check's failures at frame `index`, changes between beats included."""
    _, changing = compose(index)
    return failures(index, changing)


def failures(index: int, changing: bool) -> list:
    """The layout check's failures for the frame just composed."""
    k = max(i for i, p in enumerate(PLAN) if p.start <= index / FPS)
    tiny = [i for i in layout.ITEMS if changing and i.kind == "text" and i.size < layout.SMALLEST]
    layout.ITEMS[:] = [i for i in layout.ITEMS if i not in tiny]  # shrinking mid-zoom, not a size the film settles on
    return [f"{index / FPS:6.2f} s  {PLAN[k].scene.key}: {f}" for f in layout.check((W, H), VIEW_H)]


def qa_moments(k: int) -> list:
    """Beat k's QA frames, in beat time: its start (just after the change), middle and end, each line as it starts,
    and each step once its callout has settled."""
    placed = PLAN[k]
    start = CHANGE + 0.1 if k else 0.5
    moments = {start, (start + placed.seconds) / 2, placed.seconds - 0.05, *(s + 0.7 for s in placed.line_starts[1:])}
    if placed.scene.steps:
        steps = placed.scene.steps()
        for i, step in enumerate(steps):
            end = steps[i + 1].start if i + 1 < len(steps) else placed.seconds
            moments.add(min(step.start + 1.0, (step.start + end) / 2) if end - step.start < 2.0 else step.start + 1.0)
    return sorted(m for m in moments if 0 <= m < placed.seconds)


def qa() -> int:
    """The layout check on every frame, then the QA frames."""
    total = PLAN[-1].start + PLAN[-1].seconds
    frames = int(total * FPS)
    with multiprocessing.Pool(mv.workers()) as pool:
        found = [f for each in pool.map(check_frame, range(frames), chunksize=8) for f in each]
    print("\n".join(found) if found else "layout check: no failures", flush=True)
    print(f"layout check: {len(found)} failures in {frames} frames (every frame)", flush=True)
    qa_frames()
    return len(found)


def qa_frames() -> None:
    """A frame as each beat starts, at its middle and end, as each line starts and as each step settles."""
    folder_ = CHECKS / "qa"
    folder_.mkdir(parents=True, exist_ok=True)
    for old in folder_.glob("*.png"):
        old.unlink()
    for k, placed in enumerate(PLAN):
        for at in qa_moments(k):
            t = placed.start + at
            picture, _ = compose(int(t * FPS))
            picture.save(folder_ / f"{k + 1:02d}_{placed.scene.key}_{t:06.2f}s.png")
    print(f"QA frames in {folder_}", flush=True)


def storyboard() -> None:
    folder_ = CHECKS / "storyboard"
    folder_.mkdir(parents=True, exist_ok=True)
    for old in folder_.glob("*.png"):
        old.unlink()
    thumbs, rows = [], []
    for k, placed in enumerate(PLAN):
        picture, _ = compose(int((placed.start + placed.scene.still) * FPS))
        picture.save(folder_ / f"{k + 1:02d}_{placed.scene.key}.png")
        thumbs.append(picture.resize((640, 360), Image.LANCZOS))
        lines = " / ".join(mv.caption(line) for line in placed.scene.lines) or "(no line)"
        rows.append(f"{k + 1:2d}  {placed.start:6.2f}-{placed.start + placed.seconds:6.2f} s  {placed.scene.chapter or '-':15s}"
                    f"{placed.scene.key:14s} {lines}")
    sheet = Image.new("RGB", (3 * 640, ((len(thumbs) + 2) // 3) * 360), "white")
    for k, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((k % 3) * 640, (k // 3) * 360))
    sheet.save(CHECKS / "storyboard_sheet.png")
    (CHECKS / "beats.txt").write_text("\n".join(rows) + "\n")
    print("\n".join(rows))
    print(f"{len(thumbs)} frames in {folder_}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--qa", action="store_true", help="the layout check on every frame, and QA frames")
    parser.add_argument("--storyboard", action="store_true", help="a frame per beat, with its line")
    args = parser.parse_args()
    PLAN.extend(mv.timeline(BEATS, LEAD, GAP, TAIL))
    print(f"{len(PLAN)} beats, {PLAN[-1].start + PLAN[-1].seconds:.1f} s", flush=True)
    if args.qa:
        raise SystemExit(1 if qa() else 0)
    if args.storyboard:
        storyboard()
    else:
        film()


if __name__ == "__main__":
    main()
