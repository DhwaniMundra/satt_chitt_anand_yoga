"""Two phones, one server and no WhatsApp on either: a teacher on emulator-5554 and students on emulator-5556, through
the whole loop. The teacher signs up, sets each batch's everyday Meet link (never a WhatsApp group link) and shares a
class through Android's share sheet. Two students sign up with the group code and tell the teacher about themselves, one
with pain, and the teacher places each in the batch their answers point to. Asha joins the class, says how she feels
before it and how each item went after it, with a strain on one; the teacher reads the class on Insights and in its
review, strain first, and writes to her about that asana, which she reads in its history. She practises on her own with
the stopwatch and shares a health note. The teacher moves Meera to another batch with a note and gives her a new
password; a new group code turns the old one away from a third sign-up; and both sign out and in again, their data
still there.

Each step saves a screenshot (.local/visualization/viz_<major>/screens/<version>/), and a check that fails saves the
screen and its UI dump beside them (fail_<n>.png and .xml). The debug build's run is recorded from both screens into
one side-by-side video (viz_<major>/tours/two_phones_<version>.mp4). With --release, the same loop runs again on a
release build (shrunk by R8) pointed at the dev backend, its screenshots named release_*. The pass/fail list goes to
docs/evals/two_phones_<version>.md.

Needs: both emulators running (scripts/run_emulator.sh, then SCA_AVD=sca_phone_2 SCA_PORT=5556 ...), the debug APK
built, and nothing else on port 8000: each build's run starts the dev backend on an empty Sheet
(data/two_phones_<build>.json) whose teacher signs up with `teacher_code`. Uses test people only (98000001xx).

Usage:
  python3 scripts/two_phone_test.py v0.9-two-phones PILOT1
  python3 scripts/two_phone_test.py v0.9-two-phones PILOT1 --release android/app/build/outputs/apk/release/app-release.apk
The release APK for the emulator: in android/, ./gradlew assembleRelease -PscaServer=http://10.0.2.2:8000 -Pabi=x86_64
-Psigning=<the properties file of any key, as scripts/build_app.sh writes one>.
"""

import argparse
import contextlib
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

import phone as p
import viz

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
TEACHER, STUDENT = "emulator-5554", "emulator-5556"
PHONES = (TEACHER, STUDENT)
SERVER = "http://10.0.2.2:8000"  # the dev backend, as the emulators see it
IST = timezone(timedelta(hours=5, minutes=30))
T = p.TEACHER_NAME
PASSWORD = "pilot123"  # every test person's, until the teacher gives one a new password
TEACHER_PHONE, ASHA, MEERA, KAVYA = "9800000101", "9800000102", "9800000103", "9800000104"
BATCHES = {b["key"]: b for b in json.loads((ROOT / "content" / "studio.json").read_text(encoding="utf-8"))["batches"]}
LINKS = {"beginner": "meet.google.com/beg-ginn-ers", "intermediate": "meet.google.com/int-erme-dia",
         "advanced": "meet.google.com/adv-ance-dyo", "pain_management": "meet.google.com/pai-nman-age"}  # everyday links
CLASS_LINK = "meet.google.com/pil-otte-sta"  # the shared class's own
FEEDBACK = "Keep the hips low today; lift only as far as the back allows."
NOTE = "Right knee clicks when I kneel"
MOVE_NOTE = "Steady in the standing poses; ready for longer holds"
BUILDS = {"debug": "Debug build (app-debug.apk)",
          "release": "Release build (R8-shrunk, x86_64, built with -PscaServer=http://10.0.2.2:8000 -Pabi=x86_64)"}


def on(serial: str) -> None:
    """Points every following adb call at one phone."""
    os.environ["ANDROID_SERIAL"] = serial


