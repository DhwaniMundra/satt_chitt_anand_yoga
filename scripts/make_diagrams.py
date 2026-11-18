"""Draws the README's diagrams with matplotlib, in the app's colours: a morning with the app (student, teacher and
what happens behind the scenes, after a service blueprint), how it works, and how it was made in rounds.
Writes docs/media/diagrams/*.png. They carry no titles: the README's headings name them.

Usage: tools/media-venv/bin/python scripts/make_diagrams.py
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "media" / "diagrams"
FONTS = ROOT / "tools" / "fonts"
CREAM, PAPER, LINE = "#F6F1E7", "#FFFCF6", "#E5DDCF"
MOSS, MOSS_LIGHT, SAFFRON, SAFFRON_LIGHT, INK, MUTED = "#3F5B45", "#DDE6D8", "#C26A2D", "#F6E0CC", "#2B2A26", "#6E6A60"


def sora(weight: int) -> Path:
    """A static instance of the variable Sora font at `weight`, made once with fontTools (matplotlib cannot pick a
    weight from a variable font)."""
    path = FONTS / f"Sora-{weight}.ttf"
    if not path.exists():
        from fontTools.ttLib import TTFont
        from fontTools.varLib.instancer import instantiateVariableFont

        instantiateVariableFont(TTFont(FONTS / "Sora.ttf"), {"wght": weight}).save(path)
    return path


REGULAR, SEMI, BOLD = (FontProperties(fname=sora(w)) for w in (400, 600, 700))
SERIF = FontProperties(fname="/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")


def canvas(width: float, height: float):
    """A figure in inches with axes in the same units, origin at the bottom left."""
    fig = plt.figure(figsize=(width, height), dpi=200, facecolor=CREAM)
    ax = fig.add_axes((0, 0, 1, 1))
    ax.set_xlim(0, width)
    ax.set_ylim(0, height)
    ax.axis("off")
    return fig, ax


def card(ax, x, y, w, h, title="", lines=(), fill=PAPER, edge=LINE, title_color=MOSS, size=11, title_size=12.5, center=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.12", fc=fill, ec=edge, lw=1.4))
    tx = x + w / 2 if center else x + 0.16
    align = "center" if center else "left"
    top = y + h - 0.2
    if title:
        ax.text(tx, top, title, fontproperties=BOLD, fontsize=title_size, color=title_color, ha=align, va="top")
        top -= 0.33
    for i, line in enumerate(lines):
        ax.text(tx, top - i * 0.27, line, fontproperties=REGULAR, fontsize=size, color=INK, ha=align, va="top")


def arrow(ax, start, end, color=MUTED, rad=0.0, style="-|>", lw=1.6, dashed=False):
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=14, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=(0, (4, 3)) if dashed else "solid",
                                 shrinkA=2, shrinkB=2))


def save(fig, name: str, border: int = 40) -> None:
    """Saves the figure, then trims the empty cream margins to an even `border` (matplotlib's tight crop counts the
    invisible axes)."""
    import numpy as np
    from PIL import Image

    path = OUT / f"{name}.png"
    fig.savefig(path, facecolor=CREAM)
    plt.close(fig)
    image = Image.open(path).convert("RGB")
    pixels = np.asarray(image).astype(int)
    used = np.abs(pixels - np.array([0xF6, 0xF1, 0xE7])).sum(axis=2) > 12
    rows, cols = np.where(used.any(axis=1))[0], np.where(used.any(axis=0))[0]
    box = (max(cols[0] - border, 0), max(rows[0] - border, 0), min(cols[-1] + border, image.width), min(rows[-1] + border, image.height))
    image.crop(box).save(path, optimize=True)


def journey() -> None:
    """A morning with the app: what the teacher and a student do, and what happens behind the scenes."""
    fig, ax = canvas(13, 6.2)
    columns = ("Before class", "Joining", "In class", "After class", "Any time")
    times = ("7:30", "7:58", "8:00", "8:55", "")
    lanes = (("Teacher", 3.75), ("Student", 2.25), ("Behind the\nscenes", 0.75))
    x0, colw, boxw, boxh = 1.75, 2.2, 2.0, 1.15
    for i, (name, t) in enumerate(zip(columns, times, strict=True)):
        cx = x0 + i * colw
        ax.text(cx + 0.02, 5.05, name.upper(), fontproperties=BOLD, fontsize=10.5, color=SAFFRON, va="center")
        if t:
            ax.text(cx + boxw - 0.02, 5.05, t, fontproperties=REGULAR, fontsize=10.5, color=MUTED, va="center", ha="right")
    for name, y in lanes:
        ax.add_patch(FancyBboxPatch((0.35, y - 0.12), 12.3, boxh + 0.24, boxstyle="round,pad=0,rounding_size=0.15",
                                    fc="#EFE8DA" if name != "Student" else "#E7EEE2", ec="none"))
        ax.text(0.5, y + boxh / 2, name, fontproperties=BOLD, fontsize=12, color=MOSS, va="center")
    ax.plot([0.45, 12.55], [1.98, 1.98], color=MUTED, lw=1, ls=(0, (2, 3)))
    ax.text(12.55, 2.02, "line of visibility", fontproperties=REGULAR, fontsize=8.5, color=MUTED, ha="right", va="bottom")

    def cell(col, lane_y, title, lines, accent=False):
        card(ax, x0 + col * colw, lane_y, boxw, boxh, title, lines, fill=SAFFRON_LIGHT if accent else PAPER,
             edge=SAFFRON if accent else LINE, title_color=SAFFRON if accent else MOSS, size=9.8, title_size=11)

    teacher, student, back = 3.75, 2.25, 0.75
    cell(0, teacher, "Posts the link", ("Pastes the Meet link,", "taps Save and share"))
    cell(2, teacher, "Teaches", ("live on Google Meet",))
    cell(4, teacher, "Sees how it went", ("who joined, and how", "they felt before / after"))
    cell(0, student, "Sees today's class", ("in the app, with", "a countdown"))
    cell(1, student, "Taps Join", ("one tap first:", "how do you feel?"), accent=True)
    cell(2, student, "Practises", ("with the class",))
    cell(3, student, "One tap again", ("how do you feel", "now?"), accent=True)
    cell(4, student, "Asks, breathes", ("questions, the breathing", "circle, own progress"))
    cell(0, back, "WhatsApp opens", ("message ready for", "the class group"))
    cell(1, back, "Google Meet opens", ("the check-in is", "saved on the laptop"))
    cell(3, back, "Asks on return", ("when the app comes", "back after class"))
    cell(4, back, "Gemma answers", ("from the studio's notes;", "emergencies: call 112"))
    mid = boxh / 2
    arrow(ax, (x0 + boxw, student + mid), (x0 + colw, student + mid), color=MOSS)
    arrow(ax, (x0 + colw + boxw / 2, student), (x0 + colw + boxw / 2, back + boxh), color=MOSS)
    arrow(ax, (x0 + 3 * colw + boxw, student + boxh * 0.8), (x0 + 4 * colw, teacher + 0.3), color=SAFFRON, rad=0.25)
    save(fig, "journey")


def how_it_works() -> None:
    fig, ax = canvas(13, 5.0)
    card(ax, 0.5, 2.15, 3.0, 1.6, "Phone", ("the Android app, for", "students and the teacher", "English · Hindi · Marathi"))
    card(ax, 0.5, 0.35, 1.4, 1.2, "WhatsApp", ("class group",), size=9.8, title_size=11)
    card(ax, 2.1, 0.35, 1.4, 1.2, "Google Meet", ("the class",), size=9.8, title_size=11)
    arrow(ax, (1.2, 2.15), (1.2, 1.55))
    arrow(ax, (2.8, 2.15), (2.8, 1.55))
    ax.text(0.62, 1.85, "share", fontproperties=REGULAR, fontsize=9, color=MUTED)
    ax.text(2.9, 1.85, "join", fontproperties=REGULAR, fontsize=9, color=MUTED)
    ax.add_patch(FancyBboxPatch((4.6, 0.35), 8.0, 3.85, boxstyle="round,pad=0,rounding_size=0.18", fc=MOSS_LIGHT, ec=MOSS, lw=1.4))
    ax.text(4.8, 4.0, "The studio's laptop", fontproperties=BOLD, fontsize=13, color=MOSS, va="top")
    card(ax, 4.85, 1.9, 2.35, 1.55, "Server", ("accounts, classes,", "check-ins"))
    card(ax, 7.45, 1.9, 2.35, 1.55, "Studio notes", ("yoga and health,", "readable, correctable"))
    card(ax, 10.05, 1.9, 2.35, 1.55, "Gemma 4", ("open AI model, on", "the graphics card"), fill=SAFFRON_LIGHT, edge=SAFFRON,
         title_color=SAFFRON)
    arrow(ax, (3.5, 2.95), (4.85, 2.95), color=MOSS, style="<|-|>")
    arrow(ax, (7.2, 2.67), (7.45, 2.67), color=MOSS)
    arrow(ax, (9.8, 2.67), (10.05, 2.67), color=MOSS)
    notes = ("Questions are kept only if the student agrees.", "Emergency signs skip the AI: a fixed reply, call 112.",
             "Optional: a private backup on GitHub.")
    for i, note in enumerate(notes):
        ax.text(4.9, 1.45 - i * 0.36, "•  " + note, fontproperties=REGULAR, fontsize=10.5, color=INK, va="top")
    save(fig, "how_it_works")


def rounds() -> None:
    fig, ax = canvas(13, 5.4)
    steps = ("Build", "Tour every screen\non the emulator", "Ask the assistant\nthe same questions", "Read every screen\nand every answer",
             "Fix, and add a test\nso it stays fixed")
    w, gap, y = 2.2, 0.32, 3.15
    for i, step in enumerate(steps):
        x = 0.5 + i * (w + gap)
        accent = i == 3
        ax.add_patch(FancyBboxPatch((x, y), w, 0.95, boxstyle="round,pad=0,rounding_size=0.45",
                                    fc=SAFFRON_LIGHT if accent else PAPER, ec=SAFFRON if accent else LINE, lw=1.4))
        ax.text(x + w / 2, y + 0.475, step, fontproperties=SEMI, fontsize=10.5, color=SAFFRON if accent else MOSS,
                ha="center", va="center", linespacing=1.3)
        if i < len(steps) - 1:
            arrow(ax, (x + w, y + 0.475), (x + w + gap, y + 0.475))
    arrow(ax, (0.5 + 4 * (w + gap) + w / 2, y + 0.95), (0.5 + w / 2, y + 0.95), rad=0.12, dashed=True)
    versions = (
        ("v0.1", "First build", ("'Log in' hidden below", "the sign-up form; a Hindi", "question found no notes")),
        ("v0.2", "Fixes, a scripted tour", ("Marathi answers", "changed facts", "('belly' for 'back')")),
        ("v0.3", "A prompt fix", ("Marathi still wrong", "in 2 of 4 answers;", "read, not just scored")),
        ("v0.4", "Outside review", ("15 bugs fixed; Marathi", "notes: 7 errors to 0;", "two phones, one server")),
    )
    cw = 2.95
    for i, (tag, title, lines) in enumerate(versions):
        x = 0.5 + i * (cw + 0.17)
        card(ax, x, 0.75, cw, 1.9, "", (), fill=PAPER)
        ax.text(x + 0.18, 2.42, tag, fontproperties=BOLD, fontsize=16, color=SAFFRON, va="top")
        ax.text(x + 0.95, 2.37, title, fontproperties=BOLD, fontsize=11.5, color=MOSS, va="top")
        for k, line in enumerate(lines):
            ax.text(x + 0.18, 1.86 - k * 0.3, line, fontproperties=REGULAR, fontsize=10.5, color=INK, va="top")
    save(fig, "rounds")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    journey()
    how_it_works()
    rounds()
    print(f"diagrams in {OUT}")


if __name__ == "__main__":
    main()
