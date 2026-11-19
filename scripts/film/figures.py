"""Flat, friendly figures without faces: a 2D skeleton with rounded limbs, eased between keyframed yoga poses.

A pose is ten absolute angles in degrees (0 points up, 90 right, 180 down): torso, head, each arm's upper and lower
part, each leg's thigh and shin; then its breadth, 1 when the figure faces us (shoulders and hips apart) and 0 when
seen from the side. Limb "a" is drawn in front. Figures stand on their floor: whatever pose they are in,
the lowest point touches it."""

import math
from dataclasses import dataclass

from PIL import ImageDraw

from make_video import ease

POSES = {
    "tadasana": (0, 0, 196, 188, 164, 172, 182, 180, 178, 180, 1),
    "arms_up": (0, 0, -6, -2, 6, 2, 182, 180, 178, 180, 1),
    "trikonasana": (62, 68, 0, 0, 180, 180, 205, 205, 155, 155, 1),
    "vrikshasana": (0, 0, -22, 34, 22, -34, 180, 180, 128, 238, 1),
    "bend": (8, 4, 188, 178, 172, 166, 145, 215, 147, 217, 0),  # knees bent forward over planted feet, going down
    "kneel": (0, 0, 190, 186, 170, 174, 180, 270, 182, 272, 0),  # upright on the knees, on the way down to sit
    "vajrasana": (2, 0, 158, 108, 162, 110, 95, 270, 97, 272, 0),
    "balasana": (112, 140, 100, 92, 102, 94, 150, 272, 152, 274, 0),
    "shavasana": (270, 272, 95, 92, 87, 89, 90, 90, 92, 92, 0),
    "seated": (0, 4, 168, 120, 172, 124, 95, 270, 97, 272, 0),  # sitting on the heels, looking at a phone
    "virabhadrasana": (0, 0, 268, 270, 92, 90, 220, 182, 145, 145, 1),  # warrior: front knee bent, arms out wide
    "utkatasana": (18, 12, 350, 352, 354, 356, 112, 200, 114, 202, 0),  # chair: knees bent, arms reaching up
    "padmasana": (0, 0, 220, 200, 140, 160, 255, 85, 105, 275, 1),  # lotus, facing us: knees out, shins crossed, hands on knees
    "sarvangasana": (180, 270, 92, 2, 88, 0, 0, 0, 2, 2, 0),  # shoulder stand: legs up, hands on the back
    "halasana": (170, 270, 92, 92, 88, 90, 235, 205, 237, 207, 0),  # plough: feet over the head to the floor
    "sectional": (270, 270, 60, 110, 95, 92, 40, 150, 42, 152, 0),  # lying, knees bent, a hand on the belly
    "pavanamuktasana": (270, 278, 45, 70, 95, 92, 330, 80, 90, 90, 0),  # lying, one knee hugged to the chest
    "setu": (240, 270, 95, 92, 97, 94, 80, 175, 82, 177, 0),  # bridge: shoulders down, hips lifted
}
TRANSITION = 0.75
LENGTH = {"torso": 0.31, "neck": 0.135, "arm": 0.16, "forearm": 0.15, "thigh": 0.24, "shin": 0.23}
HEAD = 0.075


@dataclass(frozen=True)
class Person:
    """How someone looks and moves: colours, and how they differ from the teacher's lead."""

    name: str
    shirt: tuple
    skin: tuple
    hair: tuple = (58, 44, 36)
    pants: tuple = (70, 66, 58)
    lag: float = 0.0  # seconds behind the teacher
    offsets: tuple = (0,) * 11  # degrees added to each part


def turn(a: float, b: float, p: float) -> float:
    """From angle a to angle b the short way round, at p (0 to 1)."""
    d = (b - a + 180) % 360 - 180
    return a + d * p


def blend(a: tuple, b: tuple, p: float) -> tuple:
    return tuple(turn(x, y, p) for x, y in zip(a, b, strict=True))


def pose_at(sequence: tuple, t: float) -> tuple:
    """The angles at time t of a sequence of (pose, hold seconds), easing for TRANSITION between poses."""
    at = 0.0
    for k, (name, hold) in enumerate(sequence):
        if t < at + hold or k == len(sequence) - 1:
            return POSES[name]
        at += hold
        following = sequence[k + 1][0]
        if t < at + TRANSITION:
            return blend(POSES[name], POSES[following], ease((t - at) / TRANSITION))
        at += TRANSITION
    return POSES[sequence[-1][0]]


def length(sequence: tuple) -> float:
    return sum(hold for _, hold in sequence) + TRANSITION * (len(sequence) - 1)


def moving(person: Person, sequence: tuple, t: float) -> tuple:
    """`person`'s angles at t: the sequence a little behind the lead, their own small differences, and a breath."""
    breath = math.sin(t * 1.3 + hash(person.name) % 7) * 1.5
    angles = pose_at(sequence, t - person.lag)
    return tuple(a + o + breath * (k in (2, 4)) for k, (a, o) in enumerate(zip(angles, person.offsets, strict=True)))