class Run:
    """One build's pass through the loop: its checks so far, and where its screenshots go."""

    def __init__(self, build: str, out: Path) -> None:
        self.build = build
        self.out = out
        self.prefix = "" if build == "debug" else build + "_"
        self.results: list[tuple[str, bool, str]] = []

    def shot(self, name: str) -> None:
        full = self.out / f"{self.prefix}{name}.png"
        p.screenshot(full)
        image = Image.open(full).convert("RGB")
        image.resize((image.width // 2, image.height // 2), Image.LANCZOS).save(full, optimize=True)

    def verdict(self, what: str, ok: bool, detail: str = "") -> bool:
        """Records a check; one that failed keeps the screen and its UI dump, and names them in `detail`."""
        if not ok:
            name = f"{self.prefix}fail_{len(self.results) + 1:02d}"
            p.screenshot(self.out / f"{name}.png")
            with contextlib.suppress(subprocess.CalledProcessError, ValueError):
                (self.out / f"{name}.xml").write_text(p.hierarchy(), encoding="utf-8")
            detail = f"{detail}; {name}.png".lstrip("; ")
        self.results.append((what, ok, detail))
        print(("PASS " if ok else "FAIL ") + what + ("" if ok else f" ({detail})"), flush=True)
        return ok

    def check(self, what: str, text: str, timeout: float = 20, exact: bool = False, scroll: bool = False) -> bool:
        """That `text` shows on screen (with `scroll`, anywhere on the page, from its top)."""
        try:
            if scroll:
                p.scroll_to_top()
                p.find_scrolling(text, exact)
            else:
                p.find(text, timeout=timeout, exact=exact)
            return self.verdict(what, True)
        except TimeoutError:
            return self.verdict(what, False, f"'{text}' never showed")

    def check_gone(self, what: str, text: str) -> bool:
        time.sleep(2)
        try:
            p.find(text, timeout=3)
            return self.verdict(what, False, f"'{text}' is on screen")
        except TimeoutError:
            return self.verdict(what, True)

    @contextlib.contextmanager
    def part(self, name: str):
        """A part of the loop. A step in it that cannot go on (a button missing, say) is a failed check; then both
        apps start again, still signed in, and the loop goes on with the next part."""
        try:
            yield
        except Exception as e:  # noqa: BLE001 (any of them stops only this part)
            self.verdict(f"{name}: carried through", False, f"{type(e).__name__}: {e}"[:300])
            for serial in PHONES:
                on(serial)
                p.launch()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version")
    parser.add_argument("teacher_code")
    parser.add_argument("--release", type=Path, help="a release APK for the emulator, to run the loop on as well")
    args = parser.parse_args()
    builds = [("debug", APK)] + ([("release", args.release.resolve())] if args.release else [])
    short = args.version.removesuffix("-two-phones")
    out = viz.fresh_screens(args.version)  # swapped in for screens/<version>/ at the end of a run that finishes
    started = datetime.now(IST)
    runs = []
    for build, apk in builds:
        run = Run(build, out)
        runs.append(run)
        with p.dev_backend(ROOT / "data" / f"two_phones_{build}.json", demo=False, teacher_code=args.teacher_code):
            for serial in PHONES:
                on(serial)
                p.install(apk)
                p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
                p.demo_mode()
                p.launch(fresh=True)
            video = SideBySide(viz.tours(args.version)) if build == "debug" else None
            try:
                loop(run, args.teacher_code, debug=build == "debug")
            finally:
                if video:
                    video.save(f"two_phones_{short}.mp4")
    report = ROOT / "docs" / "evals" / f"two_phones_{short}.md"
    report.write_text(summary(args.version, runs, started), encoding="utf-8")
    viz.keep_screens(args.version)
    for run in runs:
        print(f"{run.build}: {sum(ok for _, ok, _ in run.results)}/{len(run.results)} passed")
    print(report)


def loop(run: Run, teacher_code: str, debug: bool) -> None:
    for serial, whose in ((TEACHER, "the teacher's"), (STUDENT, "the students'")):
        on(serial)
        whatsapp = [line for line in p.adb("shell", "pm", "list", "packages").split() if "whatsapp" in line.lower()]
        run.verdict(f"no WhatsApp on {whose} phone (pm list packages)", not whatsapp, ", ".join(whatsapp))

    # 1. The teacher signs up and sees the day's classes, a card for each batch's class.
    with run.part("the teacher signs up"):
        on(TEACHER)
        if debug:  # a release build has no server box
            run.check("teacher phone shows the server address before sign-in", SERVER)
        run.shot("01_teacher_welcome")
        sign_up("Teacher (test)", TEACHER_PHONE, teacher_code, teacher=True)
        run.check("teacher signed up", "Your classes")
        token = api_login(TEACHER_PHONE)
        home = p.call("GET", "/teacher/home?lang=en", token)
        code = home["settings"]["group_code"]
        day = [s["batch"]["name"] for s in home["sessions"]]
        cards = class_cards()
        run.verdict(f"the Today tab has a card for each of the day's classes, one per batch ({len(day)} at "
                    f"{datetime.now(IST):%H:%M} India time: {', '.join(day)})", cards == day and len(set(day)) == len(day),
                    f"cards {cards}, the day's classes {day}")
        run.shot("02_teacher_today")

    # 2. Each batch's everyday Meet link; the WhatsApp group link is never set.
    with run.part("the teacher sets each batch's everyday Meet link"):
        for key, link in LINKS.items():
            p.find_scrolling(link_box(key))
            p.type_into(link_box(key), link)
        p.hide_keyboard()
        p.tap_scrolling("Save", exact=True)
        run.check("the everyday links are saved", "Saved")
        run.shot("03_teacher_links")
        home = p.call("GET", "/teacher/home?lang=en", token)
        saved = {b["key"]: b["meet_link"] for b in home["batches"]}
        run.verdict("each batch keeps its everyday link", saved == {k: "https://" + v for k, v in LINKS.items()}, str(saved))
        run.verdict("and the WhatsApp group link stays unset", home["settings"]["group_link"] is None, str(home["settings"]))
        run.check("the day's classes now use their batch's everyday link", "Using the batch's everyday link", scroll=True)

    # 3. Asha signs up with the group code and tells the teacher about herself, with pain in the knee.
    with run.part("Asha signs up and answers about herself"):
        on(STUDENT)
        sign_up("Asha (test)", ASHA, code)
        run.check("the intake opens after sign-up, saying first who sees it", f"These answers go to {T}")
        run.shot("04_student_intake")
        fill_intake("34", "160", "58", "Vegetarian", ["Knee"], "Right knee aches on the stairs",
                    [("Tadasana", "Steady"), ("Vajrasana", "With effort")])
        run.shot("05_student_intake_pain")
        p.tap_scrolling(f"Send to {T}", exact=True)
        run.check("the answers are sent", f"{T} will place you soon")
        run.check("then she waits to be placed", "Waiting for")
        log_out("Me")

    # 4. Meera: a wrong code is refused; with the code she answers later, from the waiting card: no pain, two easy poses.
    with run.part("Meera signs up and answers about herself"):
        sign_up("Meera (test)", "0" + MEERA, "WRONG1")  # the number typed with a leading 0
        run.check("a wrong group code is refused", f"Ask {T} for the group code")
        run.shot("06_student_wrong_code")
        retype("WRONG1", code, exact=True)
        p.hide_keyboard()
        p.tap("Create account", exact=True, last=True)
        time.sleep(3)
        run.check("with the code, she is asked about herself", f"These answers go to {T}")
        p.tap("Back", exact=True)  # the intake's back arrow: she can answer later
        run.check("and waits to be placed", "Waiting for")
        p.tap(f"Tell {T} about yourself")
        fill_intake("29", "155", "50", "Eggetarian", [], "", [("Tadasana", "At ease"), ("Vrikshasana", "Steady")])
        p.tap_scrolling(f"Send to {T}", exact=True)
        run.check("her answers are sent from the waiting card", f"{T} will place you soon")

    # 5. The teacher sees both, with their answers and the batch each points to, and approves them.
    with run.part("the teacher places both students"):
        on(TEACHER)
        tab("Students")
        time.sleep(2)
        run.check("teacher sees Meera's answers", "29 yrs · 155 cm · 50 kg · Eggetarian", scroll=True)
        run.check("and the batch they point to: Beginner, for no pain and two easy poses", "Suggested: Beginner", scroll=True)
        run.shot("07_teacher_students")
        run.check("teacher sees Asha's answers, with her pain", "Pain: Knee", scroll=True)
        run.check("teacher sees the answers and the batch they point to: Pain management", "Suggested: Pain management",
                  scroll=True)
        run.shot("08_teacher_students_pain")
        p.scroll_to_top()
        p.tap_scrolling("Approve into Beginner", exact=True)  # what her answers point to is chosen already
        time.sleep(2)
        p.scroll_to_top()
        p.tap_scrolling("Approve into Pain management", exact=True)
        time.sleep(2)
        placed = {u["name"]: (u["status"], u["batch"]) for u in p.call("GET", "/teacher/students", token)["students"]}
        run.verdict("teacher approves each into the batch suggested", placed == {
            "Meera (test)": ("approved", "beginner"), "Asha (test)": ("approved", "pain_management")}, str(placed))
        p.scroll_to_top()
        run.shot("09_teacher_placed")

    # 6. Each student's Today tab: the batch, the next class and its link; with no group link, no WhatsApp button.
    with run.part("the students' Today tab"):
        on(STUDENT)
        come_back()
        run.check_gone("the placed student leaves the waiting card, after returning to the app", "Waiting for")
        run.check("the placed student sees her batch", "Your batch: Beginner")
        today_tab(run, "Meera")
        run.shot("10_student_today")
        joins(run, "Join class opens the class's Meet link, in the browser as there is no Meet app")
        mine = p.call("GET", "/home?lang=en", api_login(MEERA))["sessions"][0]
        run.verdict("her next class carries her batch's everyday link", (mine["batch"]["key"], mine["meet_link"]) == (
            "beginner", "https://" + LINKS["beginner"]), f"{mine['batch']['key']}: {mine['meet_link']}")
        log_out("Me")
        log_in(ASHA)
        run.check("Asha, placed, sees her batch", "Your batch: Pain management")
        today_tab(run, "Asha")
        mine = p.call("GET", "/home?lang=en", api_login(ASHA))["sessions"][0]
        run.verdict("her next class carries her batch's everyday link", (mine["batch"]["key"], mine["meet_link"]) == (
            "pain_management", "https://" + LINKS["pain_management"]), f"{mine['batch']['key']}: {mine['meet_link']}")
        run.shot("11_student_a_today")

    # 7. The teacher shares a class with its own link. With no WhatsApp the share sheet opens; dismissed, the link stays.
    with run.part("the teacher shares a class"):
        on(TEACHER)
        tab("Today")
        staged = p.add_class("pain_management", -47)  # under way, 8 minutes left: both check-ins are open
        come_back()
        first = p.call("GET", "/teacher/home?lang=en", token)["sessions"][0]
        if first["id"] != staged:  # a class that began earlier is still on, and its card is the open one
            starts = next(s for s in p.call("GET", "/teacher/home?lang=en", token)["sessions"] if s["id"] == staged)["starts_at"]
            p.scroll_to_top()
            p.tap_scrolling(f"Today · {clock(starts)}", exact=True)
        p.find_scrolling("Google Meet link")
        p.type_into("Google Meet link", CLASS_LINK)
        p.hide_keyboard()
        p.tap("Save and share on WhatsApp")
        time.sleep(2)
        run.verdict("with no WhatsApp, Save and share opens Android's share sheet",
                    p.resumed().startswith("com.android.intentresolver/"), p.resumed())
        run.check("WhatsApp message carries the link", CLASS_LINK)
        run.check("and names the batch", "Pain management")
        run.shot("12_teacher_share_sheet")
        p.back()  # dismissed, shared with no one
        run.verdict("the share sheet is dismissed, back in the app", p.resumed().endswith("/.MainActivity"), p.resumed())
        run.check("the link is still saved, on the class's card", "https://" + CLASS_LINK, scroll=True)
        session = next(s for s in p.call("GET", "/teacher/home?lang=en", token)["sessions"] if s["id"] == staged)
        run.verdict("and on the server, as the class's own link", session["own_link"] and session["meet_link"] == "https://"
                    + CLASS_LINK, str(session["meet_link"]))
        run.shot("13_teacher_link_saved")

    # 8. Asha checks in before the class with a mood; after it, a reaction per item, a strain on one, and a note.
    with run.part("Asha's class"):
        on(STUDENT)
        come_back()
        run.check("the shared class is her next, under way", "Live now")
        p.clear_log()
        p.tap("Join class")
        run.check("before-class question appears in the check-in window", "How do you feel right now?")
        p.tap("Okay")
        time.sleep(3)
        run.verdict("checked in, Join opens the class's Meet link", any(link.startswith("https://meet.google.com/") for link in
                                                                         p.opened()), str(p.opened()))
        mine = p.call("GET", "/home?lang=en", api_login(ASHA))["sessions"][0]
        run.verdict("the link she is given is the one the teacher shared", (mine["id"], mine["meet_link"], mine["checked_in"])
                    == (staged, "https://" + CLASS_LINK, True), f"{mine['id']}: {mine['meet_link']}, checked in {mine['checked_in']}")
        come_back()  # from Meet in the browser, without restarting the app
        p.adb("shell", "am", "force-stop", "com.android.chrome")
        p.tap(f"Tell {T}")
        run.check("after-class question appears on returning to the app", "Class done! How do you feel now?")
        p.tap("Great")
        p.tap_under("Sectional", "Steady")
        p.tap_under("Pavanamuktasana", "At ease")
        p.tap_under("Setu Bandhasana", "With effort")
        p.tap_under("Setu Bandhasana", "Felt strain or pain")
        p.tap_under("Setu Bandhasana", "Add a note")
        p.type_under("Setu Bandhasana", "Lower back pinched lifting the hips")
        p.tap_under("Makarasana", "Steady")
        run.shot("14_student_after_class")
        p.tap_scrolling("Done", exact=True)
        run.check("the answers are kept", f"You told {T} how it went")
        run.shot("15_student_told")
        tab("Ask")
        run.check("a 2 GB phone says chat needs more memory", "Cloud model support coming soon")
        run.shot("16_student_ask")

    # 9. The teacher sees the class on Insights and in its review, strain first.
    with run.part("the teacher reads the class"):
        on(TEACHER)
        tab("Insights")
        time.sleep(2)
        run.check("teacher sees the student's before and after", "1 joined")
        run.shot("17_teacher_insights")
        p.tap_scrolling("How each item went")
        run.check("the class review opens", "How the class went")
        run.check("with her strain, her name and her note", "Felt strain or pain: Asha (test)")
        items = ("Vibhagiya", "Pavanamuktasana", "Setu Bandhasana", "Makarasana")
        top = next((item for text in labels() for item in items if item in text), None)
        run.verdict("strain or pain first: Setu Bandhasana leads, ahead of the class's order", top == "Setu Bandhasana",
                    f"first item: {top}")
        run.shot("18_teacher_class_review")
        p.back()

    # 10. The teacher writes to Asha about that asana; she reads it in its history on the Practice tab.
    with run.part("the teacher's word on one asana"):
        tab("Students")
        time.sleep(2)
        p.tap_under("Asha (test)", "How each item has gone ›")
        time.sleep(2)
        p.tap_scrolling("Setu Bandhasana")
        time.sleep(2)
        p.type_into("Write to Asha", FEEDBACK)
        p.hide_keyboard()
        p.tap("Send", exact=True)
        run.check("the teacher's word on one asana is sent", "YOU WROTE")
        run.shot("19_teacher_feedback")
        p.back()
        p.back()
        on(STUDENT)
        tab("Practice")
        time.sleep(2)
        run.check("her Practice tab shows the teacher wrote", f"{T} wrote", scroll=True)
        p.scroll_to_top()
        p.tap_scrolling("Setu Bandhasana")
        run.check("and she reads it in that asana's history", FEEDBACK[:40])
        run.shot("20_student_item_history")
        p.back()

    # 11. A practice on her own with the stopwatch, saved; it shows on the Practice tab.
    with run.part("Asha practises on her own"):
        p.scroll_to_top()
        p.tap("Practise on your own")
        p.type_into("Search by name", "vajra")
        p.tap("+ Vajrasana")
        p.hide_keyboard()
        p.tap_scrolling("Start (1)", exact=True)
        p.tap("Start the stopwatch")
        time.sleep(12)
        p.tap("Stop", exact=True)
        p.tap("Steady", exact=True)
        p.type_into("Add a note", "Cushion under the ankles")
        p.hide_keyboard()
        run.shot("21_student_solo")
        p.tap_scrolling("Finish", exact=True)
        run.check("the practice on her own is saved", "Saved to your practice")
        run.check("and shows on the Practice tab", "Solo practice · 1 min", scroll=True)
        run.shot("22_student_practice")
        p.scroll_to_top()
        p.tap_scrolling("Vajrasana")
        run.check("with the hold the stopwatch timed, in Vajrasana's history", "Solo · held 0:1")
        p.back()

    # 12. A health note shared from the Me tab; the teacher sees it.
    with run.part("Asha shares a health note"):
        tab("Me")
        p.type_into("For example: my left knee", NOTE)
        p.hide_keyboard()
        p.tap("Save", exact=True)
        p.tap(f"Share with {T}")
        p.tap("Share", exact=True)  # in the dialog that asks first
        run.check("the note is shared", f"Shared with {T}")
        run.shot("23_student_note_shared")
        on(TEACHER)
        tab("Students")
        time.sleep(2)
        run.check("the teacher sees the shared health note", NOTE)
        run.shot("24_teacher_shared_note")

    # 13. Meera moved to another batch, with a note; then a new password, which signs her out everywhere.
    with run.part("the teacher moves Meera"):
        p.tap_under("Meera (test)", "Move to batch")
        p.tap_under("Meera (test)", "Intermediate")
        p.type_under("Meera (test)", MOVE_NOTE)
        run.shot("25_teacher_move")
        p.tap_under("Meera (test)", "Move to Intermediate")
        time.sleep(2)
        moved = next(u for u in p.call("GET", "/teacher/students", token)["students"] if u["name"] == "Meera (test)")
        run.verdict("Meera is moved to Intermediate", moved["batch"] == "intermediate", str(moved["batch"]))
        run.check("her card shows the new batch", "Intermediate · since", scroll=True)
    with run.part("the teacher gives Meera a new password"):
        p.scroll_to_top()
        p.tap_under("Meera (test)", "New password")
        run.check("the teacher is asked first", "New password for Meera (test)?")
        p.tap_under("New password for Meera (test)?", "New password")
        shown = p.label(p.find("New password for Meera (test):"))
        new_password = shown.rsplit(": ", 1)[1].strip()
        run.shot("26_teacher_new_password")
        p.tap("OK", exact=True)

    # 14. Meera: the old password fails, the new one works; her new batch, its class and the teacher's note.
    with run.part("Meera signs in again"):
        on(STUDENT)
        log_out("Me")
        log_in(MEERA)
        run.check("the old password fails", "Wrong number or password.")
        run.shot("27_student_old_password")
        retype("Password", new_password)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)
        time.sleep(3)
        run.check("the new password works", "Namaste, Meera")
        run.check("she sees her new batch", "Your batch: Intermediate")
        run.check("and its class", "Intermediate", exact=True)
        page = labels(whole_page=True)
        run.verdict("and the teacher's note on the move", any(MOVE_NOTE[:24] in text for text in page),
                    "the note shows nowhere on her Today tab")
        run.shot("28_student_moved")

    # 15. A new group code; the invite opens the share sheet. The old code is turned away from a third sign-up.
    with run.part("the teacher makes a new group code"):
        on(TEACHER)
        tab("Today")
        old_code = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_code"]
        p.tap_scrolling("New code", exact=True)
        time.sleep(2)
        new_code = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_code"]
        run.verdict("a new group code is made", new_code != old_code, f"{old_code} -> {new_code}")
        run.check("and shown", new_code, exact=True)
        p.tap_scrolling("Invite students on WhatsApp")
        time.sleep(2)
        run.verdict("with no WhatsApp, the invite opens Android's share sheet", p.resumed().startswith("com.android.intentresolver/"),
                    p.resumed())
        run.check("the invite carries the new code", f"*{new_code}*")
        run.shot("29_teacher_invite")
        p.back()
        run.verdict("the share sheet is dismissed, back in the app", p.resumed().endswith("/.MainActivity"), p.resumed())
    with run.part("a third student signs up"):
        on(STUDENT)
        log_out("Me")
        sign_up("Kavya (test)", KAVYA, old_code)
        run.check("the old group code is refused", f"Ask {T} for the group code")
        run.shot("30_student_old_code")
        retype(old_code, new_code, exact=True)
        p.hide_keyboard()
        p.tap("Create account", exact=True, last=True)
        time.sleep(3)
        run.check("the new code works for a third sign-up", f"These answers go to {T}")
        p.tap("Back", exact=True)
        run.check("and she waits to be placed", "Waiting for")
        run.shot("31_student_third")

    # 16. Both sign out and in again; what they did is still there.
    with run.part("the teacher signs out and in"):
        on(TEACHER)
        log_out("Today")
        log_in(TEACHER_PHONE, teacher=True)
        run.check("teacher signed in again", "Your classes")
        run.check("the new student waits for her", "1 student waiting for your approval")
        run.check("the everyday links are still set", "https://" + LINKS["pain_management"], scroll=True)
        tab("Students")
        time.sleep(2)
        for name in ("Kavya (test)", "Meera (test)", "Asha (test)"):
            run.check(f"{name.split()[0]} is still on the Students tab", name, scroll=True)
        run.check("and the note Asha shared", NOTE, scroll=True)
        tab("Insights")
        time.sleep(2)
        run.check("and the class on the Insights tab", "1 joined")
        run.shot("32_teacher_signed_in_again")
    with run.part("Asha signs out and in"):
        on(STUDENT)
        log_out("Me")
        log_in(ASHA)
        run.check("Asha signed in again, in her batch", "Your batch: Pain management")
        tab("Practice")
        time.sleep(2)
        run.check("her practice on her own is still there", "Solo practice · 1 min", scroll=True)
        run.check("and the teacher's word", f"{T} wrote", scroll=True)
        tab("Me")
        run.check("her health note, kept on this phone, is still there", NOTE, scroll=True)
        run.check("marked shared", f"✓ Shared with {T}", scroll=True)
        run.shot("33_student_signed_in_again")


# ---- steps ----

def come_back() -> None:
    """Home, then back to the running app, as a person returning from Meet or the share sheet would."""
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


def log_in(number: str, password: str = PASSWORD, teacher: bool = False) -> None:
    p.tap("I'm the teacher" if teacher else "I'm a student")
    p.tap("Log in", exact=True)
    p.type_into("WhatsApp number", number)
    p.type_into("Password", password)
    p.hide_keyboard()
    p.tap("Log in", exact=True, last=True)  # the button under the form, not the switch above it
    time.sleep(3)


def tab(name: str) -> None:
    """Taps a tab, the lowest of the words on screen: a screen's heading may have them too (Students)."""
    p.tap(name, exact=True, last=True)


def log_out(screen: str) -> None:
    tab(screen)
    p.tap_scrolling("Log out")
    time.sleep(1.5)


def retype(box: str, value: str, exact: bool = False) -> None:
    """Empties the filled text box showing `box` (its words, or its label) and types `value` into it."""
    p.tap(box, exact=exact)
    p.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END", *["KEYCODE_DEL"] * 24)
    p.type_text(value)


def fill_intake(age: str, height: str, weight: str, food: str, pain: list[str], pain_note: str,
                poses: list[tuple[str, str]]) -> None:
    """The answers about oneself, down to the button that sends them: the pain areas, and how each pose in `poses` went."""
    p.type_into("Age", age)
    p.type_into("Height (cm)", height)
    p.type_into("Weight (kg)", weight)
    p.hide_keyboard()
    p.tap_scrolling(food, exact=True)
    for area in pain:
        p.tap_scrolling(area, exact=True)
    if pain_note:
        p.find_scrolling("What hurts, and when")
        p.type_into("What hurts, and when", pain_note)
        p.hide_keyboard()
    for pose, reaction in poses:
        p.tap_under(pose, reaction)
    p.find_scrolling(f"Send to {T}", exact=True)


def today_tab(run: Run, who: str) -> None:
    """A placed student's Today tab, all of it: the next class with a link to join, nothing missing or failed, and with
    no group link set, no button for a WhatsApp group."""
    page = labels(whole_page=True)
    run.check("her next class, with its Meet link to join", "Join class")
    run.verdict(f"with no group link set, {who}'s Today tab has no 'Open WhatsApp group' button",
                "Open WhatsApp group" not in page, "the button shows")
    wanted = ["NEXT CLASS", "Join class", "Your first class is free."]
    wrong = ["Something went wrong.", "This could not be loaded.", "The class link will appear here before class.", "Loading…"]
    missing = [w for w in wanted if w not in page] + [w for w in wrong if any(w in text for text in page)]
    run.verdict("and nothing on it is broken or empty: the next class to join, its sequence, the studio, no error",
                not missing, f"missing or wrong: {missing}")


def joins(run: Run, what: str) -> None:
    """Taps Join class (skipping the mood, if the check-in is open), checks that a Meet link opened, and comes back."""
    p.scroll_to_top()
    p.clear_log()
    p.tap("Join class")
    with contextlib.suppress(TimeoutError):
        p.tap("Skip", exact=True, timeout=4)
    time.sleep(3)
    run.verdict(what, any(link.startswith("https://meet.google.com/") for link in p.opened()), str(p.opened()))
    come_back()
    p.adb("shell", "am", "force-stop", "com.android.chrome")


# ---- reading the screen and the server ----

def labels(whole_page: bool = False) -> list[str]:
    """The words on screen, top to bottom; with `whole_page`, all of the page's, scrolling through it once from its top."""
    if not whole_page:
        return [p.label(n) for n, _ in p.nodes() if p.label(n)]
    p.scroll_to_top()
    seen: list[str] = []
    for _ in range(12):
        new = [text for text in labels() if text not in seen]
        if not new:
            break
        seen += new
        p.scroll_down()
    p.scroll_to_top()
    return seen


def class_cards() -> list[str]:
    """The batch of each class card on the teacher's Today tab, top to bottom: a card shows its day and time
    ("Today · 7:00 AM"), then its batch."""
    names = {b["name"]["en"] for b in BATCHES.values()}
    p.scroll_to_top()
    cards: list[tuple[str, str]] = []
    for _ in range(12):
        texts = labels()
        cards += [(when, name) for when, name in zip(texts, texts[1:])
                  if re.search(r" · \d{1,2}:\d\d [AP]M$", when) and name in names and (when, name) not in cards]
        if "CLASS LINKS AND GROUP" in texts:
            break
        p.scroll_down()
    p.scroll_to_top()
    return [name for _, name in cards]


def link_box(batch: str) -> str:
    """The label of a batch's everyday-link box on the teacher's Today tab: "Beginner · 07:00"."""
    return f"{BATCHES[batch]['name']['en']} · {BATCHES[batch]['time']}"


def clock(iso: str) -> str:
    """A moment as the app shows the time of day, in India: "6:13 AM"."""
    at = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(IST)
    return f"{at.hour % 12 or 12}:{at.minute:02d} {'AM' if at.hour < 12 else 'PM'}"


def api_login(number: str, password: str = PASSWORD) -> str:
    """A token of the test person with this number, from the dev backend: to read what the server gives them."""
    return p.call("POST", "/auth/login", body={"phone": number, "password": password})["token"]


# ---- the recording and the report ----

class SideBySide:
    """Both screens recorded at once in parts that start together (screenrecord stops by itself after 3 minutes), each
    pulled into `out` as it ends; save() sets them side by side, the teacher on the left, into one video."""

    PART_S = 170

    def __init__(self, out: Path) -> None:
        self.out = out
        out.mkdir(parents=True, exist_ok=True)
        self.parts = 0
        self.stopping = threading.Event()
        self.thread = threading.Thread(target=self.record, daemon=True)
        self.thread.start()

    def start(self, part: int) -> list[subprocess.Popen]:
        return [subprocess.Popen(["adb", "-s", serial, "shell", "screenrecord", "--bit-rate", "4000000", "--time-limit",
                                  str(self.PART_S), f"/sdcard/part{part}.mp4"]) for serial in PHONES]

    def record(self) -> None:
        recording = self.start(0)
        while True:
            while any(r.poll() is None for r in recording) and not self.stopping.wait(0.5):
                pass
            stopped = self.stopping.is_set()
            if stopped:
                for serial in PHONES:
                    subprocess.run(["adb", "-s", serial, "shell", "pkill", "-INT", "screenrecord"], capture_output=True)
                for r in recording:
                    r.wait(timeout=20)
                time.sleep(1.5)
            else:
                following = self.start(self.parts + 1)  # first, so the next part follows on with no gap
            for serial, who in zip(PHONES, ("teacher", "student")):
                remote = f"/sdcard/part{self.parts}.mp4"
                subprocess.run(["adb", "-s", serial, "pull", remote, str(self.out / f"part{self.parts}_{who}.mp4")], capture_output=True)
                subprocess.run(["adb", "-s", serial, "shell", "rm", remote], capture_output=True)
            self.parts += 1
            if stopped:
                return
            recording = following

    def save(self, name: str) -> None:
        self.stopping.set()
        self.thread.join()
        joined = []
        for part in range(self.parts):
            teacher, student = (self.out / f"part{part}_{who}.mp4" for who in ("teacher", "student"))
            if not (teacher.exists() and student.exists()):
                continue
            joined.append(self.out / f"part{part}.mp4")
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(teacher), "-i", str(student), "-filter_complex",
                 "[0:v]scale=540:-2,fps=24[a];[1:v]scale=540:-2,fps=24[b];[a][b]hstack=inputs=2:shortest=1[v]",
                 "-map", "[v]", "-c:v", "libx264", "-crf", "30", "-preset", "slow", "-an", str(joined[-1])],
                check=True,
            )
        listing = self.out / "parts.txt"
        listing.write_text("".join(f"file '{part.name}'\n" for part in joined))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing), "-c", "copy",
                        "-movflags", "+faststart", str(self.out / name)], check=True)
        for leftover in [listing, *joined, *self.out.glob("part*_*.mp4")]:
            leftover.unlink()


