"""Renders docs/media/video/satt_chitt_anand_tour.mp4: a narrated tour of the app, about three minutes, to share with
people and ask for their feedback.

How it is made: Kokoro-82M speaks each line of the script on this
laptop and reports when each word starts; every scene lasts as long as its lines; frames are drawn with Pillow and
streamed to ffmpeg; a quiet synthesised pad sits under the voice (nothing to license); the mix is brought to -16 LUFS
with one fixed gain from a measuring pass. Captions follow the voice word by word, so the video also works muted, as
most videos shared on WhatsApp are first watched.

Everything shown is the real app: v0.4's tour screenshots and screen recordings (.local/visualization/tours/,
gitignored), on synthetic demo data. Writes the 720p video, its captions and a thumbnail to docs/media/video/, and a
1080p copy to .local/visualization/.

    scripts/setup_media.sh                                       # once: tools/media-venv
    tools/media-venv/bin/python scripts/make_video.py --stills   # one frame per shot, to check the layout
    tools/media-venv/bin/python scripts/make_video.py            # voice, frames, sound: the mp4s, captions, thumbnail
"""

import argparse
import functools
import hashlib
import json
import multiprocessing
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy.io import wavfile
from scipy.signal import butter, resample_poly, sosfilt

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "visualization"  # gitignored
MEDIA = LOCAL / "tours"  # the tours' screenshots and recordings
OUT = ROOT / "docs" / "media" / "video"
WORK = LOCAL / "work" / "video"  # the build's intermediate files: voice clips, clip frames, the silent picture, stills
FONTS = ROOT / "tools" / "fonts"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
os.environ.setdefault("HF_HOME", str(ROOT / "tools" / "hf"))

W, H, FPS, RATE = 1920, 1080, 30, 48000
VOICE, SPEED = "af_heart", 1.08  # a touch quicker than Kokoro's unhurried default
LEAD, GAP, TAIL, FADE, SHOT_FADE = 0.5, 0.4, 0.8, 0.45, 0.35
PHONE_H, PHONE_TOP, PHONE_X = 900, 70, 560  # phone height, top edge, and centre x
TEXT_X, TEXT_W = 1040, 760

CREAM, PAPER, INK, MUTED, FAINT, LINE = (246, 241, 231), (255, 252, 246), (43, 42, 38), (110, 106, 96), (190, 183, 170), (229, 221, 207)
MOSS, MOSS_LIGHT, SAFFRON, SAFFRON_LIGHT, DANGER = (63, 91, 69), (221, 230, 216), (194, 106, 45), (246, 224, 204), (179, 38, 30)

# Kokoro's own guesses for these were wrong ("Sat Chit Ann-and", "Hath-a"); spoken as written in IPA instead.
SATT = "[Satt Chitt Anand](/sˈʌt ʧˈɪt ɑnˈʌnd/)"
HATHA = "[Hatha](/hˈʌtə/)"
SATSANG = "[Satsang](/sˈʌtsʌŋ/)"
MARATHI = "[Marathi](/məɹˈɑti/)"

# Clips: source video (committed small copies), start and length in seconds, and speed.
CLIPS = {
    "breathe": (MEDIA / "v0.4" / "student_tour_small.mp4", 43.4, 10.2, 1.0),
    "ask": (MEDIA / "v0.4" / "student_tour_small.mp4", 57.4, 8.6, 1.0),
    "two": (LOCAL / "two_phones_v0.4.mp4", 44.0, 94.0, 5.0),  # to the teacher's Insights showing the check-in
}


@dataclass(frozen=True)
class Shot:
    """What the phone shows from line `at` of its scene: a screenshot under docs/media, or a clip. `focus` rings a
    part of the screen, as fractions of its width and height (left, top, right, bottom)."""

    at: int
    image: str = ""
    clip: str = ""
    focus: tuple = ()


@dataclass(frozen=True)
class Scene:
    key: str
    chapter: str
    tag: str
    title: str
    lines: tuple
    shots: tuple = ()
    kind: str = "phone"  # phone, title, wide (two phones), diagram, numbers, end
    least: float = 0.0  # shortest length, for scenes carrying a clip


