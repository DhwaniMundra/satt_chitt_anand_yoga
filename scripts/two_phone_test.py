"""Two phones, one server: a teacher on emulator-5554 and students on emulator-5556. Checks the loop across
devices, saves a screenshot at each step (.local/visualization/tours/<version>/) and records both screens into one
side-by-side video (.local/visualization/two_phones_<version>.mp4); the pass/fail list goes to
docs/evals/two_phones_<version>.md.

Needs: both emulators running (scripts/run_emulator.sh, then SCA_AVD=sca_phone_2 SCA_PORT=5556 ...), the APK built,
and the backend running on a fresh database with SCA_TEACHER_CODE set. `server` is the address the app shows:
http://10.0.2.2:8000 for emulators, or the laptop's Wi-Fi address for an APK built with -PscaServer.
Uses test people only.

Usage: python3 scripts/two_phone_test.py v0.3-two-phones http://10.0.2.2:8000 data/two_phones.sqlite3 PILOT1
"""

import subprocess

import os
import sqlite3
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from PIL import Image

import phone as p

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "visualization"  # gitignored
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TEACHER, STUDENT = "emulator-5554", "emulator-5556"


def on(serial: str) -> None:
    """Points every following adb call at one phone."""
    os.environ["ANDROID_SERIAL"] = serial


