"""The camera's moves between pictures: zooming through a point of one picture into the next (world to home to
phone), or a plain change. Either way the old picture is gone before the new one shows, through the background, so
two pictures' words are never on screen at once."""

from PIL import Image

from .figures import ease


def zoom_into(image: Image.Image, point: tuple, k: float) -> Image.Image:
    """`image` magnified k times about `point`, which stays where it is."""
    if k <= 1.001:
        return image
    w, h = image.size
    x, y = point
    box = (x - x / k, y - y / k, x + (w - x) / k, y + (h - y) / k)
    return image.resize((w, h), Image.BILINEAR, box=box)


def shrink_onto(image: Image.Image, point: tuple, s: float, background: tuple) -> Image.Image:
    """`image` at scale s about `point`, on `background`."""
    if s >= 0.999:
        return image
    w, h = image.size
    small = image.resize((max(1, round(w * s)), max(1, round(h * s))), Image.BILINEAR)
    canvas = Image.new(image.mode, (w, h), background)
    canvas.paste(small, (round(point[0] - point[0] * s), round(point[1] - point[1] * s)))
    return canvas


def stages(p: float, zoom: bool) -> tuple:
    """At p (0 to 1) through a change: the old picture's scale and opacity, then the new one's. The old one fades out
    over the first half and the new one in over the second."""
    q = ease(p)
    old_on, new_on = 1 - ease(p / 0.5), ease((p - 0.5) / 0.5)
    return (1 + 5 * q, old_on, 0.2 + 0.8 * q, new_on) if zoom else (1.0, old_on, 1.0, new_on)


def change(a: Image.Image, a_point: tuple, b: Image.Image, b_point: tuple, p: float, background: tuple,
           zoom: bool = True) -> Image.Image:
    """From picture a to picture b at p: with `zoom`, a grows about a_point (a home, a phone) and b grows out of
    b_point; without, a plain change. Run p from 1 to 0 to zoom back out."""
    k, a_on, s, b_on = stages(p, zoom)
    blank = Image.new(a.mode, a.size, background)
    if a_on > 0:
        return Image.blend(blank, zoom_into(a, a_point, k), a_on)
    return Image.blend(blank, shrink_onto(b, b_point, s, background), b_on)


def scaled(box: tuple, point: tuple, k: float) -> tuple:
    """Where a box ends up when its picture is scaled k times about `point`."""
    return tuple(point[i % 2] + (v - point[i % 2]) * k for i, v in enumerate(box))