SCENES = (
    Scene("title", "Welcome", "A prototype · November 2026", "", (
        f"Namaste. This is {SATT}, an app for an online yoga studio and its students.",
        "Classes are live on Google Meet every morning, and the class talks on WhatsApp.",
    ), (Shot(0, "v0.4/01_welcome.png"),), kind="title"),
    Scene("signup", "Students", "Students", "Signing up", (
        f"Students pick English, Hindi or {MARATHI}, and sign up with their WhatsApp number.",
        "A group code from the class WhatsApp group lets them in at once. Otherwise, the teacher approves them.",
    ), (Shot(0, "v0.4/02_signup.png"), Shot(1, "v0.4/02_signup.png", focus=(0.05, 0.705, 0.95, 0.81)))),
    Scene("today", "Students", "Students", "Today", (
        "Today shows the next class, with a countdown.",
        "One tap on Join class opens Google Meet.",
    ), (Shot(0, "v0.4/hero_today.png", focus=(0.04, 0.115, 0.96, 0.43)), Shot(1, "v0.4/hero_today.png", focus=(0.07, 0.335, 0.93, 0.41)))),
    Scene("checkin", "Students", "Students", "One tap: how do you feel?", (
        "Just before joining, the app asks one thing: how do you feel right now? Five faces. No reading needed.",
        "After class, it asks again, so everyone can see whether the classes help.",
    ), (Shot(0, "v0.4/04_checkin_before.png", focus=(0.07, 0.355, 0.93, 0.565)),
        Shot(1, "v0.4-two-phones/04_student_after_class.png", focus=(0.03, 0.115, 0.97, 0.315)))),
    Scene("week", "Students", "Students", "The week", (
        f"Week shows the studio's rhythm, from {HATHA} to Sunday {SATSANG}, and introduces the teacher.",
    ), (Shot(0, "v0.4/05_week.png"),)),
    Scene("breathe", "Students", "Students", "Breathe", (
        "Breathe is a circle that grows as you breathe in, and shrinks as you breathe out.",
        "It follows the eye, not words.",
    ), (Shot(0, clip="breathe"),), least=10.4),
    Scene("me", "Students", "Students", "My practice", (
        "Me shows a student's practice: classes, days in a row, and how much better they feel after class.",
    ), (Shot(0, "v0.4/09_me.png", focus=(0.03, 0.195, 0.97, 0.36)),)),
    Scene("ask", "Assistant", "The assistant", "Ask about yoga", (
        "Ask is a practice assistant. Students tap a suggested question, or type their own.",
        "It runs Gemma 4, an open AI model, on the studio's laptop, and answers only from the studio's own notes.",
        "Under every answer, it shows which notes it used.",
    ), (Shot(0, clip="ask"), Shot(1, "v0.4/08_ask_answer.png"),
        Shot(2, "v0.4/08_ask_answer.png", focus=(0.03, 0.735, 0.82, 0.77))), least=9.0),
    Scene("safety", "Assistant", "The assistant", "Safe by design", (
        "It never diagnoses, and never touches medicines.",
        "If someone mentions chest pain or fainting, it skips the AI, and tells them to stop and call one one two.",
    ), (Shot(0, "v0.4/17_ask_urgent.png"), Shot(1, "v0.4/17_ask_urgent.png", focus=(0.03, 0.315, 0.86, 0.545)))),
    Scene("languages", "Assistant", "The assistant", "Hindi and Marathi", (
        f"Everything works in Hindi and {MARATHI} too: the screens, the class names, and the answers.",
        f"For {MARATHI}, it copies notes written in {MARATHI}, so the facts stay right.",
    ), (Shot(0, "v0.4/19_today_marathi.png"), Shot(1, "v0.4/18_ask_marathi.png"))),
    Scene("classes", "Teacher", "The teacher", "Classes and WhatsApp", (
        "For the teacher, Classes shows the coming week.",
        "Paste the Meet link, tap Save and share, and WhatsApp opens with the message ready for the group.",
    ), (Shot(0, "v0.4/hero_teacher.png"), Shot(1, "v0.4/13_teacher_share.png", focus=(0.03, 0.555, 0.97, 0.705)))),
    Scene("students", "Teacher", "The teacher", "Students", (
        "Students shows who is waiting. The teacher approves them, removes them, or gives a new password.",
    ), (Shot(0, "v0.4/15_students.png", focus=(0.03, 0.095, 0.97, 0.24)),)),
    Scene("insights", "Teacher", "The teacher", "Insights", (
        "Insights shows who joined each class, and how they felt before and after. Here, with demo data.",
    ), (Shot(0, "v0.4/16_insights_demo_data.png"),)),
    Scene("two", "Teacher", "Two phones, one server", "Teacher and student", (
        "Here it is on two phones at once.",
        "The teacher posts the link. The student joins, checks in before and after class, and asks a question.",
        "And the teacher sees the check-in arrive.",
    ), (Shot(0, clip="two"),), kind="wide", least=19.0),
    Scene("built", "How it's built", "How it's built", "Under the hood", (
        "Under the hood: an Android app, and a small server on the studio's laptop, where Gemma runs on the graphics card.",
        "Accounts and check-ins live on that laptop, with an optional private backup. "
        "Questions are kept only if the student agrees.",
    ), kind="diagram"),
    Scene("rounds", "How it's built", "How it's built", "Built in small rounds", (
        "Sixty-nine automatic tests. Thirty-four questions to the assistant, every answer read. "
        "And an outside review that found fifteen bugs.",
        f"When {MARATHI} answers changed facts, notes written in {MARATHI} took the errors from seven to zero.",
    ), kind="numbers"),
    Scene("end", "Feedback", "Your feedback", "", (
        "We would love to hear from you. Would you use this before class? What was confusing? What is missing?",
        "Reply to whoever sent you this video. Thank you, and namaste.",
    ), kind="end"),
)
CHAPTERS = ("Welcome", "Students", "Assistant", "Teacher", "How it's built", "Feedback")
QUESTIONS = ("Would you use this before class?", "What was confusing?", "What is missing?")
NUMBERS = (("69", "automatic tests"), ("34", "questions, every answer read"), ("15", "bugs found by an outside review, fixed"),
           ("7 → 0", "Marathi answers that changed facts"))  # the arrow is drawn by big_text


