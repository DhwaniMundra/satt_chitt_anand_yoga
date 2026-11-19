"""Two phones, one server: a teacher on emulator-5554 and students on emulator-5556. Checks the loop across
devices (sign-up with the group code, the student's answers about themselves, approval into the batch they point to,
a class, a wrong code, a second approval), saves a screenshot at each step (.local/visualization/viz_<major>/screens/<version>/) and records both screens
into one side-by-side video (.local/visualization/viz_<major>/two_phones_<version>.mp4); the pass/fail list goes to
docs/evals/two_phones_<version>.md.

Needs: both emulators running (scripts/run_emulator.sh, then SCA_AVD=sca_phone_2 SCA_PORT=5556 ...), the debug APK
built, and nothing else on port 8000: the test starts the dev backend on an empty Sheet (data/two_phones.json) whose
teacher signs up with `teacher_code`. Uses test people only.

Usage: python3 scripts/two_phone_test.py v1-two-phones PILOT1
"""

import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image

import phone as p
import viz

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TEACHER, STUDENT = "emulator-5554", "emulator-5556"
SERVER = "http://10.0.2.2:8000"  # the dev backend, as the emulators see it
TEACHER_PHONE = "9800000101"
PASSWORD = "pilot123"  # every test person's


def on(serial: str) -> None:
    """Points every following adb call at one phone."""
    os.environ["ANDROID_SERIAL"] = serial


def main(version: str, teacher_code: str) -> None:
    with p.dev_backend(ROOT / "data" / "two_phones.json", demo=False, teacher_code=teacher_code):
        run(version, teacher_code)


