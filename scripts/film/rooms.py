"""Each person's home: a simple room with a window lit for their local hour, a mat, a plant, and their phone on a
stool. The class itself is the same rooms side by side, as in a Meet grid."""

from dataclasses import dataclass

from PIL import Image, ImageDraw

from make_video import MOSS, MOSS_LIGHT, PAPER, SAFFRON, SAFFRON_LIGHT
from . import figures
from .world import PLACES


@dataclass(frozen=True)
class Home:
    place: str  # a key of world.PLACES
    person: figures.Person
    wall: tuple
    mat: tuple
    window: float = 0.56  # the window's left edge, as a fraction of the room's width (clear of a label at top left)
    plant: float = 0.86  # the plant's centre


PEOPLE = {
    "teacher": Home("teacher", figures.Person("Teacher", SAFFRON, (190, 140, 100)), (241, 229, 212), SAFFRON_LIGHT, 0.6, 0.12),
    "dubai": Home("dubai", figures.Person("Dubai", MOSS, (176, 124, 88), lag=0.2, offsets=(0, 2, 6, 4, -5, -3, 0, 0, 3, 0, 0)),
                  (236, 231, 221), MOSS_LIGHT),
    "sydney": Home("sydney", figures.Person("Sydney", (120, 146, 118), (222, 182, 146), hair=(30, 26, 24), lag=0.3,
                                                  offsets=(-3, -2, -4, -6, 4, 6, 2, 0, -4, 3, 0)), (231, 236, 227), MOSS_LIGHT, 0.52, 0.12),
    "california": Home("california", figures.Person("California", (150, 96, 60), (150, 104, 74), hair=(84, 62, 44), lag=0.12,
                                                    offsets=(2, 0, 3, -2, -2, 2, -2, 0, 2, -2, 0)), (240, 227, 222), MOSS_LIGHT),
    "kolkata": Home("kolkata", figures.Person("Kolkata", (96, 110, 150), (196, 150, 112), hair=(40, 32, 30)), (236, 232, 240),
                    MOSS_LIGHT, 0.56, 0.12),
}
STUDENTS = ("dubai", "sydney", "california")


def sky(hour: float) -> tuple:
    """The window's colour at a local hour: dawn, day, dusk or night."""
    if 5 <= hour < 7.5:
        return (247, 214, 186)
    if 7.5 <= hour < 17:
        return (206, 225, 233)
    if 17 <= hour < 19.5:
        return (234, 176, 146)
    return (66, 76, 98)


def draw_room(canvas: Image.Image, box: tuple, home: Home, angles: tuple, figure: float = 0.5,
              hour: float | None = None) -> dict:
    """The room in `box` (left, top, right, bottom) with its person in pose `angles`, `figure` of the room's height
    tall, its window lit for the local `hour` (the class's, unless given); returns where the person's joints are."""
    draw = ImageDraw.Draw(canvas)
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    floor = y0 + 0.7 * h
    draw.rectangle([x0, y0, x1, floor], fill=home.wall)
    draw.rectangle([x0, floor, x1, y1], fill=(222, 202, 174))
    draw.rectangle([x0, floor, x1, floor + 0.012 * h], fill=(204, 180, 150))
    wx = x0 + home.window * w
    window = sky(PLACES[home.place].hour() if hour is None else hour)
    draw.rounded_rectangle([wx, y0 + 0.12 * h, wx + 0.26 * w, y0 + 0.5 * h], round(0.02 * w), fill=window, outline=PAPER,
                           width=max(2, round(0.012 * w)))
    draw.line([(wx + 0.13 * w, y0 + 0.12 * h), (wx + 0.13 * w, y0 + 0.5 * h)], fill=PAPER, width=max(2, round(0.008 * w)))
    px = x0 + home.plant * w
    draw.polygon([(px - 0.035 * w, floor - 0.1 * h), (px + 0.035 * w, floor - 0.1 * h), (px + 0.025 * w, floor),
                  (px - 0.025 * w, floor)], fill=(176, 120, 84))
    for dx, dy, r in ((-0.03, -0.2, 0.05), (0.03, -0.24, 0.055), (0.0, -0.3, 0.05)):
        cx, cy, rr = px + dx * w, floor + dy * h, r * h
        draw.ellipse([cx - rr * 0.7, cy - rr, cx + rr * 0.7, cy + rr], fill=MOSS)
    mat_y = y0 + 0.86 * h
    draw.rounded_rectangle([x0 + 0.2 * w, mat_y, x0 + 0.7 * w, mat_y + 0.03 * h], round(0.015 * h), fill=home.mat)
    joints = figures.draw_figure(draw, home.person, angles, x0 + 0.45 * w, mat_y + 0.005 * h, figure * h)
    # The phone, upright on a stool beside the mat.
    sx = x0 + 0.8 * w
    draw.rounded_rectangle([sx - 0.06 * w, mat_y - 0.07 * h, sx + 0.06 * w, mat_y + 0.03 * h], round(0.01 * w), fill=(176, 140, 104))
    pw, ph = 0.045 * h, 0.1 * h
    draw.rounded_rectangle((sx - pw / 2, mat_y - 0.07 * h - ph, sx + pw / 2, mat_y - 0.07 * h), round(0.012 * h), fill=(31, 31, 28))
    return joints


def grid_boxes(area: tuple, gap: int = 18) -> dict:
    """Four tiles in two rows inside `area`: the teacher first, as in a call."""
    x0, y0, x1, y1 = area
    tw, th = (x1 - x0 - gap) / 2, (y1 - y0 - gap) / 2
    keys = ("teacher",) + STUDENTS
    return {k: (x0 + (i % 2) * (tw + gap), y0 + (i // 2) * (th + gap), x0 + (i % 2) * (tw + gap) + tw,
                y0 + (i // 2) * (th + gap) + th) for i, k in enumerate(keys)}
