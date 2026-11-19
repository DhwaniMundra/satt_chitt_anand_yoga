"""Every frame's drawn elements and their boxes, and the check that fails when they collide.

Drawing code registers what it draws: text, label pills, chips, markers, icons, phone frames, highlight boxes and the
caption bar. `check()` then applies the film's rules:

- no two text or label boxes intersect (a text and the pill it sits in belong together);
- no text or label sits on a marker, icon or phone it doesn't belong to;
- text stays inside its container and inside the safe area (48 px from every edge);
- nothing but the caption bar's own text sits on the caption bar;
- no text is smaller than 22 px;
- a highlight box never cuts through a row of text on a phone screen (the drawing code reports this itself);
- nothing flying along an arc covers a home;
- no label straddles the edge of a panel (it is wholly inside or wholly outside);
- the caption's lowest glyph is at least CAPTION_GAP above the chapter row (measured on the drawn glyphs).

Text registers whatever its opacity, and during a change between beats the picture on screen registers where the
camera has moved it (make_advert.compose), so the check runs on every frame. Mid-zoom, an element carried by the camera
may run off the edge or under the caption bar, which is drawn opaquely on top; it is still checked against everything
else that moves with it.
"""

from dataclasses import dataclass

from PIL import ImageDraw, ImageFont

SAFE = 48
SMALLEST = 22
CAPTION_GAP = 28


@dataclass
class Item:
    name: str
    kind: str  # text, label, marker, icon, phone, highlight, bar
    box: tuple
    owner: str = ""  # what it belongs to: a text's pill, a label's marker
    container: tuple | None = None
    size: int = 0
    moving: bool = False  # carried by the camera mid-zoom, under the overlay drawn on top of it


ITEMS: list[Item] = []
PROBLEMS: list[str] = []  # failures found while drawing (a highlight cutting text)


def reset() -> None:
    ITEMS.clear()
    PROBLEMS.clear()


def add(name: str, kind: str, box: tuple, owner: str = "", container: tuple | None = None, size: int = 0) -> tuple:
    ITEMS.append(Item(name, kind, box, owner, container, size))
    return box


def text(draw: ImageDraw.ImageDraw, xy: tuple, words: str, face: ImageFont.FreeTypeFont, fill: tuple, anchor: str = "la",
         name: str = "", owner: str = "", container: tuple | None = None) -> tuple:
    """Draws text and registers its box."""
    draw.text(xy, words, font=face, fill=fill, anchor=anchor)
    box = draw.textbbox(xy, words, font=face, anchor=anchor)
    add(name or words[:24], "text", box, owner, container, round(face.size))
    return box


def problem(message: str) -> None:
    PROBLEMS.append(message)


def hits(a: tuple, b: tuple, pad: float = 0.0) -> bool:
    return a[0] < b[2] + pad and b[0] < a[2] + pad and a[1] < b[3] + pad and b[1] < a[3] + pad


def inside(a: tuple, b: tuple, slack: float = 1.0) -> bool:
    return a[0] >= b[0] - slack and a[1] >= b[1] - slack and a[2] <= b[2] + slack and a[3] <= b[3] + slack


def check(size: tuple, bar_top: float) -> list[str]:
    """The rules above, as a list of failures (empty when the frame is clean)."""
    w, h = size
    safe = (SAFE, SAFE, w - SAFE, h - SAFE)
    out = list(PROBLEMS)
    texts = [i for i in ITEMS if i.kind in ("text", "label")]
    for k, a in enumerate(texts):
        for b in texts[k + 1:]:
            related = a.owner == b.name or b.owner == a.name or (a.owner and a.owner == b.owner)
            under = a.moving != b.moving  # one carried by the zoom under the other, drawn on top
            if hits(a.box, b.box) and not related and not under:
                out.append(f"{a.kind} '{a.name}' overlaps {b.kind} '{b.name}'")
        for other in ITEMS:
            if other.kind in ("marker", "icon", "phone") and other.name != a.owner and a.moving == other.moving \
                    and hits(a.box, other.box):
                out.append(f"{a.kind} '{a.name}' overlaps {other.kind} '{other.name}'")
        if a.container and not inside(a.box, a.container):
            out.append(f"{a.kind} '{a.name}' runs outside its container")
        if not a.moving and not inside(a.box, safe):
            out.append(f"{a.kind} '{a.name}' outside the safe area {tuple(round(v) for v in a.box)}")
        if not a.moving and a.owner != "bar" and a.box[3] > bar_top:
            out.append(f"{a.kind} '{a.name}' sits on the caption bar")
        if a.kind == "text" and a.size and a.size < SMALLEST:
            out.append(f"text '{a.name}' is {a.size} px")
    for icon in (i for i in ITEMS if i.kind == "icon" and i.name.startswith("flying")):
        for home in (i for i in ITEMS if i.kind == "marker"):
            if hits(icon.box, home.box):
                out.append(f"'{icon.name}' covers '{home.name}'")
    for panel in (i for i in ITEMS if i.kind == "panel"):
        for a in texts:
            if not a.moving and a.owner != panel.name and hits(a.box, panel.box) and not inside(a.box, panel.box):
                out.append(f"{a.kind} '{a.name}' straddles the edge of '{panel.name}'")
    captions = [i.box[3] for i in ITEMS if i.name.startswith("caption")]
    chapters = [i.box[1] for i in ITEMS if i.name.startswith("chapter")]
    if captions and chapters and min(chapters) - max(captions) < CAPTION_GAP:
        out.append(f"the caption is {min(chapters) - max(captions):.0f} px above the chapters (at least {CAPTION_GAP})")
    return out
