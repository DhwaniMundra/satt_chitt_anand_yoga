"""The world the class lives in: a dotted map centred on India, the homes with their local time at a moment (the
Intermediate batch's 8:00 IST class by default), arcs between them, things travelling along the arcs, and day and
night.

Land is Natural Earth's 110m land (public domain), fetched once into tools/natural-earth/."""

import functools
import json
import math
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
from matplotlib.path import Path as Outline
from PIL import ImageDraw

from .chrome import VIEW_H, W, tint
from .layout import hits

ROOT = Path(__file__).resolve().parents[2]
LAND = ROOT / "tools" / "natural-earth" / "ne_110m_land.geojson"
LAND_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_land.geojson"
CENTRE = 120.0  # the overview's middle meridian: the Americas stay whole on the right, across the Pacific
CLASS_AT = datetime(2026, 11, 19, 8, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
SIZE = (W, VIEW_H)  # the map fills the picture above the caption bar


@dataclass(frozen=True)
class Place:
    name: str
    lon: float
    lat: float
    zone: str

    def time(self, moment: datetime = CLASS_AT) -> str:
        """`moment` (the class's start unless given) in this place's own time, e.g. "Wed 6:30 PM"."""
        local = moment.astimezone(ZoneInfo(self.zone))
        return local.strftime("%a ") + local.strftime("%I:%M %p").lstrip("0")

    def clock(self, moment: datetime) -> str:
        """`moment` as this place's phones show it in the status bar, e.g. "1:28"."""
        return moment.astimezone(ZoneInfo(self.zone)).strftime("%I:%M").lstrip("0")

    def hour(self, moment: datetime = CLASS_AT) -> float:
        local = moment.astimezone(ZoneInfo(self.zone))
        return local.hour + local.minute / 60


# The teacher in India; the Intermediate batch's students spread round the world, where 8:00 in India is a sensible
# hour; and a new student in Kolkata, who joins the Pain management batch (5:30 PM in India, Mon, Wed and Fri).
PLACES = {
    "teacher": Place("India", 74.0, 19.0, "Asia/Kolkata"),
    "kolkata": Place("Kolkata", 88.4, 22.6, "Asia/Kolkata"),
    "dubai": Place("Dubai", 55.3, 25.2, "Asia/Dubai"),
    "sydney": Place("Sydney", 151.2, -33.9, "Australia/Sydney"),
    "california": Place("California", -122.0, 37.5, "America/Los_Angeles"),
}


@functools.lru_cache(maxsize=1)
def land_dots(step: float = 2.0) -> np.ndarray:
    """Longitude and latitude of a grid of points on land, `step` degrees apart (cached next to the land file)."""
    cache = LAND.with_suffix(f".dots{step}.npy")
    if cache.exists():
        return np.load(cache)
    if not LAND.exists():
        LAND.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(LAND_URL, headers={"User-Agent": "map-fetch"})
        LAND.write_bytes(urllib.request.urlopen(request, timeout=60).read())
    lon, lat = np.meshgrid(np.arange(-180 + step / 2, 180, step), np.arange(-58 + step / 2, 78, step))
    grid = np.stack([lon.ravel(), lat.ravel()], axis=1)
    on_land = np.zeros(len(grid), bool)
    for feature in json.loads(LAND.read_text())["features"]:
        geometry = feature["geometry"]
        polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
        for polygon in polygons:
            on_land |= Outline(polygon[0]).contains_points(grid)
    np.save(cache, grid[on_land])
    return grid[on_land]


@dataclass(frozen=True)
class View:
    """The camera on the map: its centre (degrees east of CENTRE, degrees of latitude) and pixels per degree. The
    world wraps round the camera, so any place can be in the middle."""

    u: float = 0.0
    lat: float = 14.0
    scale: float = 5.6

    def xy(self, lon: float, lat: float, size: tuple = SIZE) -> tuple:
        u = (lon - CENTRE - self.u + 180) % 360 - 180
        return size[0] / 2 + u * self.scale, size[1] / 2 - (lat - self.lat) * self.scale


def draw_map(draw: ImageDraw.ImageDraw, view: View, day: tuple, night: tuple, sun: float | None = None) -> None:
    """Land as a fine grid of dots (a degree apart, half a degree zoomed in, so the coasts read); with `sun` (the
    longitude under the sun), the night side in `night`, shading into the day over about 36 degrees (200 px at the
    world's scale), so the line between them never shows as an edge."""
    step = 1.0 if view.scale < 10 else 0.5  # zoomed in on a country, a finer grid
    radius = max(0.9, view.scale * 0.2 * step)
    for lon, lat in land_dots(step):
        x, y = view.xy(lon, lat)
        if -4 < x < SIZE[0] + 4 and -4 < y < SIZE[1] + 4:
            color = day
            if sun is not None:
                p = min(max((0.31 - math.cos(math.radians(lon - sun))) / 0.62, 0.0), 1.0)
                p = p * p * (3 - 2 * p)
                color = tuple(round(d + (n - d) * p) for d, n in zip(day, night, strict=True))
            if lat > 60:  # the land grid stops at 78 degrees north: fade it out above 60, so it has no edge
                color = tint(color, (78 - lat) / 18)
            draw.ellipse([x - radius, y - radius, x + radius, y + radius], fill=color)


PIN_R, PIN_UP = 15, 34  # a pin's head radius, and how far its head's centre sits above its tip
FLYER = (34, 18)  # half the largest thing that flies along an arc


def head(view: View, key: str, size: tuple) -> tuple:
    """Where a home's pin head is: above the city, which the pin's tip marks."""
    x, y = view.xy(PLACES[key].lon, PLACES[key].lat, size)
    return x, y - PIN_UP


def arc(view: View, a: str, b: str, steps: int = 48, size: tuple = SIZE) -> list:
    """Points on a curve from place a's pin head to place b's, bowed upwards."""
    (x0, y0), (x1, y1) = head(view, a, size), head(view, b, size)
    lift = 0.28 * math.hypot(x1 - x0, y1 - y0)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2 - lift
    return [((1 - s) ** 2 * x0 + 2 * (1 - s) * s * cx + s * s * x1, (1 - s) ** 2 * y0 + 2 * (1 - s) * s * cy + s * s * y1)
            for s in (k / steps for k in range(steps + 1))]


def at_distance(points: list, d: float) -> tuple:
    """The point `d` pixels along a polyline (clamped to its ends)."""
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        step = math.hypot(x1 - x0, y1 - y0)
        if d <= step:
            f = d / step if step else 0.0
            return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f
        d -= step
    return points[-1]


def length(points: list) -> float:
    return sum(math.hypot(x1 - x0, y1 - y0) for (x0, y0), (x1, y1) in zip(points, points[1:]))


def draw_arc(draw: ImageDraw.ImageDraw, points: list, drawn: float, color: tuple) -> None:
    """The first `drawn` fraction of the arc, as a line of short dashes."""
    end = max(0, round(drawn * (len(points) - 1)))
    for k in range(0, end, 2):
        draw.line([points[k], points[k + 1]], fill=color, width=3)


def pin_box(x: float, y: float) -> tuple:
    return x - PIN_R - 3, y - PIN_UP - PIN_R - 3, x + PIN_R + 3, y + 2


def pin_distance(point: tuple, x: float, y: float) -> float:
    """How far `point` is from the pin whose tip is at (x, y): from the nearest point between its head and its tip."""
    px, py = point
    nearest_y = min(max(py, y - PIN_UP), y)
    return math.hypot(px - x, py - nearest_y)


def leader(box: tuple, x: float, y: float) -> tuple:
    """A leader line from the pin at (x, y) to its label at `box`: from the tip when the label is below it, else from
    the edge of the head; it ends at the label's nearest point. Returns (start, end)."""
    left, top, right, bottom = box
    if top >= y:
        return (x, y + 3), (min(max(x, left), right), top)
    hx, hy = x, y - PIN_UP
    lx, ly = min(max(hx, left), right), min(max(hy, top), bottom)
    d = math.hypot(lx - hx, ly - hy) or 1
    return (hx + (lx - hx) * (PIN_R + 3) / d, hy + (ly - hy) * (PIN_R + 3) / d), (lx, ly)


def anchor(box: tuple, x: float, y: float, led: bool) -> tuple:
    """Where a label is read as belonging: its leader's end, or its middle when it sits by its pin without one."""
    return leader(box, x, y)[1] if led else ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def misread(view: "View", size: tuple, key: str, box: tuple, led: bool, keys: tuple = tuple(PLACES)) -> str:
    """The other place of `keys` a label at `box` would be read as belonging to (its anchor nearer that place's pin), or
    ""."""
    spots = {k: view.xy(PLACES[k].lon, PLACES[k].lat, size) for k in keys}
    point = anchor(box, *spots[key], led)
    own = pin_distance(point, *spots[key])
    return next((k for k, s in spots.items() if k != key and pin_distance(point, *s) <= own), "")


# Land a label must not cover, (west, north, east, south) in degrees: India's peninsula, where the teacher's pin is.
KEEP_CLEAR = ((72.4, 21.0, 81.0, 7.4),)


def draw_home(draw: ImageDraw.ImageDraw, x: float, y: float, color: tuple, edge: tuple, house: tuple) -> tuple:
    """A home as a pin: its tip on the city, its head above in its person's colour with a small house in it, outlined
    thinly so it stands out from the dots without covering the land around it. Returns its box."""
    hx, hy = x, y - PIN_UP
    stem = [(hx - PIN_R * 0.62, hy + PIN_R * 0.78), (x, y), (hx + PIN_R * 0.62, hy + PIN_R * 0.78)]
    draw.polygon(stem, fill=color, outline=edge)
    draw.ellipse([hx - PIN_R - 2, hy - PIN_R - 2, hx + PIN_R + 2, hy + PIN_R + 2], fill=edge)
    draw.ellipse([hx - PIN_R, hy - PIN_R, hx + PIN_R, hy + PIN_R], fill=color)
    s = PIN_R * 0.5
    draw.rectangle([hx - s * 0.8, hy - s * 0.1, hx + s * 0.8, hy + s * 0.9], fill=house)
    draw.polygon([(hx - s * 1.15, hy - s * 0.1), (hx, hy - s * 1.05), (hx + s * 1.15, hy - s * 0.1)], fill=house)
    return pin_box(x, y)


def place_labels(view: View, size: tuple, keys: tuple, widths: dict, height: float, area: tuple) -> dict:
    """Where each home's label goes: beside its pin on a free side, or further out with a leader line, never on
    another label, a pin, or an arc (where things fly, FLYER being half the largest flying thing). `widths` are the
    labels' widths; returns, per key, the label's box and whether it needs a leader line."""
    spots = {k: view.xy(PLACES[k].lon, PLACES[k].lat, size) for k in keys}
    blocked = [pin_box(x, y) for x, y in spots.values()]
    for west, north, east, south in KEEP_CLEAR:
        blocked.append((*view.xy(west, north, size), *view.xy(east, south, size)))
    for k in keys:
        if k != "teacher" and "teacher" in keys:
            for px, py in arc(view, "teacher", k, 48, size)[3:-3]:
                blocked.append((px - FLYER[0], py - FLYER[1], px + FLYER[0], py + FLYER[1]))
    placed = {}
    for k in sorted(keys, key=lambda k: k != "teacher"):
        x, y = spots[k]
        w = widths[k]
        top, bottom, side = y - PIN_UP - PIN_R, y, PIN_R + 12  # the pin's extent
        candidates = [(left, top_, far) for far in (0, 40, 80) for left, top_ in (
            (x - w / 2, bottom + 10 + far), (x - w / 2, top - 10 - height - far),  # below, above
            (x + side + far, y - PIN_UP - height / 2), (x - side - far - w, y - PIN_UP - height / 2),  # right, left
            (x + side + far, bottom + 6 + far / 2), (x - side - far - w, bottom + 6 + far / 2),  # below right, left
            (x + side + far, top - height - far / 2), (x - side - far - w, top - height - far / 2))]  # above right, left
        for left, top_, far in candidates:
            box = (left, top_, left + w, top_ + height)
            fits = box[0] >= area[0] and box[1] >= area[1] and box[2] <= area[2] and box[3] <= area[3]
            if fits and not any(hits(box, b, 6) for b in blocked) and not misread(view, size, k, box, far > 0, keys):
                placed[k] = (box, far > 0)
                blocked.append(box)
                break
    return placed

