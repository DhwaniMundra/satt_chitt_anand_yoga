"""Walks through the app on the emulator and saves the same screenshots and two screen recordings every time,
so each iteration can be compared with the last: .local/visualization/viz_<major>/screens/<version>/ (gitignored;
scripts/make_figures.py turns the best of it into the committed GIFs and contact sheets in docs/media/).

Needs: `source scripts/env.sh`, the 6 GB emulator running (SCA_AVD=sca_phone_big scripts/run_emulator.sh) with
Gemma downloaded in Ask, and nothing else on port 8000. The tour starts the dev backend on a fresh copy of the
synthetic demo (data/tour.json), adds a class starting in 20 minutes so the before-class check-in is open, and starts
the app signed out with no chat or notes, so a second run shows the same screens.

Usage: python3 scripts/capture_tour.py v1
"""

import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

import phone as p
import viz

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
STUDENT = ("9800000002", "demo123")
TEACHER = ("9800000001", "demo123")
CLEAR_HI = "\u0938\u093e\u092b\u093c \u0915\u0930\u0947\u0902"  # "साफ़ करें" (Clear), spelt as in values-hi/strings.xml


def main(version: str) -> None:
    with p.dev_backend(ROOT / "data" / "tour.json", demo=True):
        p.add_class("hatha", 20)
        tour(version)


def tour(version: str) -> None:
    out = viz.screens(version)
    out.mkdir(parents=True, exist_ok=True)

    def shot(name: str) -> None:
        full = out / f"{name}.png"
        p.screenshot(full)
        image = Image.open(full).convert("RGB")
        image.resize((image.width // 2, image.height // 2), Image.LANCZOS).save(full, optimize=True)

    def log_in(number: str, password: str) -> None:
        p.tap("Log in", exact=True)
        p.type_into("WhatsApp number", number)
        p.type_into("Password", password)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)  # the button under the form, not the switch above it
        time.sleep(3)

    p.adb("install", "-r", str(APK))
    p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
    p.demo_mode()
    p.launch(fresh=True)

    # ---- student ----
    video = p.Recording(viz.folder(version) / f"student_tour_{version}.mp4")
    shot("01_welcome")
    p.tap("I'm a student")
    shot("02_signup")
    log_in(*STUDENT)
    shot("03_today")
    p.tap("Join class")
    shot("04_checkin_before")
    p.tap("Okay")  # the 😐 face, by its spoken label
    time.sleep(3)
    p.launch()  # back from the Meet link in the browser
    p.tap("Practice", exact=True)
    shot("05_practice")
    p.tap("Ask", exact=True)
    shot("07_ask")
    p.tap("How was my practice this week?")
    p.find("Looked at your practice", timeout=120)
    time.sleep(1)
    shot("08_ask_answer")
    p.type_into("Type your question", "Please remember that my left knee hurts in Vajrasana.")
    shot("08a_ask_typing")  # the box stays above the keyboard
    p.tap("Send", exact=True)
    p.find("Saved a note", timeout=120)
    p.hide_keyboard()
    time.sleep(1)
    shot("08b_ask_remember")
    p.tap("Me", exact=True)
    p.find("left knee hurts")  # under "What I remember"
    time.sleep(1)
    shot("09_me")
    tap_below("हिन्दी")  # the language chips, under what the companion remembers
    time.sleep(3)
    p.tap("आज", exact=True)
    time.sleep(1.5)
    shot("10_today_hindi")
    video.stop()

    p.launch()
    p.tap("पूछें", exact=True)
    p.tap(CLEAR_HI, exact=True)  # the phone keeps the English conversation; cleared, the Hindi suggestions show
    p.tap("इस हफ्ते मेरी प्रैक्टिस कैसी रही?")
    p.find("आपका अभ्यास देखा", timeout=120)
    time.sleep(1)
    shot("11_ask_hindi")
    p.tap("मैं", exact=True)
    tap_below("English")
    time.sleep(3)
    p.scroll_down()
    tap_below("Log out")
    time.sleep(1.5)

    # ---- teacher ----
    video = p.Recording(viz.folder(version) / f"teacher_tour_{version}.mp4")
    p.tap("I'm the teacher")
    log_in(*TEACHER)
    shot("12_teacher_classes")
    p.type_into("Google Meet link", "meet.google.com/xyz-abcd-efg")
    p.hide_keyboard()
    p.tap("Save and share on WhatsApp")
    time.sleep(2.5)
    shot("13_teacher_share")
    p.back()
    time.sleep(1)
    p.scroll_down()
    p.scroll_down()
    shot("14_teacher_group")
    p.tap("Students", exact=True)
    time.sleep(2)
    shot("15_students")
    p.tap("Insights", exact=True)
    time.sleep(2)
    shot("16_insights_demo_data")
    video.stop()

    for name in ("student_tour", "teacher_tour"):
        make_small(viz.folder(version) / f"{name}_{version}.mp4", out / f"{name}_small.mp4")
    print(f"saved to {out}")


def tap_below(text: str) -> None:
    """Taps `text`, scrolling down once first if it is not on screen."""
    try:
        p.find(text, timeout=2)
    except TimeoutError:
        p.scroll_down()
    p.tap(text)


def make_small(video: Path, small: Path) -> None:
    """A 540 px copy, the source for the GIFs and the narrated video."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=540:-2,fps=24", "-c:v", "libx264",
                    "-crf", "30", "-preset", "slow", "-an", "-movflags", "+faststart", str(small)], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
