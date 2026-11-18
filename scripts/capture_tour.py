"""Walks through the app on the emulator and saves the same screenshots and two screen recordings every time,
so each iteration can be compared with the last: .local/visualization/tours/<version>/ (gitignored;
scripts/make_figures.py turns the best of it into the committed GIFs and contact sheets in docs/media/).

Needs: `source scripts/env.sh`, the emulator running (scripts/run_emulator.sh), and the backend running on the
synthetic demo database (backend/scripts/seed_demo.py), with Gemma loaded.

Usage: python3 scripts/capture_tour.py v0.4 data/demo.sqlite3
(The database path lets the tour add a class starting in 20 minutes, so the before-class check-in is open.)
"""

import sqlite3
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

import phone as p

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "visualization"  # gitignored: recordings on top, raw screenshots in tours/
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
STUDENT = ("9800000002", "demo123")
TEACHER = ("9800000001", "demo123")


def class_soon(db_path: Path) -> None:
    """A Hatha class 20 minutes from now: the check-in opens an hour before class, whatever the time of the tour."""
    start = (datetime.now(UTC) + timedelta(minutes=20)).replace(second=0).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn = sqlite3.connect(db_path)
    conn.execute("INSERT OR IGNORE INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES ('hatha', ?, 55, ?)", (start, start))
    conn.commit()


def main(version: str, db_path: Path) -> None:
    out = LOCAL / "tours" / version
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

    class_soon(db_path)
    p.adb("install", "-r", str(APK))
    p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
    p.demo_mode()
    p.launch(clear=True)

    # ---- student ----
    video = p.Recording(LOCAL / f"student_tour_{version}.mp4")
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
    p.tap("Week", exact=True)
    shot("05_week")
    p.tap("Breathe", exact=True)
    p.tap("Start", exact=True)
    time.sleep(6)
    shot("06_breathe")
    p.tap("Stop", exact=True)
    p.tap("Ask", exact=True)
    shot("07_ask")
    p.tap("Yoga for back pain?")
    p.find("From the notes", timeout=120)
    time.sleep(1)
    shot("08_ask_answer")
    p.tap("Me", exact=True)
    shot("09_me")
    p.tap("हिन्दी")
    time.sleep(3)
    p.tap("आज", exact=True)
    time.sleep(1.5)
    shot("10_today_hindi")
    video.stop()

    p.launch()  # a fresh start empties the chat, so the Hindi suggestions show
    p.tap("पूछें", exact=True)
    p.tap("कक्षा से पहले क्या खाएँ?")
    p.find("नोट्स से", timeout=120)
    time.sleep(1)
    shot("11_ask_hindi")
    p.tap("मैं", exact=True)
    p.tap("English")
    time.sleep(3)
    p.scroll_down()
    p.tap("Log out")
    time.sleep(1.5)

    # ---- teacher ----
    video = p.Recording(LOCAL / f"teacher_tour_{version}.mp4")
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
        make_small(LOCAL / f"{name}_{version}.mp4", out / f"{name}_small.mp4")
    print(f"saved to {out}")


def make_small(video: Path, small: Path) -> None:
    """A 540 px copy, the source for the GIFs and the narrated video."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=540:-2,fps=24", "-c:v", "libx264",
                    "-crf", "30", "-preset", "slow", "-an", "-movflags", "+faststart", str(small)], check=True)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