def run(version: str, teacher_code: str) -> None:
    out = viz.screens(version)
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
        p.type_into("Password", PASSWORD)
        p.type_into("Teacher code" if teacher else "Group code", code)
        p.hide_keyboard()
        p.tap("Create account", exact=True, last=True)
        time.sleep(3)

    for serial in (TEACHER, STUDENT):
        on(serial)
        p.adb("install", "-r", str(APK))
        p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
        p.demo_mode()
        p.launch(fresh=True)

    recordings: list[tuple[str, p.Recording]] = []

    def record(part: str) -> None:
        """Starts recording both phones at once (screenrecord stops by itself after 3 minutes, hence parts)."""
        for serial, who in ((TEACHER, "teacher"), (STUDENT, "student")):
            on(serial)
            recordings.append((serial, p.Recording(viz.tours(version) / f"{part}_{who}.mp4", f"/sdcard/{part}.mp4")))

    def stop_recording() -> None:
        while recordings:
            serial, rec = recordings.pop(0)
            on(serial)
            rec.stop()

    record("part1")

    # 1. Teacher signs up and shares the class link; the app already shows the server address it will use.
    on(TEACHER)
    check("teacher phone shows the server address before sign-in", SERVER)
    shot("01_teacher_welcome_server")
    sign_up("Teacher (test)", TEACHER_PHONE, teacher_code, teacher=True)
    check("teacher signed up", "Your classes")
    p.add_class("intermediate", -47)  # under way, 8 minutes left: both check-ins are open
    token = p.call("POST", "/auth/login", body={"phone": TEACHER_PHONE, "password": PASSWORD})["token"]
    group_code = p.call("GET", "/teacher/home", token)["settings"]["group_code"]
    come_back()
    p.type_into("Google Meet link", "meet.google.com/pil-otte-sta")  # the class under way comes first
    p.hide_keyboard()
    p.tap("Save and share on WhatsApp")
    time.sleep(2)
    check("WhatsApp message carries the link", "meet.google.com/pil-otte-sta")
    check("and names the batch", "Intermediate")
    shot("02_teacher_share")
    p.back()

    # 2. Student A signs up with the group code and tells the teacher about herself, then waits to be placed.
    on(STUDENT)
    sign_up("Asha (test)", "9800000102", group_code)
    check("the intake opens after sign-up, saying first who sees it", f"These answers go to {p.TEACHER_NAME}")
    shot("03_student_intake")
    p.type_into("Age", "34")
    p.type_into("Height (cm)", "160")
    p.type_into("Weight (kg)", "58")
    p.hide_keyboard()
    p.tap("Vegetarian", exact=True)
    for pose in ("Tadasana", "Vrikshasana", "Trikonasana", "Vajrasana"):  # steady in most: Intermediate
        p.tap_under(pose, "Steady")
    for _ in range(12):
        try:
            p.find(f"Send to {p.TEACHER_NAME}", timeout=1, exact=True)
            break
        except TimeoutError:
            p.scroll_down()
    shot("04_student_intake_sent")
    p.tap(f"Send to {p.TEACHER_NAME}", exact=True)
    check("the answers are sent", f"{p.TEACHER_NAME} will place you soon")
    check("then she waits to be placed", "Waiting for")

    # 3. The teacher sees her answers and approves her into the batch they point to.
    on(TEACHER)
    p.tap("Students", exact=True)
    time.sleep(2)
    check("teacher sees the answers and the batch they point to", "Suggested: Intermediate")
    shot("05_teacher_students")
    p.tap("Approve into Intermediate", exact=True)
    time.sleep(2)

    # 4. Student A, placed, joins the class and says how it went.
    on(STUDENT)
    come_back()
    check("the placed student sees her batch", "Your batch: Intermediate")
    shot("06_student_today")
    p.tap("Join class")
    check("before-class question appears in the check-in window", "How do you feel right now?")
    p.tap("Okay")
    time.sleep(3)
    come_back()  # from Meet in the browser, without restarting the app
    p.tap(f"Tell {p.TEACHER_NAME}")
    check("after-class question appears on returning to the app", "Class done! How do you feel now?")
    p.tap("Great")
    p.tap_under("Sectional", "Steady")
    for _ in range(12):
        try:
            p.find("Done", timeout=1, exact=True)
            break
        except TimeoutError:
            p.scroll_down()
    p.tap("Done", exact=True)
    check("the answers are kept", f"You told {p.TEACHER_NAME} how it went")
    shot("07_student_after_class")
    p.tap("Ask", exact=True)
    check("a 2 GB phone says chat needs more memory", "Cloud model support coming soon")
    shot("08_student_ask")

    # 5. Teacher sees the check-in from the other phone.
    on(TEACHER)
    p.tap("Insights", exact=True)
    time.sleep(2)
    check("teacher sees the student's before and after", "1 joined")
    shot("09_teacher_insights")

    stop_recording()
    record("part2")

    # 6. Student B: a wrong code is refused; with the code, she waits until the teacher places her.
    on(STUDENT)
    p.tap("Me", exact=True)
    for _ in range(8):
        try:
            p.find("Log out", timeout=1)
            break
        except TimeoutError:
            p.scroll_down()
    p.tap("Log out")
    time.sleep(1.5)
    sign_up("Meera (test)", "09800000103", "WRONG1")  # the number typed with a leading 0
    check("a wrong group code is refused", f"Ask {p.TEACHER_NAME} for the group code")
    shot("10_student_wrong_code")
    p.tap("WRONG1", exact=True)  # the code box, still filled: emptied, then the right code
    p.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(len("WRONG1")):
        p.adb("shell", "input", "keyevent", "KEYCODE_DEL")
    p.type_text(group_code)
    p.hide_keyboard()
    p.tap("Create account", exact=True, last=True)
    time.sleep(3)
    check("with the code, she is asked about herself", f"These answers go to {p.TEACHER_NAME}")
    p.tap("Back", exact=True)  # the intake's back arrow: she can answer later, from Me
    check("and waits to be placed", "Waiting for")
    on(TEACHER)
    p.tap("Students", exact=True)
    time.sleep(2)
    shot("11_teacher_students")
    p.tap("Approve into Beginner", exact=True)  # no answers yet: Beginner is preselected
    time.sleep(2)
    on(STUDENT)
    come_back()
    check_gone("the placed student leaves the waiting card, after returning to the app", "Waiting for")
    shot("12_student_placed")

    stop_recording()
    side_by_side(viz.tours(version), f"two_phones_{version.removesuffix('-two-phones')}.mp4")

    passed = sum(ok for _, ok in results)
    report = ROOT / "docs" / "evals" / f"two_phones_{version.removesuffix('-two-phones')}.md"
    report.write_text(
        f"# Two-phone test: {version}\n\n"
        f"- **Server:** the dev backend at {SERVER} (the laptop as the emulators see it)\n"
        f"- **Phones:** {TEACHER} (teacher), {STUDENT} (students), Android 16 emulators\n"
        f"- **Passed:** {passed}/{len(results)}\n\n"
        + "".join(f"- {'✅' if ok else '❌'} {what}\n" for what, ok in results)
        + f"\nTest people only. Screenshots and the recording are kept locally in .local/visualization/{viz.folder(version).name}/"
        " (screens/ and tours/).\n",
        encoding="utf-8",
    )
    print(f"{passed}/{len(results)} passed; {report}")


def side_by_side(out: Path, name: str) -> None:
    """Teacher on the left, student on the right, both parts (recorded into `out`) in sequence, into `out` / `name`."""
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
                    "-movflags", "+faststart", str(out / name)], check=True)
    for leftover in [listing, *parts, *out.glob("part*_*.mp4")]:
        leftover.unlink()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