def skeleton(angles: tuple, height: float) -> dict:
    """Joint positions for `angles`, in pixels, with the pelvis at (0, 0) and y down."""
    torso, head, arm_a, forearm_a, arm_b, forearm_b, thigh_a, shin_a, thigh_b, shin_b, breadth = angles

    def step(p: tuple, angle: float, part: str) -> tuple:
        a = math.radians(angle)
        return p[0] + math.sin(a) * LENGTH[part] * height, p[1] - math.cos(a) * LENGTH[part] * height

    j = {"pelvis": (0.0, 0.0)}
    j["neck"] = step(j["pelvis"], torso, "torso")
    j["head"] = step(j["neck"], head, "neck")
    across = (math.cos(math.radians(torso)) * height, math.sin(math.radians(torso)) * height)  # to the body's right
    for side, sign, arm, forearm, thigh, shin in (("a", -1, arm_a, forearm_a, thigh_a, shin_a),
                                                  ("b", 1, arm_b, forearm_b, thigh_b, shin_b)):
        shoulder = (j["neck"][0] * 0.88 + sign * across[0] * 0.075 * breadth, j["neck"][1] * 0.88 + sign * across[1] * 0.075 * breadth)
        hip = (sign * 0.045 * height * breadth, 0.0)  # the pelvis stays level
        j["shoulder_" + side], j["hip_" + side] = shoulder, hip
        j["elbow_" + side] = step(shoulder, arm, "arm")
        j["hand_" + side] = step(j["elbow_" + side], forearm, "forearm")
        j["knee_" + side] = step(hip, thigh, "thigh")
        j["foot_" + side] = step(j["knee_" + side], shin, "shin")
    return j


def shade(color: tuple, k: float) -> tuple:
    return tuple(int(c * k) for c in color)


def limb(draw: ImageDraw.ImageDraw, points: list, width: float, color: tuple) -> None:
    """A thick line with rounded joints and ends."""
    w = max(2, round(width))
    draw.line(points, fill=color, width=w, joint="curve")
    for x, y in (points[0], points[-1]):
        draw.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=color)


def draw_figure(draw: ImageDraw.ImageDraw, person: Person, angles: tuple, x: float, floor: float, height: float) -> dict:
    """`person` in pose `angles`, centred on x at the pelvis, standing (or lying) on the line y = floor; returns where
    the joints are."""
    j = skeleton(angles, height)
    # While the body is upright (standing, kneeling, sitting back on the heels) the feet stay planted and the pelvis
    # moves over them, so going down to kneel the knees bend forward rather than the feet sliding back. Folded or
    # lying down, the pelvis leads.
    x -= max(0.0, math.cos(math.radians(angles[0]))) * (j["foot_a"][0] + j["foot_b"][0]) / 2
    head_r = HEAD * height
    arm_w, leg_w, torso_w = 0.06 * height, 0.075 * height, 0.13 * height
    # The lowest point of the drawn body, limbs' thickness included, rests on the floor.
    half = {"pelvis": torso_w, "neck": torso_w, "hip_a": leg_w, "hip_b": leg_w, "knee_a": leg_w, "knee_b": leg_w,
            "foot_a": leg_w, "foot_b": leg_w}
    lowest = max(max(y + half.get(k, arm_w) / 2 for k, (_, y) in j.items() if k != "head"), j["head"][1] + head_r)
    dy = floor - lowest
    p = {k: (x + v[0], v[1] + dy) for k, v in j.items()}
    limb(draw, [p["hip_b"], p["knee_b"], p["foot_b"]], leg_w, shade(person.pants, 0.82))
    limb(draw, [p["shoulder_b"], p["elbow_b"], p["hand_b"]], arm_w, shade(person.shirt, 0.82))
    limb(draw, [p["hip_a"], p["knee_a"], p["foot_a"]], leg_w, person.pants)
    limb(draw, [p["pelvis"], p["neck"]], torso_w, person.shirt)
    limb(draw, [p["neck"], p["head"]], 0.07 * height, person.skin)  # the neck, so the head never floats
    hx, hy = p["head"]
    draw.ellipse([hx - head_r, hy - head_r, hx + head_r, hy + head_r], fill=person.skin)
    # Hair over the top half of the head, turned with it.
    direction = math.degrees(math.atan2(hy - p["neck"][1], hx - p["neck"][0]))
    draw.chord([hx - head_r, hy - head_r, hx + head_r, hy + head_r], direction - 95, direction + 95, fill=person.hair)
    limb(draw, [p["shoulder_a"], p["elbow_a"], p["hand_a"]], arm_w, person.shirt)
    for hand in ("hand_a", "hand_b"):
        hx, hy = p[hand]
        r = arm_w * 0.55
        draw.ellipse([hx - r, hy - r, hx + r, hy + r], fill=person.skin)
    return p