def summary(version: str, runs: list[Run], started: datetime) -> str:
    lines = [
        f"# Two-phone test: {version}", "",
        f"- **Server:** the dev backend at {SERVER} (the laptop as the emulators see it), on an empty Sheet for each build",
        f"- **Phones:** {TEACHER} (teacher), {STUDENT} (students), Android 16 emulators with 2 GB and no WhatsApp, so each "
        "share button opens Android's share sheet",
        f"- **Started:** {started:%Y-%m-%d %H:%M} India time. The teacher's Today tab shows the rest of the day's classes, "
        "one card per batch, so how many depends on the hour",
        "- **Not tested:** the Ask tab, as Gemma needs a phone with 6 GB", "",
    ]
    for run in runs:
        passed = sum(ok for _, ok, _ in run.results)
        lines += [f"## {BUILDS[run.build]}: {passed}/{len(run.results)} passed", ""]
        lines += [f"- {'✅' if ok else '❌'} {what}" + ("" if ok else f" ({detail})") for what, ok, detail in run.results]
        lines.append("")
    lines.append(f"Test people only (98000001xx). The screenshots, with the screen and UI dump of each failed check "
                 f"(fail_<n>.png and .xml), and the recording are kept locally in .local/visualization/"
                 f"{viz.folder(version).name}/ (screens/{version}/ and tours/).")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