def caption(line: str) -> str:
    """The words as shown: `[word](/phonemes/)` becomes `word`."""
    return re.sub(r"\[([^\]]+)\]\(/[^)]+/\)", r"\1", line)


# ---------- voice ----------


def voice(line: str) -> tuple[np.ndarray, list[tuple[str, float]]]:
    """The spoken line at RATE, and when each shown word starts, in seconds. Cached by text."""
    key = hashlib.sha1(f"{VOICE}|{SPEED}|{line}".encode()).hexdigest()[:16]
    wav, words_file = WORK / "voice" / f"{key}.wav", WORK / "voice" / f"{key}.json"
    if not wav.exists():
        from kokoro import KPipeline

        pipeline = voice.pipeline = getattr(voice, "pipeline", None) or KPipeline(lang_code=VOICE[0], repo_id="hexgrad/Kokoro-82M")
        pieces, spoken = [], []
        for chunk in pipeline(line, voice=VOICE, speed=SPEED):
            offset = sum(len(p) for p in pieces) / 24000
            for token in chunk.tokens:
                if token.start_ts is not None and re.search(r"\w", token.text):
                    spoken += [(word, round(offset + token.start_ts, 3)) for word in token.text.split()]
            pieces.append(np.asarray(chunk.audio, dtype=np.float32))
        audio = resample_poly(np.concatenate(pieces), RATE, 24000).astype(np.float32)
        wav.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(wav, RATE, audio)
        words_file.write_text(json.dumps(align(caption(line), spoken, len(audio) / RATE), ensure_ascii=False))
    return wavfile.read(wav)[1], [tuple(w) for w in json.loads(words_file.read_text())]


def align(text: str, spoken: list[tuple[str, float]], seconds: float) -> list[tuple[str, float]]:
    """Start times for the shown words: Kokoro's when the counts agree, else spread by position in the line."""
    words = text.split()
    if len(spoken) == len(words):
        return [(word, start) for word, (_, start) in zip(words, spoken, strict=True)]
    total, at, out = len(text), 0, []
    for word in words:
        out.append((word, round(seconds * 0.95 * at / total, 3)))
        at += len(word) + 1
    return out


# ---------- timeline ----------


@dataclass(frozen=True)
class Placed:
    scene: Scene
    start: float
    seconds: float
    line_starts: tuple
    line_seconds: tuple
    words: tuple  # per line: ((word, start), ...)


def timeline() -> list[Placed]:
    placed, t = [], 0.0
    for scene in SCENES:
        at, starts, lengths, words = LEAD, [], [], []
        for line in scene.lines:
            audio, spoken = voice(line)
            starts.append(at)
            lengths.append(len(audio) / RATE)
            words.append(tuple(spoken))
            at += len(audio) / RATE + GAP
        seconds = max(at - GAP + TAIL, scene.least + 0.6)
        placed.append(Placed(scene, t, seconds, tuple(starts), tuple(lengths), tuple(words)))
        t += seconds
    return placed


# ---------- drawing ----------


@functools.lru_cache(maxsize=64)
def font(size: int, weight: int = 500, serif: bool = False) -> ImageFont.FreeTypeFont:
    if serif:
        return ImageFont.truetype(SERIF, size)
    face = ImageFont.truetype(str(FONTS / "Sora.ttf"), size)
    face.set_variation_by_axes([weight])
    return face


def rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius, fill=255)
    return mask


BEZEL = 12


def framed(screen: Image.Image, height: int = PHONE_H) -> Image.Image:
    """A screen in a dark bezel with rounded corners, `height` tall including the bezel."""
    inner_h = height - 2 * BEZEL
    screen = screen.convert("RGB").resize((round(screen.width * inner_h / screen.height), inner_h), Image.LANCZOS)
    radius = inner_h // 22
    frame = Image.new("RGBA", (screen.width + 2 * BEZEL, height), (0, 0, 0, 0))
    ImageDraw.Draw(frame).rounded_rectangle([0, 0, frame.width - 1, height - 1], radius + BEZEL, fill=(31, 31, 28, 255))
    frame.paste(screen, (BEZEL, BEZEL), rounded_mask(screen.size, radius))
    return frame


@functools.lru_cache(maxsize=32)
def screenshot(path: str) -> Image.Image:
    return framed(Image.open(MEDIA / path))


def clip_frame(name: str, t: float) -> Image.Image:
    folder = WORK / "clips" / name
    count = len(list(folder.glob("*.png")))
    index = min(max(int(t * FPS), 0), count - 1)
    image = Image.open(folder / f"{index + 1:05d}.png")
    return framed(image, PHONE_H) if name != "two" else image