def main(version: str, server: str, db_path: Path, teacher_code: str) -> None:
    out = LOCAL / "tours" / version
    out.mkdir(parents=True, exist_ok=True)
    results: list[tuple[str, bool]] = []

    def shot(name: str) -> None:
        full = out / f"{name}.png"
        p.screenshot(full)
        image = Image.open(full).convert("RGB")
        image.resize((image.width // 2, image.height // 2), Image.LANCZOS).save(full, optimize=True)

    def check(what: str, text: str, timeout: float = 20) -> None:
        try:
            p.find(text, timeout=timeout)
            results.append((what, True))
        except TimeoutError:
            results.append((what, False))
        print(("PASS " if results[-1][1] else "FAIL ") + what, flush=True)

    def check_gone(what: str, text: str) -> None:
        time.sleep(2)
        try:
            p.find(text, timeout=3)
            results.append((what, False))
        except TimeoutError:
            results.append((what, True))
        print(("PASS " if results[-1][1] else "FAIL ") + what, flush=True)

    def come_back() -> None:
        """Home, then back to the running app, as a person returning from Meet or WhatsApp would."""
        p.adb("shell", "input", "keyevent", "KEYCODE_HOME")
        time.sleep(1)
        p.adb("shell", "am", "start", "-n", f"{p.PACKAGE}/.MainActivity")
        time.sleep(3)

    def sign_up(name: str, number: str, code: str, teacher: bool = False) -> None:
        p.tap("I'm the teacher" if teacher else "I'm a student")
        p.tap("Create account", exact=True)  # the switch above the form; the teacher's form opens on "Log in"
        p.type_into("Your name", name)
        p.type_into("WhatsApp number", number)
        p.type_into("Password", "pilot123")
        p.type_into("Teacher code" if teacher else "Group code", code)
        p.hide_keyboard()
        p.tap("Create account", exact=True, last=True)
        time.sleep(3)

    for serial in (TEACHER, STUDENT):
        on(serial)
        p.adb("install", "-r", str(APK))
        p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
        p.demo_mode()
        p.launch(clear=True)

    recordings: list[tuple[str, p.Recording]] = []

    def record(part: str) -> None:
        """Starts recording both phones at once (screenrecord stops by itself after 3 minutes, hence parts)."""
        for serial, who in ((TEACHER, "teacher"), (STUDENT, "student")):
            on(serial)
            recordings.append((serial, p.Recording(out / f"{part}_{who}.mp4", f"/sdcard/{part}.mp4")))

    def stop_recording() -> None:
        while recordings:
            serial, rec = recordings.pop(0)
            on(serial)
            rec.stop()

    record("part1")

    # 1. Teacher signs up and sets the class link; the app already shows the server address it will use.
    on(TEACHER)
    check("teacher phone shows the server address before sign-in", server)
    shot("01_teacher_welcome_server")
    sign_up("Ramit (test)", "9800000101", teacher_code, teacher=True)
    check("teacher signed up", "Your classes")
    # A class in progress (started 47 min ago, 8 min left), so check-ins are open now.
    conn = sqlite3.connect(db_path)
    start = (datetime.now(UTC) - timedelta(minutes=47)).isoformat(timespec="seconds").replace("+00:00", "Z")
    conn.execute(
        "INSERT INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES ('pranayama', ?, 55, ?)",
        (start, start),
    )
    conn.commit()
    group_code = conn.execute("SELECT value FROM settings WHERE key = 'group_code'").fetchone()[0]
    come_back()
    p.type_into("Google Meet link", "meet.google.com/pil-otte-sta")
    p.hide_keyboard()
    p.tap("Save and share on WhatsApp")
    time.sleep(2)
    check("WhatsApp message carries the link", "meet.google.com/pil-otte-sta")
    shot("02_teacher_share")
    p.back()

    # 2. Student A signs up with the group code on the other phone and sees the link at once.
    on(STUDENT)
    sign_up("Asha (test)", "9800000102", group_code)
    check("student with group code sees the class", "Pranayama")
    shot("03_student_today")
    p.tap("Join class")
    check("before-class question appears in the check-in window", "How do you feel right now?")
    p.tap("Okay")
    time.sleep(3)
    come_back()  # from Meet in the browser, without restarting the app
    check("after-class question appears on returning to the app", "Class done! How do you feel now?")
    shot("04_student_after_class")
    p.tap("Great")
    time.sleep(2)
    p.tap("Ask", exact=True)
    p.tap("What should I eat before class?")
    check("Gemma answers the student", "From the notes", timeout=120)
    shot("05_student_ask")

    # 3. Teacher sees the check-in from the other phone.
    on(TEACHER)
    p.tap("Insights", exact=True)
    time.sleep(2)
    check("teacher sees the student's before and after", "1 joined")
    shot("06_teacher_insights")

    stop_recording()
    record("part2")

    # 4. Student B signs up without the code: pending, no link, until the teacher approves.
    on(STUDENT)
    p.tap("Me", exact=True)
    p.scroll_down()
    p.tap("Log out")
    time.sleep(1.5)
    p.tap("I'm a student")
    p.type_into("Your name", "Meera (test)")
    p.type_into("WhatsApp number", "09800000103")  # typed with a leading 0
    p.type_into("Password", "pilot123")
    p.hide_keyboard()
    p.tap("Create account", exact=True, last=True)
    time.sleep(3)
    check("student without code waits for approval", "Waiting for approval")
    shot("07_student_pending")
    on(TEACHER)
    p.tap("Students", exact=True)
    time.sleep(2)
    shot("08_teacher_students")
    p.tap("Approve", exact=True)
    time.sleep(2)
    on(STUDENT)
    come_back()
    check_gone("approved student is no longer waiting, after returning to the app", "Waiting for approval")
    shot("09_student_approved")

    stop_recording()
    side_by_side(out, LOCAL / f"two_phones_{version.removesuffix('-two-phones')}.mp4")

    passed = sum(ok for _, ok in results)
    report = ROOT / "docs" / "evals" / f"two_phones_{version.removesuffix('-two-phones')}.md"
    report.write_text(
        f"# Two-phone test: {version}\n\n"
        f"- **Server:** {server} (the laptop as seen from the emulators; an APK built with -PscaServer uses the laptop's Wi-Fi address instead)\n"
        f"- **Phones:** {TEACHER} (teacher), {STUDENT} (students), Android 16 emulators\n"
        f"- **Passed:** {passed}/{len(results)}\n\n"
        + "".join(f"- {'✅' if ok else '❌'} {what}\n" for what, ok in results)
        + f"\nTest people only. Screenshots and the recording are kept locally in .local/visualization/tours/{version}/.\n",
        encoding="utf-8",
    )
    print(f"{passed}/{len(results)} passed; {report}")


def side_by_side(out: Path, final: Path) -> None:
    """Teacher on the left, student on the right, both parts in sequence, into `final`."""
    parts = []
    for part in ("part1", "part2"):
        joined = out / f"{part}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / f"{part}_teacher.mp4"), "-i", str(out / f"{part}_student.mp4"),
             "-filter_complex", "[0:v]scale=540:-2,fps=24[a];[1:v]scale=540:-2,fps=24[b];[a][b]hstack=inputs=2:shortest=1[v]",
             "-map", "[v]", "-c:v", "libx264", "-crf", "30", "-preset", "slow", "-an", str(joined)],
            check=True,
        )
        parts.append(joined)
    listing = out / "parts.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
                    "-movflags", "+faststart", str(final)], check=True)
    for leftover in [listing, *parts, *out.glob("part*_*.mp4")]:
        leftover.unlink()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4])