@functools.lru_cache(maxsize=1)
def shadow_for(size: tuple[int, int]) -> Image.Image:
    pad = 60
    shadow = Image.new("RGBA", (size[0] + 2 * pad, size[1] + 2 * pad), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle([pad, pad + 18, pad + size[0], pad + size[1] + 18], 60, fill=(0, 0, 0, 70))
    return shadow.filter(ImageFilter.GaussianBlur(26))


def place_phone(canvas: Image.Image, phone: Image.Image, cx: int = PHONE_X, top: int = PHONE_TOP) -> tuple[int, int]:
    x = cx - phone.width // 2
    shadow = shadow_for(phone.size)
    canvas.alpha_composite(shadow, (x - 60, top - 60))
    canvas.alpha_composite(phone, (x, top))
    return x, top


def said_at(placed: Placed, line: int, word: str) -> float:
    """When `word` (the first shown word starting with it) is spoken in line `line`, in scene seconds."""
    for shown, start in placed.words[line]:
        if shown.startswith(word):  # case matters: "Would you…" is a question, "we would love" is not
            return placed.line_starts[line] + start
    return placed.line_starts[line]


def ease(x: float) -> float:
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def focus_ring(canvas: Image.Image, origin: tuple[int, int], phone: Image.Image, box: tuple, amount: float) -> None:
    """Dims the screen outside `box` and draws a saffron ring round it, `amount` from 0 to 1."""
    if amount <= 0:
        return
    sw, sh = phone.width - 2 * BEZEL, phone.height - 2 * BEZEL
    x0, y0 = origin[0] + BEZEL, origin[1] + BEZEL
    left, top, right, bottom = (x0 + box[0] * sw, y0 + box[1] * sh, x0 + box[2] * sw, y0 + box[3] * sh)
    dim = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(dim)
    draw.rounded_rectangle([x0, y0, x0 + sw, y0 + sh], 36, fill=(30, 28, 24, int(85 * amount)))
    draw.rounded_rectangle([left - 6, top - 6, right + 6, bottom + 6], 22, fill=(0, 0, 0, 0))
    canvas.alpha_composite(dim)
    ring = ImageDraw.Draw(canvas)
    grow = 10 * (1 - amount)
    ring.rounded_rectangle([left - 8 - grow, top - 8 - grow, right + 8 + grow, bottom + 8 + grow], 24,
                           outline=SAFFRON + (int(255 * amount),), width=6)


def phone_at(placed: Placed, t: float) -> tuple[Image.Image, tuple]:
    """The phone picture for scene time `t`, and the ring to draw with its strength."""
    shots = placed.scene.shots
    current = max((s for s in shots if placed.line_starts[s.at] - 0.15 <= t), key=lambda s: s.at, default=shots[0])
    if current.clip:
        clip_start = placed.line_starts[current.at] if current.at else 0.0
        picture = clip_frame(current.clip, t - clip_start)
    else:
        picture = screenshot(current.image)
    ring = (current.focus, ease((t - placed.line_starts[current.at] - 0.2) / 0.45)) if current.focus else ((), 0.0)
    # Cross-fade from the previous shot when the picture changes.
    earlier = [s for s in shots if s.at < current.at]
    since = t - (placed.line_starts[current.at] - 0.15)
    if earlier and since < SHOT_FADE and (earlier[-1].image != current.image or earlier[-1].clip != current.clip):
        before = screenshot(earlier[-1].image) if earlier[-1].image else clip_frame(earlier[-1].clip, 99)
        if before.size == picture.size:
            picture = Image.blend(before, picture, ease(since / SHOT_FADE))
    return picture, ring


def wrap(text_words: list[str], face: ImageFont.FreeTypeFont, width: int) -> list[list[int]]:
    """Word indexes per line, wrapped to `width` pixels."""
    lines, line, used = [], [], 0
    space = face.getlength(" ")
    for i, word in enumerate(text_words):
        w = face.getlength(word)
        if line and used + space + w > width:
            lines.append(line)
            line, used = [], 0
        used += (space if line else 0) + w
        line.append(i)
    return lines + [line] if line else lines


def karaoke(draw: ImageDraw.ImageDraw, placed: Placed, t: float, x: int, y: int, width: int, size: int = 40, color=INK) -> None:
    """The line being spoken, each word darkening as it is said."""
    started = [i for i, s in enumerate(placed.line_starts) if s - 0.1 <= t]
    if not started:
        return
    index = started[-1]
    words = placed.words[index]
    local = t - placed.line_starts[index]
    face = font(size, 500)
    space = face.getlength(" ")
    fade_in = ease((t - placed.line_starts[index] + 0.1) / 0.25)
    for row, members in enumerate(wrap([w for w, _ in words], face, width)):
        cx = x
        for i in members:
            word, start = words[i]
            said = local >= start - 0.05
            fill = color if said else FAINT
            fill = tuple(int(CREAM[k] + (fill[k] - CREAM[k]) * fade_in) for k in range(3))
            draw.text((cx, y + row * int(size * 1.42)), word, font=face, fill=fill)
            cx += face.getlength(word) + space


def text_column(canvas: Image.Image, placed: Placed, t: float) -> None:
    scene = placed.scene
    draw = ImageDraw.Draw(canvas)
    appear = ease(t / 0.5)
    tag_color = tuple(int(CREAM[k] + (SAFFRON[k] - CREAM[k]) * appear) for k in range(3))
    draw.text((TEXT_X, 250), scene.tag.upper(), font=font(26, 700), fill=tag_color)
    title_color = tuple(int(CREAM[k] + (MOSS[k] - CREAM[k]) * appear) for k in range(3))
    draw.text((TEXT_X - 3, 292), scene.title, font=font(64, serif=True), fill=title_color)
    karaoke(draw, placed, t, TEXT_X, 420, TEXT_W)


def chapters_bar(canvas: Image.Image, placed: Placed, t_total: float, total: float) -> None:
    draw = ImageDraw.Draw(canvas)
    y = H - 38
    draw.rounded_rectangle([90, y, W - 90, y + 6], 3, fill=LINE)
    draw.rounded_rectangle([90, y, 90 + int((W - 180) * t_total / total), y + 6], 3, fill=MOSS)
    slot = (W - 180) / len(CHAPTERS)
    for i, name in enumerate(CHAPTERS):
        active = name == placed.scene.chapter
        draw.text((90 + slot * i, y - 34), name, font=font(20, 700 if active else 500), fill=MOSS if active else MUTED)


def draw_title(canvas: Image.Image, placed: Placed, t: float) -> None:
    picture, _ = phone_at(placed, t)
    place_phone(canvas, picture)
    draw = ImageDraw.Draw(canvas)
    appear = ease(t / 0.8)
    moss = tuple(int(CREAM[k] + (MOSS[k] - CREAM[k]) * appear) for k in range(3))
    saffron = tuple(int(CREAM[k] + (SAFFRON[k] - CREAM[k]) * appear) for k in range(3))
    draw.text((TEXT_X - 4, 170), "Satt Chitt Anand", font=font(84, serif=True), fill=moss)
    draw.text((TEXT_X, 285), "TRUTH · CONSCIOUSNESS · BLISS", font=font(28, 700), fill=saffron)
    draw.text((TEXT_X, 330), placed.scene.tag, font=font(26, 500), fill=moss)
    karaoke(draw, placed, t, TEXT_X, 430, TEXT_W)


def draw_wide(canvas: Image.Image, placed: Placed, t: float) -> None:
    picture = clip_frame("two", t).convert("RGB")
    height = PHONE_H - 40
    picture = picture.resize((round(picture.width * height / picture.height), height), Image.LANCZOS)
    half = picture.width // 2
    draw = ImageDraw.Draw(canvas)
    for i, label in enumerate(("Teacher", "Student")):
        part = framed(picture.crop((i * half, 0, (i + 1) * half, height)), height)
        cx = 300 + i * 500
        place_phone(canvas, part, cx, PHONE_TOP + 40)
        draw.text((cx, PHONE_TOP + 12), label.upper(), font=font(24, 700), fill=SAFFRON, anchor="mm")
    text_column(canvas, placed, t)


def box(draw, xy, title, lines=(), fill=PAPER, outline=LINE, title_color=MOSS, amount=1.0):
    def fade(c):
        return tuple(int(CREAM[k] + (c[k] - CREAM[k]) * amount) for k in range(3))

    draw.rounded_rectangle(xy, 22, fill=fade(fill), outline=fade(outline), width=3)
    draw.text((xy[0] + 26, xy[1] + 22), title, font=font(30, 700), fill=fade(title_color))
    for i, line in enumerate(lines):
        draw.text((xy[0] + 26, xy[1] + 70 + i * 38), line, font=font(24, 500), fill=fade(INK))


def arrow(draw, start, end, amount, label=""):
    if amount <= 0:
        return
    color = tuple(int(CREAM[k] + (MUTED[k] - CREAM[k]) * amount) for k in range(3))
    draw.line([start, end], fill=color, width=4)
    dx, dy = end[0] - start[0], end[1] - start[1]
    n = max((dx * dx + dy * dy) ** 0.5, 1)
    ux, uy = dx / n, dy / n
    tip = [end, (end[0] - 18 * ux + 10 * uy, end[1] - 18 * uy - 10 * ux), (end[0] - 18 * ux - 10 * uy, end[1] - 18 * uy + 10 * ux)]
    draw.polygon(tip, fill=color)
    if label:
        draw.text(((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 - 22), label, font=font(20, 500), fill=color, anchor="mm")


def draw_diagram(canvas: Image.Image, placed: Placed, t: float) -> None:
    draw = ImageDraw.Draw(canvas)
    first = ease((t - 0.3) / 0.6)
    second = ease((t - said_at(placed, 0, "server")) / 0.6)
    third = ease((t - said_at(placed, 0, "Gemma")) / 0.6)
    fourth = ease((t - placed.line_starts[-1]) / 0.6)
    box(draw, (90, 110, 420, 230), "WhatsApp group", ("the teacher shares",), amount=first)
    box(draw, (90, 330, 420, 520), "Phone", ("the Android app,", "students and teacher"), amount=first)
    box(draw, (90, 620, 420, 740), "Google Meet", ("the class itself",), amount=first)
    arrow(draw, (255, 330), (255, 236), first)
    arrow(draw, (255, 520), (255, 614), first)
    box(draw, (520, 110, 1000, 760), "Studio laptop", (), fill=MOSS_LIGHT, outline=MOSS, amount=second)
    box(draw, (550, 190, 970, 320), "Server", ("accounts and check-ins",), amount=second)
    box(draw, (550, 345, 970, 475), "Studio notes", ("in English and Marathi",), amount=second)
    box(draw, (550, 500, 970, 670), "Gemma 4", ("an open AI model,", "on the graphics card"), fill=SAFFRON_LIGHT, outline=SAFFRON,
        title_color=SAFFRON, amount=third)
    arrow(draw, (420, 425), (514, 425), second)
    if fourth > 0:
        color = tuple(int(CREAM[k] + (MOSS[k] - CREAM[k]) * fourth) for k in range(3))
        draw.text((550, 690), "Data lives here; backup optional.", font=font(24, 600), fill=color)
        draw.text((550, 722), "Questions kept only with consent.", font=font(24, 600), fill=color)
    text_column(canvas, placed, t)


def big_text(draw: ImageDraw.ImageDraw, xy: tuple, text: str, fill: tuple) -> None:
    """Large figures in Sora; an arrow, which Sora lacks, drawn as a shape."""
    face = font(96, 700)
    x, y = xy
    for k, part in enumerate(text.split("→")):
        if k:
            mid = y + 62
            draw.line([(x + 10, mid), (x + 70, mid)], fill=fill, width=9)
            draw.polygon([(x + 84, mid), (x + 60, mid - 20), (x + 60, mid + 20)], fill=fill)
            x += 104
        part = part.strip()
        draw.text((x, y), part, font=face, fill=fill)
        x += face.getlength(part) + 16


def draw_numbers(canvas: Image.Image, placed: Placed, t: float) -> None:
    draw = ImageDraw.Draw(canvas)
    reveal = (said_at(placed, 0, "Sixty"), said_at(placed, 0, "Thirty"), said_at(placed, 0, "fifteen"), said_at(placed, 1, "seven"))
    for i, ((big, small), at) in enumerate(zip(NUMBERS, reveal, strict=True)):
        amount = ease((t - at) / 0.5)
        if amount <= 0:
            continue
        x, y = 100 + (i % 2) * 440, 170 + (i // 2) * 330
        box(draw, (x, y, x + 400, y + 290), "", (), fill=MOSS_LIGHT if i < 3 else SAFFRON_LIGHT,
            outline=MOSS if i < 3 else SAFFRON, amount=amount)
        color = tuple(int(CREAM[k] + ((MOSS if i < 3 else SAFFRON)[k] - CREAM[k]) * amount) for k in range(3))
        big_text(draw, (x + 34, y + 40), big, color)
        for row, members in enumerate(wrap(small.split(), font(28, 500), 330)):
            draw.text((x + 36, y + 180 + row * 38), " ".join(small.split()[i] for i in members), font=font(28, 500),
                      fill=tuple(int(CREAM[k] + (INK[k] - CREAM[k]) * amount) for k in range(3)))
    text_column(canvas, placed, t)


def draw_end(canvas: Image.Image, placed: Placed, t: float) -> None:
    draw = ImageDraw.Draw(canvas)
    appear = ease(t / 0.6)
    moss = tuple(int(CREAM[k] + (MOSS[k] - CREAM[k]) * appear) for k in range(3))
    draw.text((W // 2, 170), "We would love your feedback", font=font(72, serif=True), fill=moss, anchor="mm")
    cues = (said_at(placed, 0, "Would"), said_at(placed, 0, "confusing") - 0.4, said_at(placed, 0, "missing") - 0.4)
    for i, question in enumerate(QUESTIONS):
        amount = ease((t - cues[i]) / 0.5)
        if amount <= 0:
            continue
        y = 300 + i * 120
        fill = tuple(int(CREAM[k] + (PAPER[k] - CREAM[k]) * amount) for k in range(3))
        edge = tuple(int(CREAM[k] + (SAFFRON[k] - CREAM[k]) * amount) for k in range(3))
        draw.rounded_rectangle([W // 2 - 520, y, W // 2 + 520, y + 92], 46, fill=fill, outline=edge, width=3)
        draw.text((W // 2, y + 46), question, font=font(40, 600), fill=tuple(int(CREAM[k] + (INK[k] - CREAM[k]) * amount) for k in range(3)),
                  anchor="mm")
    last = ease((t - placed.line_starts[1]) / 0.5)
    if last > 0:
        draw.text((W // 2, 700), "Satt Chitt Anand · a prototype · synthetic demo data", font=font(24, 500),
                  fill=tuple(int(CREAM[k] + (MUTED[k] - CREAM[k]) * last) for k in range(3)), anchor="mm")
    karaoke(draw, placed, t, W // 2 - 600, 790, 1200, size=38, color=SAFFRON)


def draw_scene(placed: Placed, t: float, t_total: float, total: float) -> Image.Image:
    canvas = Image.new("RGBA", (W, H), CREAM + (255,))
    kind = placed.scene.kind
    if kind == "title":
        draw_title(canvas, placed, t)
    elif kind == "wide":
        draw_wide(canvas, placed, t)
    elif kind == "diagram":
        draw_diagram(canvas, placed, t)
    elif kind == "numbers":
        draw_numbers(canvas, placed, t)
    elif kind == "end":
        draw_end(canvas, placed, t)
    else:
        picture, (focus, amount) = phone_at(placed, t)
        origin = place_phone(canvas, picture)
        if focus:
            focus_ring(canvas, origin, picture, focus, amount)
        if placed.scene.key == "insights":
            stamp = ImageDraw.Draw(canvas)
            stamp.rounded_rectangle([origin[0] + 40, PHONE_TOP + PHONE_H - 120, origin[0] + 250, PHONE_TOP + PHONE_H - 70], 25,
                                    fill=SAFFRON)
            stamp.text((origin[0] + 145, PHONE_TOP + PHONE_H - 95), "DEMO DATA", font=font(24, 700), fill=(255, 255, 255), anchor="mm")
        text_column(canvas, placed, t)
    chapters_bar(canvas, placed, t_total, total)
    return canvas


PLAN: list[Placed] = []


def frame(index: int) -> bytes:
    t_total = index / FPS
    total = PLAN[-1].start + PLAN[-1].seconds
    i = max(k for k, p in enumerate(PLAN) if p.start <= t_total)
    placed = PLAN[i]
    t = t_total - placed.start
    image = draw_scene(placed, t, t_total, total)
    if i > 0 and t < FADE:
        before = PLAN[i - 1]
        image = Image.blend(draw_scene(before, before.seconds - 0.001, t_total, total), image, ease(t / FADE))
    return image.convert("RGB").tobytes()


# ---------- clips, sound, output ----------


def extract_clips() -> None:
    for name, (source, start, seconds, speed) in CLIPS.items():
        folder = WORK / "clips" / name
        if folder.exists() and any(folder.iterdir()):
            continue
        folder.mkdir(parents=True, exist_ok=True)
        height = PHONE_H - 2 * BEZEL if name != "two" else PHONE_H - 40
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-ss", str(start), "-t", str(seconds), "-i", str(source),
             # Sampling at FPS / speed plays back `speed` times faster (setpts does not work on the two-phone
             # recording, whose timestamps come from joining two recordings).
             "-vf", f"fps={FPS / speed},scale=-2:{height}:flags=lanczos", str(folder / "%05d.png")],
            check=True,
        )


def pad(seconds: float) -> np.ndarray:
    """A quiet, slow chord pad (C, A minor, F, G), stereo at RATE."""
    n = int(seconds * RATE)
    t = np.arange(n) / RATE
    chords = ((48, 55, 64, 67), (45, 52, 60, 64), (41, 48, 57, 60), (43, 50, 59, 62))
    out = np.zeros(n)
    length = 6.0
    for k in range(int(seconds // length) + 1):
        start = int(k * length * RATE)
        end = min(n, int((k + 1) * length * RATE + 2.5 * RATE))
        if start >= n:
            break
        local = t[start:end] - k * length
        shape = np.clip(local / 2.0, 0, 1) * np.clip((length + 2.5 - local) / 2.5, 0, 1)
        for note in chords[k % 4]:
            f = 440 * 2 ** ((note - 69) / 12)
            out[start:end] += shape * (np.sin(2 * np.pi * f * local) + 0.3 * np.sin(4 * np.pi * f * local + 1.0)) / 4
    out = sosfilt(butter(2, 1400, "low", fs=RATE, output="sos"), out)
    left = out * (1 + 0.15 * np.sin(2 * np.pi * 0.05 * t))
    right = out * (1 - 0.15 * np.sin(2 * np.pi * 0.05 * t))
    return np.stack([left, right], axis=1) / max(np.abs(out).max(), 1e-9)


def soundtrack(path: Path, total: float) -> None:
    n = int((total + 0.5) * RATE)
    speech = np.zeros(n, dtype=np.float64)
    for placed in PLAN:
        for line, start in zip(placed.scene.lines, placed.line_starts, strict=True):
            audio, _ = voice(line)
            at = int((placed.start + start) * RATE)
            speech[at : at + len(audio)] += audio[: max(0, min(len(audio), n - at))]
    # The pad dips while someone is speaking.
    window = RATE // 5  # a 0.2 s running average of the voice's level, by cumulative sums
    sums = np.concatenate([[0.0], np.cumsum(np.abs(speech))])
    level = np.empty(n)
    level[: n - window] = (sums[window:n] - sums[: n - window]) / window
    level[n - window :] = level[n - window - 1]
    duck = 1 - 0.45 * np.clip(level / (level.max() * 0.15 + 1e-9), 0, 1)
    bed = pad(n / RATE)[:n] * 0.075 * duck[:, None]
    t = np.arange(n) / RATE
    fade = np.clip(t / 1.5, 0, 1) * np.clip((total + 0.3 - t) / 2.0, 0, 1)
    stereo = (bed + np.stack([speech * 0.9] * 2, axis=1)) * fade[:, None]
    wavfile.write(path, RATE, (np.clip(stereo, -1, 1) * 32767).astype(np.int16))


# Speech peaks sit far above its average level, so one fixed gain under a peak ceiling stopped
# at -24 LUFS, too quiet on a phone speaker. Here: even the voice with a gentle compressor, measure, apply the gain to
# reach -16 LUFS, and let a limiter after the gain hold the peaks under -1.5 dB.
EVEN = "acompressor=threshold=0.05:ratio=4:attack=5:release=150:makeup=2"


def loudness(sound: Path) -> str:
    """An ffmpeg filter that brings `sound` to about -16 LUFS with one fixed gain (no level riding, so the pad does
    not pump between lines) and a limiter after it."""
    report = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(sound), "-af", f"{EVEN},loudnorm=print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, check=True,
    ).stderr
    measured = json.loads(report[report.rindex("{") :])
    gain = -16.0 - float(measured["input_i"])
    return f"{EVEN},volume={gain:.2f}dB,alimiter=limit=0.84:attack=2:release=60:level=false,aresample=48000"


def subtitles(path: Path) -> None:
    """An .srt file with every spoken line, for players and sites that show captions."""

    def stamp(seconds: float) -> str:
        ms = int(round(seconds * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    rows, k = [], 1
    for placed in PLAN:
        for line, start, seconds in zip(placed.scene.lines, placed.line_starts, placed.line_seconds, strict=True):
            begin = placed.start + start
            rows.append(f"{k}\n{stamp(begin)} --> {stamp(begin + seconds + 0.2)}\n{caption(line)}\n")
            k += 1
    path.write_text("\n".join(rows), encoding="utf-8")


def encode() -> None:
    total = PLAN[-1].start + PLAN[-1].seconds
    frames = int(total * FPS)
    picture = WORK / "picture.mp4"
    render_picture(picture, frames)
    finish(picture, total)


def render_picture(picture: Path, frames: int) -> None:
    command = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
               "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p", str(picture)]
    encoder = subprocess.Popen(command, stdin=subprocess.PIPE)
    with multiprocessing.Pool(max(2, os.cpu_count() - 4)) as pool:
        for raw in pool.imap(frame, range(frames), chunksize=8):
            encoder.stdin.write(raw)
    encoder.stdin.close()
    encoder.wait()


def finish(picture: Path, total: float) -> None:
    """Sound, the two mp4s, the thumbnail and the captions, from the silent picture."""
    sound = WORK / "sound.wav"
    soundtrack(sound, total)
    OUT.mkdir(parents=True, exist_ok=True)
    audio = ["-i", str(sound), "-af", loudness(sound), "-c:a", "aac", "-b:a", "160k", "-ac", "2"]
    base = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(picture), *audio, "-t", f"{total:.2f}", "-movflags", "+faststart"]
    subprocess.run([*base, "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p",
                    str(LOCAL / "satt_chitt_anand_tour_1080p.mp4")], check=True)
    # Small enough to send on WhatsApp.
    subprocess.run([*base, "-vf", "scale=1280:720:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "28",
                    "-pix_fmt", "yuv420p", str(OUT / "satt_chitt_anand_tour_720p.mp4")], check=True)
    Image.frombytes("RGB", (W, H), frame(int(PLAN[0].seconds * 0.8 * FPS))).save(OUT / "satt_chitt_anand_tour_thumbnail.png", optimize=True)
    subtitles(OUT / "satt_chitt_anand_tour.srt")
    print(f"wrote {OUT / 'satt_chitt_anand_tour_720p.mp4'}: {total:.1f} s", flush=True)


def stills() -> None:
    folder = WORK / "stills"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    for placed in PLAN:
        moments = sorted({placed.line_starts[s.at] + 1.2 for s in placed.scene.shots} | {placed.seconds - 0.3})
        for k, at in enumerate(moments):
            index = int((placed.start + at) * FPS)
            Image.frombytes("RGB", (W, H), frame(index)).save(folder / f"{placed.start:06.1f}_{placed.scene.key}_{k}.png")
    print(f"stills in {folder}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--stills", action="store_true", help="only one frame per shot, to check the layout")
    parser.add_argument("--sound", action="store_true", help="redo the sound and outputs from the last picture")
    args = parser.parse_args()
    extract_clips()
    PLAN.extend(timeline())
    total = PLAN[-1].start + PLAN[-1].seconds
    print(f"{len(PLAN)} scenes, {total:.1f} s", flush=True)
    if args.stills:
        stills()
    elif args.sound:
        finish(WORK / "picture.mp4", total)
    else:
        encode()


if __name__ == "__main__":
    main()
