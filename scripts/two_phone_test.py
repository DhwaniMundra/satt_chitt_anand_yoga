"""Two phones, one server and no WhatsApp on either: a teacher on emulator-5554 and students on emulator-5556, through
the whole loop. The teacher signs up and sets each batch's everyday Meet link; one that is no link is refused beside its
field while the others save. Two students sign up with the group code and tell the teacher about themselves, one with
pain, and the teacher places each in the batch their answers point to. A class group link (not WhatsApp's) shows the
students a button for it, and clearing it takes the button away. The owner moves a batch's time in the Sheet, and its
coming class moves with it, keeping its own link. Meera, who did not check in, is asked whether she was in class (and
never about one held before she was placed) and says how it went. The teacher shares a class, its Meet link pasted as a
browser gives it, through Android's
share sheet; Asha checks in with a mood, which opens the class, and after it says how each item went, with a strain on
one, all of it kept when the phone turns. The teacher reads the classes on Insights and in their reviews, strain first,
and writes to Asha about that asana, which she reads in its history. She practises on her own with the stopwatch and
shares a health note. Remove and a new group code ask first; the teacher moves Meera to another batch with a note, kept
in the review history, and gives her a new password, which she changes on the Me tab; in a batch with no link yet she
checks in from the faces on the card while the server is out of reach, and it lands once it is back. A new group code turns the old one away from a third sign-up, whose answers are
kept when the phone turns; both sign out and in again, their data still there; and both Today tabs are shot in Hindi.

Each step saves a screenshot (.local/visualization/viz_<major>/screens/<version>/), and a check that fails saves the
screen and its UI dump beside them (fail_<n>.png and .xml). The debug build's run is recorded from both screens into
one side-by-side video (viz_<major>/tours/two_phones_<version>.mp4). With --release, the same loop runs again on a
release build (shrunk by R8) pointed at the dev backend, its screenshots named release_*; with --release-only, on that
build alone. The pass/fail list goes to docs/evals/two_phones_<version>.md.

Needs: both emulators running (scripts/run_emulator.sh, then SCA_AVD=sca_phone_2 SCA_PORT=5556 ...), the debug APK
built, and nothing else on port 8000: each build's run starts the dev backend on an empty Sheet
(data/two_phones_<build>.json) whose teacher signs up with `teacher_code`, and stops and starts it on the way. Uses test
people only (98000001xx).

Usage:
  python3 scripts/two_phone_test.py v0.9.1-two-phones PILOT1
  python3 scripts/two_phone_test.py v0.9.1-two-phones PILOT1 --release android/app/build/outputs/apk/release/app-release.apk
  python3 scripts/two_phone_test.py v0.9.1-two-phones PILOT1 --release-only --release <the same APK>
The release APK for the emulator: in android/, ./gradlew assembleRelease -PscaServer=http://10.0.2.2:8000 -Pabi=x86_64
-Psigning=<the properties file of any key, as scripts/build_app.sh writes one>.
"""

import argparse
import contextlib
import io
import json
import os
import re
import subprocess
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

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
OWN_PASSWORD = "pilot456"  # the one Meera then chooses
TEACHER_PHONE, ASHA, MEERA, KAVYA = "9800000101", "9800000102", "9800000103", "9800000104"
BATCHES = {b["key"]: b for b in json.loads((ROOT / "content" / "studio.json").read_text(encoding="utf-8"))["batches"]}
LINKS = {"beginner": "meet.google.com/beg-ginn-ers", "intermediate": "meet.google.com/int-erme-dia",
         "pain_management": "meet.google.com/pai-nman-age"}  # everyday links; Advanced gets no link
NOT_A_LINK = "ask me for the link"  # typed into Advanced's box, and refused
PASTED_LINK = "https://meet.google.com/ABC-defg-hij?authuser=0"  # the shared class's own, as a browser gives it
CLASS_LINK = "https://meet.google.com/abc-defg-hij"  # and as it is kept
MOVED_LINK = "meet.google.com/mov-edcl-ass"  # the own link of the class whose batch's time moves
GROUP_BOX = "Class group link (optional)"
GROUP_LINK = "https://t.me/sca_yoga_test"
REFUSED_LINK = "Please paste a video call link"
FEEDBACK = "Keep the hips low today; lift only as far as the back allows."
STRAIN_NOTE = "Lower back pinched lifting the hips"
NOTE = "Right knee clicks when I kneel"
MOVE_NOTE = "Steady in the standing poses; ready for longer holds"
BUILDS = {"debug": "Debug build (app-debug.apk)",
          "release": "Release build (R8-shrunk, x86_64, built with -PscaServer=http://10.0.2.2:8000 -Pabi=x86_64)"}


def on(serial: str) -> None:
    """Points every following adb call at one phone."""
    os.environ["ANDROID_SERIAL"] = serial


class Run:
    """One build's pass through the loop: its checks so far, and where its screenshots go."""

    def __init__(self, build: str, out: Path, sheet: Path) -> None:
        self.build = build
        self.out = out
        self.sheet = sheet
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
        phones stand upright and both apps start again, still signed in, and the loop goes on with the next part."""
        try:
            yield
        except Exception as e:  # noqa: BLE001 (any of them stops only this part)
            self.verdict(f"{name}: carried through", False, f"{type(e).__name__}: {e}"[:300])
            for serial in PHONES:
                on(serial)
                turn(landscape=False)
                p.launch()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("version")
    parser.add_argument("teacher_code")
    parser.add_argument("--release", type=Path, help="a release APK for the emulator, to run the loop on as well")
    parser.add_argument("--release-only", action="store_true", help="run the loop on the release APK alone")
    args = parser.parse_args()
    builds = ([] if args.release_only else [("debug", APK)]) + ([("release", args.release.resolve())] if args.release else [])
    short = args.version.removesuffix("-two-phones")
    out = viz.fresh_screens(args.version)  # swapped in for screens/<version>/ at the end of a run that finishes
    started = datetime.now(IST)
    runs = []
    for build, apk in builds:
        sheet = ROOT / "data" / f"two_phones_{build}.json"
        run = Run(build, out, sheet)
        runs.append(run)
        with p.dev_backend(sheet, demo=False, teacher_code=args.teacher_code) as backend:
            for serial in PHONES:
                on(serial)
                p.install(apk)
                p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
                turn(landscape=False)
                p.demo_mode()
                p.launch(fresh=True)
            video = SideBySide(viz.tours(args.version)) if build == "debug" else None
            try:
                loop(run, backend, args.teacher_code, debug=build == "debug")
            finally:
                if video:
                    video.save(f"two_phones_{short}.mp4")
    report = ROOT / "docs" / "evals" / f"two_phones_{short}.md"
    report.write_text(summary(args.version, runs, started), encoding="utf-8")
    viz.keep_screens(args.version, carry=lambda name: "fail_" not in name)  # a failure's screen belongs to its own run
    for run in runs:
        print(f"{run.build}: {sum(ok for _, ok, _ in run.results)}/{len(run.results)} passed")
    print(report)


def loop(run: Run, backend: p.DevBackend, teacher_code: str, debug: bool) -> None:
    moved = None  # the class whose batch's time moves, once it has its own link
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

    # 2. Each batch's everyday Meet link: one box holds no link and is refused beside it, and the others save.
    with run.part("the teacher sets each batch's everyday Meet link"):
        for key, link in (*LINKS.items(), ("advanced", NOT_A_LINK)):
            p.find_scrolling(link_box(key))
            p.type_into(link_box(key), link)
        p.hide_keyboard()
        p.tap_under(GROUP_BOX, "Save")
        time.sleep(2)
        p.scroll_to_top()
        p.find_scrolling(link_box("pain_management"))  # the box below Advanced's: both in view, and what is between
        run.verdict("what is no link is refused, its reason beside its own box",
                    between(link_box("advanced"), REFUSED_LINK, link_box("pain_management")), f"'{REFUSED_LINK}' not under Advanced")
        run.shot("03_teacher_links")
        home = p.call("GET", "/teacher/home?lang=en", token)
        saved = {b["key"]: b["meet_link"] for b in home["batches"]}
        run.verdict("and the other batches' links are saved", saved == {**{k: "https://" + v for k, v in LINKS.items()}, "advanced": None},
                    str(saved))
        run.verdict("no class group link is set", home["settings"]["group_link"] is None, str(home["settings"]))
        retype(NOT_A_LINK, "")  # Advanced stays without a link
        p.hide_keyboard()
        run.check("the day's classes use their batch's everyday link", "Using the batch's everyday link", scroll=True)

    # 3. Asha signs up with the group code and tells the teacher about herself, with pain in the knee.
    with run.part("Asha signs up and answers about herself"):
        on(STUDENT)
        sign_up_form()
        run.check("sign-up asks for a phone number, with a hint for one from outside India", "Outside India? Start with +")
        run.shot("04_student_signup")
        fill_sign_up("Asha (test)", ASHA, code)
        run.check("the intake opens after sign-up, saying first who sees it", f"These answers go to {T}")
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
        run.check("a wrong group code is refused, saying it comes from the teacher", "It comes from your teacher")
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

    # 6. Meera's Today tab: the batch, the next class and its link; with no group link, no button for one.
    with run.part("Meera's Today tab"):
        on(STUDENT)
        come_back()
        run.check_gone("the placed student leaves the waiting card, after returning to the app", "Waiting for")
        run.check("the placed student sees her batch", "Your batch: Beginner")
        today_tab(run, "Meera")
        run.shot("10_student_today")
        joins(run, "Join class opens the class's Meet link, in the browser as there is no Meet app")
        mine = p.call("GET", "/home?lang=en", api_login(MEERA))
        nxt, after, since = mine["sessions"][0], mine["after_class"], mine["user"]["batch_since"]
        run.verdict("her next class carries her batch's everyday link", (nxt["batch"]["key"], nxt["meet_link"]) == (
            "beginner", "https://" + LINKS["beginner"]), f"{nxt['batch']['key']}: {nxt['meet_link']}")
        early = after and not after["checked_in"] and after["starts_at"] < since
        run.verdict("she is not asked whether she was in a class held before she was placed", not early,
                    f"asked about {after['batch']['name']} at {clock(after['starts_at'])}, placed at {clock(since)}" if early else "")

    # 7. A class group link that is not WhatsApp's: the student gets a button for it; cleared, the button goes.
    with run.part("the class group link"):
        on(TEACHER)
        tab("Today")
        p.find_scrolling(GROUP_BOX)
        p.type_into(GROUP_BOX, GROUP_LINK)
        p.hide_keyboard()
        p.tap_under(GROUP_BOX, "Save")
        run.check("a Telegram group link is saved", "Saved")
        group = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_link"]
        run.verdict("as the class group link", group == GROUP_LINK, str(group))
        on(STUDENT)
        come_back()
        run.check("the student sees 'Open the class group'", "Open the class group", scroll=True)
        run.shot("11_student_group_link")
        p.clear_log()
        p.tap("Open the class group")
        time.sleep(3)
        run.verdict("which opens the group's link", any(link.startswith("https://t.me/") for link in p.opened()), str(p.opened()))
        come_back()
        p.adb("shell", "am", "force-stop", "com.android.chrome")
        on(TEACHER)
        p.scroll_to_top()
        p.find_scrolling(GROUP_LINK, exact=True)
        retype(GROUP_LINK, "", exact=True)
        p.hide_keyboard()
        p.tap_under(GROUP_BOX, "Save")
        run.check("cleared, the group link is saved empty", "Saved")
        group = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_link"]
        run.verdict("and removed", group is None, str(group))
        on(STUDENT)
        come_back()
        run.verdict("and the student's button goes", "Open the class group" not in labels(whole_page=True), "the button still shows")

    # 8. The owner's hand in the Sheet, with the server stopped. The day's last class, which the teacher gives its own
    #    link, has its batch's time moved 45 minutes later: it moves with it, keeping its id and its link, and the day
    #    gets no second class. Meera's placement is dated two hours back, so a class begun since then is her batch's.
    with run.part("a batch's time moves in the Sheet"):
        on(TEACHER)
        sessions = p.call("GET", "/teacher/home?lang=en", token)["sessions"]
        last = [s for s in sessions if moment(s["starts_at"]) > datetime.now(IST) + timedelta(hours=1)][-1]
        p.scroll_to_top()
        if last["id"] != sessions[0]["id"]:  # the first card is the open one
            p.tap_scrolling(f" · {clock(last['starts_at'])}")
        p.find_scrolling("Google Meet link")
        p.type_into("Google Meet link", MOVED_LINK)
        p.hide_keyboard()
        p.tap_under("Google Meet link", "Save")
        run.check("the teacher gives a coming class its own link", "Saved")
        batch, new_start = last["batch"]["key"], moment(last["starts_at"]) + timedelta(minutes=45)
        meera = next(u for u in p.call("GET", "/teacher/students", token)["students"] if u["name"] == "Meera (test)")["id"]
        two_hours_ago = {"$date": int((time.time() - 2 * 3600) * 1000)}
        backend.stop()
        edit_sheet(run.sheet, "batches", {"key": batch}, {"time": f"{new_start:%H:%M}"})
        edit_sheet(run.sheet, "users", {"id": meera}, {"batch_since": two_hours_ago})
        edit_sheet(run.sheet, "batch_changes", {"student_id": meera}, {"created_at": two_hours_ago})
        backend.start()
        come_back()
        day = [(s["id"], s["starts_at"], s["meet_link"]) for s in p.call("GET", "/teacher/home?lang=en", token)["sessions"]
               if s["batch"]["key"] == batch]
        run.verdict(f"moved to {new_start:%H:%M}, the class keeps its id and its own link, and the day has no second {last['batch']['name']} "
                    "class", day == [(last["id"], iso(new_start), "https://" + MOVED_LINK)], str(day))
        run.check("its card shows the new time", f" · {clock(iso(new_start))}", scroll=True)
        run.check("and its own link", "https://" + MOVED_LINK, scroll=True)
        run.shot("12a_teacher_class_moved")
        moved = last["id"]

    # 9. Meera did not check in to a class of her batch: asked whether she was in it, she says how it went.
    with run.part("Meera says how a class went, with no check-in"):
        on(STUDENT)
        unchecked = p.add_class("beginner", -50)  # began 50 minutes ago; the after-class window is open
        asked = p.call("GET", "/home?lang=en", api_login(MEERA))["after_class"]
        run.verdict("a class of her batch that she did not check in to is the one she is asked about", (asked["id"], asked["checked_in"])
                    == (unchecked, False), f"{asked['id']}, checked in {asked['checked_in']}")
        come_back()
        run.check("a student who did not check in is asked 'Were you in class?'", "Were you in class?")
        run.check("about that class, once the tab has read it again", f"Beginner · Today · {clock(asked['starts_at'])}")
        run.shot("12_student_were_you_in_class")
        p.tap(f"Tell {T}")
        run.check("and can say how it went", "How do you feel now?")
        p.tap("Good", exact=True)
        p.tap_under("Sectional", "Steady")
        p.tap_under("Omkar", "At ease")
        p.tap_scrolling("Done", exact=True)
        run.check("her answers are kept", f"You told {T} how it went")
        run.shot("13_student_told_no_checkin")
        log_out("Me")
        log_in(ASHA)
        run.check("Asha, placed, sees her batch", "Your batch: Pain management")
        today_tab(run, "Asha")
        nxt = p.call("GET", "/home?lang=en", api_login(ASHA))["sessions"][0]
        link = "https://" + (MOVED_LINK if nxt["id"] == moved else LINKS["pain_management"])
        run.verdict("her next class carries its link: its own, or else her batch's everyday one", (nxt["batch"]["key"], nxt["meet_link"])
                    == ("pain_management", link), f"{nxt['batch']['key']}: {nxt['meet_link']}")
        run.shot("14_student_a_today")

    # 10. The teacher shares a class, its link pasted as a browser gives it: Share saves it, then opens the share sheet.
    with run.part("the teacher shares a class"):
        on(TEACHER)
        staged = p.add_class("pain_management", -47)  # under way, 8 minutes left: both check-ins are open
        come_back()
        p.scroll_to_top()
        first = p.call("GET", "/teacher/home?lang=en", token)["sessions"][0]
        if first["id"] != staged:  # a class that began earlier is still on, and its card is the open one
            starts = next(s for s in p.call("GET", "/teacher/home?lang=en", token)["sessions"] if s["id"] == staged)["starts_at"]
            p.tap_scrolling(f"Today · {clock(starts)}", exact=True)
        p.find_scrolling("Google Meet link")
        p.type_into("Google Meet link", PASTED_LINK)
        p.hide_keyboard()
        p.tap_under("Google Meet link", "Share")
        time.sleep(2)
        run.verdict("Share opens Android's share sheet", p.resumed().startswith("com.android.intentresolver/"), p.resumed())
        run.check("the message carries the link, as the server keeps it", CLASS_LINK)
        run.check("and names the batch", "Pain management")
        run.shot("15_teacher_share_sheet")
        p.back()  # dismissed, shared with no one
        run.verdict("the share sheet is dismissed, back in the app", p.resumed().endswith("/.MainActivity"), p.resumed())
        session = next(s for s in p.call("GET", "/teacher/home?lang=en", token)["sessions"] if s["id"] == staged)
        run.verdict("the pasted link is accepted and kept in its plain form, as the class's own", session["own_link"]
                    and session["meet_link"] == CLASS_LINK, str(session["meet_link"]))
        run.check("and shows on the class's card", CLASS_LINK, scroll=True)
        p.find_scrolling("Google Meet link")
        save = tappable_around("Google Meet link", "Save")
        run.verdict("saved, the card's Save is off until the link changes again", save.get("enabled") == "false",
                    "Save stays on: the box keeps the link as typed, not as saved")
        run.shot("16_teacher_link_saved")

    # 11. Asha checks in with a mood, which opens the class; after it, a reaction per item, a strain and a note, kept
    #     when the phone turns.
    with run.part("Asha's class"):
        on(STUDENT)
        come_back()
        run.check("the shared class is her next, under way", "Live now")
        p.clear_log()
        p.tap("Join class")
        run.check("before-class question appears in the check-in window", "How do you feel right now?")
        p.tap("Okay", exact=True)
        time.sleep(3)
        run.verdict("the mood tap opens the class's Meet link at once", any(link.startswith("https://meet.google.com/") for link in
                                                                            p.opened()), str(p.opened()))
        mine = p.call("GET", "/home?lang=en", api_login(ASHA))["sessions"][0]
        run.verdict("the check-in reaches the server, and the link she is given is the one shared", (mine["id"], mine["meet_link"],
                    mine["checked_in"]) == (staged, CLASS_LINK, True), f"{mine['id']}: {mine['meet_link']}, checked in {mine['checked_in']}")
        come_back()  # from Meet in the browser, without restarting the app
        p.adb("shell", "am", "force-stop", "com.android.chrome")
        p.tap(f"Tell {T}")
        run.check("after-class question appears on returning to the app", "Class done! How do you feel now?")
        p.tap("Great")
        reactions = (("Sectional", "Steady"), ("Pavanamuktasana", "At ease"), ("Setu Bandhasana", "With effort"), ("Makarasana", "Steady"))
        for item, reaction in reactions[:3]:
            p.tap_under(item, reaction)
        p.tap_under("Setu Bandhasana", "Felt strain or pain")
        p.tap_under("Setu Bandhasana", "Add a note")
        p.type_under("Setu Bandhasana", STRAIN_NOTE)
        p.tap_under(*reactions[3])
        run.shot("17_student_after_class")
        turn(landscape=True)
        run.shot("17b_student_after_class_landscape")
        turn(landscape=False)
        p.scroll_to_top()
        lost = [] if any(n.get("text") == "Great" for n, _ in p.nodes()) else ["the mood"]
        for item, reaction in reactions:  # down the list, each read while its card is in view
            lost += [] if chosen(item, reaction) else [f"{item}: {reaction}"]
            if item == "Setu Bandhasana":
                lost += [] if chosen(item, "Felt strain or pain") else ["the strain"]
                note = p.under(item, lambda n: n.get("class") == "android.widget.EditText", "the note").get("text")
                lost += [] if note == STRAIN_NOTE else [f"the note ({note!r})"]
        run.verdict("turned to landscape and back, her answers are all kept: the mood, each reaction, the strain, the note",
                    not lost, f"lost: {lost}")
        p.tap_scrolling("Done", exact=True)
        run.check("the answers are kept", f"You told {T} how it went")
        run.shot("18_student_told")
        tab("Ask")
        run.check("a 2 GB phone says chat needs more memory", "Cloud model support coming soon")

    # 12. The teacher reads both classes on Insights and in their reviews, strain first; Meera counts with no mood before.
    with run.part("the teacher reads the classes"):
        on(TEACHER)
        tab("Insights")
        time.sleep(2)
        run.check("teacher sees the student's before and after", "1 joined")
        run.shot("19_teacher_insights")
        counted = {s["id"]: s for s in p.call("GET", "/teacher/insights?lang=en", token)["sessions"]}.get(unchecked, {})
        run.verdict("the class Meera came to without a check-in counts her, with no mood before", (counted.get("joined"),
                    counted.get("mood_before")) == (1, None), str(counted))
        p.tap_scrolling("How each item went")
        run.check("the class review opens", "How the class went")
        run.check("with her strain, her name and her note", "Felt strain or pain: Asha (test)")
        items = ("Vibhagiya", "Pavanamuktasana", "Setu Bandhasana", "Makarasana")
        top = next((item for text in labels() for item in items if item in text), None)
        run.verdict("strain or pain first: Setu Bandhasana leads, ahead of the class's order", top == "Setu Bandhasana",
                    f"first item: {top}")
        run.shot("20_teacher_class_review")
        p.back()
        p.scroll_to_top()
        p.find_scrolling("Beginner")
        p.tap_under("Beginner", "How each item went")
        run.check("the review of Meera's class counts her and what she said", "1 joined · 1 said how it went")
        run.shot("21_teacher_review_no_checkin")
        p.back()

    # 13. The teacher writes to Asha about that asana; she reads it in its history on the Practice tab.
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
        run.shot("22_teacher_feedback")
        p.back()
        p.back()
        on(STUDENT)
        tab("Practice")
        time.sleep(2)
        run.check("her Practice tab shows the teacher wrote", f"{T} wrote", scroll=True)
        p.scroll_to_top()
        p.tap_scrolling("Setu Bandhasana")
        run.check("and she reads it in that asana's history", FEEDBACK[:40])
        run.shot("23_student_item_history")
        p.back()

    # 14. A practice on her own with the stopwatch, saved; it shows on the Practice tab, with her run of classes.
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
        run.shot("24_student_solo")
        p.tap_scrolling("Finish", exact=True)
        run.check("the practice on her own is saved", "Saved to your practice")
        run.check("and shows on the Practice tab", "Solo practice · 1 min", scroll=True)
        p.scroll_to_top()
        texts = labels()
        streak = p.call("GET", "/me", api_login(ASHA))["stats"]["streak_days"]
        tile = texts[texts.index("Classes in a row") - 1] if "Classes in a row" in texts else None
        run.verdict(f"her streak reads 'Classes in a row': {tile}", tile == str(streak) and streak >= 1,
                    f"tile {tile!r}, server {streak}")
        run.shot("25_student_practice")
        p.tap_scrolling("Vajrasana")
        run.check("with the hold the stopwatch timed, in Vajrasana's history", "Solo · held 0:1")
        p.back()

    # 15. A health note shared from the Me tab; the teacher sees it.
    with run.part("Asha shares a health note"):
        tab("Me")
        p.type_into("For example: my left knee", NOTE)
        p.hide_keyboard()
        p.tap("Save", exact=True)
        p.tap(f"Share with {T}")
        p.tap("Share", exact=True)  # in the dialog that asks first
        run.check("the note is shared", f"Shared with {T}")
        run.shot("26_student_note_shared")
        on(TEACHER)
        tab("Students")
        time.sleep(2)
        run.check("the teacher sees the shared health note", NOTE)
        run.shot("27_teacher_shared_note")

    # 16. Remove asks first; the move to another batch, with its note in the review history; a new password, shown
    #     until OK.
    with run.part("the teacher asked before removing Meera"):
        p.scroll_to_top()
        p.tap_under("Meera (test)", "Remove")
        run.check("Remove asks first", "Remove Meera (test)?")
        run.shot("28_teacher_remove_asks")
        p.tap("Cancel", exact=True)
        status = next(u for u in p.call("GET", "/teacher/students", token)["students"] if u["name"] == "Meera (test)")["status"]
        run.verdict("Cancel, and she stays", status == "approved", status)
    with run.part("the teacher moves Meera"):
        p.scroll_to_top()
        p.tap_under("Meera (test)", "Move to batch")
        p.tap_under("Meera (test)", "Advanced")
        p.type_under("Meera (test)", MOVE_NOTE)
        run.shot("29_teacher_move")
        p.tap_under("Meera (test)", "Move to Advanced")
        time.sleep(2)
        moved = next(u for u in p.call("GET", "/teacher/students", token)["students"] if u["name"] == "Meera (test)")
        run.verdict("Meera is moved to Advanced", moved["batch"] == "advanced", str(moved["batch"]))
        run.check("her card shows the new batch", "Advanced · since", scroll=True)
        noted = [c for c in sheet_rows(run.sheet, "batch_changes") if c["student_id"] == moved["id"] and c["to"] == "advanced"]
        run.verdict("the move and its note are kept in her batch history (the Sheet's batch_changes tab; the app has no "
                    "screen for it)", [c["note"] for c in noted] == [MOVE_NOTE], str(noted))
    with run.part("the teacher gives Meera a new password"):
        p.scroll_to_top()
        p.tap_under("Meera (test)", "New password")
        run.check("the teacher is asked first", "New password for Meera (test)?")
        p.tap_under("New password for Meera (test)?", "New password")
        shown = p.label(p.find("New password for Meera (test):"))
        new_password = shown.rsplit(": ", 1)[1].strip()
        p.tap("Copy", exact=True)
        run.check("Copy copies it", "Copied", exact=True)
        p.tap_xy(540, 300)
        run.check("a tap outside leaves the dialog open", "New password for Meera (test):", timeout=4)
        p.back()
        run.check("so does Back", "New password for Meera (test):", timeout=4)
        run.shot("30_teacher_new_password")
        p.tap("OK", exact=True)
        run.check_gone("OK closes it", "New password for Meera (test):")

    # 17. Meera: the old password fails and the new one works; her new batch, which has no link yet, and its class,
    #     which she checks in to from the faces on its card; then her own password, from the Me tab.
    with run.part("Meera signs in again, in a batch with no link yet"):
        p.add_class("advanced", -10)  # under way; Advanced has no everyday link
        on(STUDENT)
        log_out("Me")
        log_in(MEERA)
        run.check("the old password fails", "Wrong number or password.")
        run.shot("31_student_old_password")
        retype("Password", new_password)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)
        time.sleep(3)
        run.check("the new password works", "Namaste, Meera")
        run.check("she sees her new batch", "Your batch: Advanced")
        run.check("and its class", "Advanced", exact=True)
        run.check("a class with no link yet says so", "The class link will appear here before class.")
        run.check("and offers the check-in, the faces on its card", "How do you feel right now?")
        run.shot("32_student_no_link_checkin")
        mine = p.call("GET", "/home?lang=en", api_login(MEERA, new_password))
        nxt, after, meera = mine["sessions"][0], mine["after_class"] or {}, mine["user"]["id"]
        run.verdict("after the move, the class of her old batch from before it is still hers to say how it went",
                    after.get("id") == unchecked, f"after_class: {after.get('id')} {after.get('batch', {}).get('key')}")
        backend.stop()  # the server out of reach as she checks in
        p.tap("Good", exact=True)
        run.check("with the server out of reach, she checks in from the faces, and the tab shows it done", "You checked in")
        time.sleep(15)  # the app's own tries, a few seconds apart, are over
        run.check("still shown done once the app has stopped trying", "You checked in")
        run.shot("33_student_checked_in_offline")
        backend.start()
        come_back()  # coming back to the app sends what waits
        landed = wait_for(lambda: [c for c in sheet_rows(run.sheet, "checkins")
                                   if (c["user_id"], c["session_id"], c["phase"]) == (meera, nxt["id"], "before")])
        run.verdict("back in reach, the check-in lands in the Sheet's checkins, once, with her mood", [c["mood"] for c in landed] == [4],
                    str(landed))
        nxt = p.call("GET", "/home?lang=en", api_login(MEERA, new_password))["sessions"][0]
        run.verdict("for her next class, which has no link", (nxt["meet_link"], nxt["checked_in"]) == (None, True),
                    f"{nxt['batch']['key']}: link {nxt['meet_link']}, checked in {nxt['checked_in']}")
        run.shot("33b_student_checked_in")
    with run.part("Meera changes her own password"):
        tab("Me")
        p.tap_scrolling("Change password")
        p.type_into("Current password", new_password)
        p.type_into("Password (6", OWN_PASSWORD)
        p.type_into("New password again", OWN_PASSWORD)
        p.hide_keyboard()
        run.shot("34_student_change_password")
        p.tap_under("New password again", "Save")
        run.check("her new password is saved", "Password changed")
        log_out("Me")
        log_in(MEERA, new_password)
        run.check("the old one fails", "Wrong number or password.")
        retype("Password", OWN_PASSWORD)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)
        time.sleep(3)
        run.check("and the new one works", "Namaste, Meera")

    # 18. A new group code asks first; the invite opens the share sheet. The old code is turned away from a third
    #     sign-up, whose pain areas are kept when the phone turns.
    with run.part("the teacher makes a new group code"):
        on(TEACHER)
        tab("Today")
        old_code = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_code"]
        p.tap_scrolling("New code", exact=True)
        run.check("New code asks first", "Make a new group code?")
        run.shot("35_teacher_new_code_asks")
        p.tap("Cancel", exact=True)
        kept = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_code"]
        run.verdict("Cancel keeps the code", kept == old_code, f"{old_code} -> {kept}")
        p.tap_scrolling("New code", exact=True)
        p.tap_under("Make a new group code?", "New code")
        time.sleep(2)
        new_code = p.call("GET", "/teacher/home?lang=en", token)["settings"]["group_code"]
        run.verdict("confirmed, a new group code is made", new_code != old_code, f"{old_code} -> {new_code}")
        run.check("and shown", new_code, exact=True)
        p.tap_scrolling("Invite students", exact=True)
        time.sleep(2)
        run.verdict("the invite opens Android's share sheet", p.resumed().startswith("com.android.intentresolver/"), p.resumed())
        run.check("the invite carries the new code", f"group code: {new_code}")
        run.shot("36_teacher_invite")
        p.back()
        run.verdict("the share sheet is dismissed, back in the app", p.resumed().endswith("/.MainActivity"), p.resumed())
    with run.part("a third student signs up"):
        on(STUDENT)
        log_out("Me")
        sign_up("Kavya (test)", KAVYA, old_code)
        run.check("the old group code is refused", "It comes from your teacher")
        run.shot("37_student_old_code")
        retype(old_code, new_code, exact=True)
        p.hide_keyboard()
        p.tap("Create account", exact=True, last=True)
        time.sleep(3)
        run.check("the new code works for a third sign-up", f"These answers go to {T}")
        for area in ("Neck", "Hip"):
            p.tap_scrolling(area, exact=True)
        turn(landscape=True)
        turn(landscape=False)
        p.scroll_to_top()
        lost = [area for area in ("Neck", "Hip") if not chosen("ANY PAIN OR CONDITION?", area)]
        run.verdict("turned to landscape and back, the pain areas chosen are kept", not lost, f"lost: {lost}")
        run.shot("38_student_intake_turned")
        p.scroll_to_top()
        p.tap("Back", exact=True)
        run.check("and she waits to be placed", "Waiting for")

    # 19. Both sign out and in again; what they did is still there.
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
        run.check("and the classes on the Insights tab", "1 joined")
        run.shot("39_teacher_signed_in_again")
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
        run.shot("40_student_signed_in_again")

    # 20. Both Today tabs in Hindi, shot down the page for words cut off or running over; then English again.
    with run.part("both Today tabs in Hindi"):
        tab("Me")
        p.tap_scrolling("हिन्दी", exact=True)
        time.sleep(4)
        tab("आज")
        time.sleep(2)
        shoot_down(run, "41_hindi_student_today")
        on(TEACHER)
        tab("Today")
        p.tap_scrolling("हिन्दी", exact=True)
        time.sleep(4)
        shoot_down(run, "42_hindi_teacher_today")
        p.tap_scrolling("English", exact=True)
        time.sleep(4)
        run.check("the teacher's app is back in English", "Students", exact=True)
        on(STUDENT)
        tab("मैं")
        p.tap_scrolling("English", exact=True)
        time.sleep(4)
        run.check("and the student's", "Practice", exact=True)


# ---- steps ----

def come_back() -> None:
    """Home, then back to the running app, as a person returning from Meet or the share sheet would, and the page pulled
    down to be read again: coming back reads it only if the last read is half a minute old."""
    p.adb("shell", "input", "keyevent", "KEYCODE_HOME")
    time.sleep(1)
    p.adb("shell", "am", "start", "-n", f"{p.PACKAGE}/.MainActivity")
    time.sleep(2)
    p.scroll_to_top()
    p.adb("shell", "input", "swipe", "540", "600", "540", "1600", "400")
    time.sleep(3)


def sign_up_form(teacher: bool = False) -> None:
    p.tap("I'm the teacher" if teacher else "I'm a student")
    p.tap("Create account", exact=True)  # the switch above the form; the teacher's form opens on "Log in"


def fill_sign_up(name: str, number: str, code: str, teacher: bool = False) -> None:
    p.type_into("Your name", name)
    p.type_into("Phone number", number)
    p.type_into("Password", PASSWORD)
    p.type_into("Teacher code" if teacher else "Group code", code)
    p.hide_keyboard()
    p.tap("Create account", exact=True, last=True)
    time.sleep(3)


def sign_up(name: str, number: str, code: str, teacher: bool = False) -> None:
    sign_up_form(teacher)
    fill_sign_up(name, number, code, teacher)


def log_in(number: str, password: str = PASSWORD, teacher: bool = False) -> None:
    p.tap("I'm the teacher" if teacher else "I'm a student")
    p.tap("Log in", exact=True)
    p.type_into("Phone number", number)
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
    """Empties the filled text box showing `box` (its words, or its label) and types `value` into it. The tap leaves the
    cursor where it landed, so the words are deleted on both sides of it."""
    p.tap(box, exact=exact)
    time.sleep(0.5)
    p.adb("shell", "input", "keyevent", *["KEYCODE_DEL"] * 64, *["KEYCODE_FORWARD_DEL"] * 64)
    if value:
        p.type_text(value)


def turn(landscape: bool) -> None:
    """Turns the phone, auto-rotate off: to landscape, or upright again. The app's screen is made anew each way."""
    p.adb("shell", "settings", "put", "system", "accelerometer_rotation", "0")
    p.adb("shell", "settings", "put", "system", "user_rotation", "1" if landscape else "0")
    time.sleep(3)


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
    no group link set, no button for a class group."""
    page = labels(whole_page=True)
    run.check("her next class, with its Meet link to join", "Join class")
    run.verdict(f"with no group link set, {who}'s Today tab has no button for a class group, nor any word of WhatsApp",
                not any("Open the class group" in text or "WhatsApp" in text for text in page), "a button or WhatsApp shows")
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


def shoot_down(run: Run, name: str) -> None:
    """Screenshots of the page from its top, a screenful at a time, until its end: name_1, name_2…"""
    p.scroll_to_top()
    seen: list[str] = []
    for n in range(1, 7):
        run.shot(f"{name}_{n}")
        texts = labels()
        if all(text in seen for text in texts):
            break
        seen += texts
        p.scroll_down()
    p.scroll_to_top()


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


def between(upper: str, text: str, lower: str) -> bool:
    """Whether the words `text` show below those holding `upper` and above those holding `lower`, on screen now."""
    at: dict[str, int] = {}
    for node, _ in p.nodes():
        for key in (upper, text, lower):
            if key in p.label(node):
                at.setdefault(key, p.center(node)[1])
    return len(at) == 3 and at[upper] < at[text] < at[lower]


def tappable_around(anchor: str, label: str) -> ET.Element:
    """The tappable element (a button, a chip) holding the words `label`, the first below `anchor`."""
    words = p.bounds(p.under(anchor, lambda n: p.label(n) == label, label))
    root = ET.fromstring(p.hierarchy())
    parents = {child: node for node in root.iter() for child in node}
    node = next(n for n in root.iter() if p.label(n) == label and p.bounds(n) == words)
    while node.get("clickable") != "true" and node in parents:
        node = parents[node]
    return node


def chosen(anchor: str, label: str) -> bool:
    """Whether the chip `label`, the first below `anchor`, is chosen. A chip tells it only by its colour, filled (green,
    or red for strain or pain) where one not chosen is outlined, so it is read off the screen: where its words are, a
    chosen chip is mostly its dark fill, one not chosen mostly the light page."""
    x1, y1, x2, y2 = p.bounds(p.under(anchor, lambda n: p.label(n) == label, label))
    screen = Image.open(io.BytesIO(subprocess.run(["adb", "exec-out", "screencap", "-p"], check=True, capture_output=True).stdout))
    box = list(screen.convert("L").crop((x1, y1, x2, y2)).getdata())
    return sum(v < 160 for v in box) > len(box) / 2


def wait_for(found: Callable[[], list], seconds: float = 20) -> list:
    """What `found` gives, once it gives something, trying again for up to `seconds`; else what it gave last."""
    end = time.time() + seconds
    while True:
        got = found()
        if got or time.time() > end:
            return got
        time.sleep(1)


def edit_sheet(sheet: Path, tab_name: str, where: dict, values: dict) -> None:
    """Changes the rows of a tab of the dev backend's Sheet that hold `where`, as its owner would by hand. Only while
    the backend is stopped: it keeps the Sheet in memory, and saves all of it after each change."""
    saved = json.loads(sheet.read_text(encoding="utf-8"))
    data = next(s for s in saved["sheets"] if s["name"] == tab_name)["data"]
    head = data[0]
    for row in data[1:]:
        if all(row[head.index(key)] == value for key, value in where.items()):
            row.extend([""] * (len(head) - len(row)))
            for key, value in values.items():
                row[head.index(key)] = value
    sheet.write_text(json.dumps(saved), encoding="utf-8")


def sheet_rows(sheet: Path, tab_name: str) -> list[dict]:
    """A tab of the dev backend's Sheet, as it is saved: one dict per row, by the header."""
    data = next(s for s in json.loads(sheet.read_text(encoding="utf-8"))["sheets"] if s["name"] == tab_name)["data"]
    return [dict(zip(data[0], row)) for row in data[1:] if any(cell != "" for cell in row)]


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


def moment(stamp: str) -> datetime:
    """A moment as the server gives it ("2026-11-20T12:00:00Z"), in India time."""
    return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone(IST)


def iso(at: datetime) -> str:
    """A moment as the server gives it: "2026-11-20T12:00:00Z"."""
    return at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def clock(stamp: str) -> str:
    """A moment as the app shows the time of day, in India: "6:13 AM"."""
    at = moment(stamp)
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
        fit = "scale=540:1200:force_original_aspect_ratio=decrease,pad=540:1200:(ow-iw)/2:(oh-ih)/2:color=black,fps=24"
        for part in range(self.parts):
            teacher, student = (self.out / f"part{part}_{who}.mp4" for who in ("teacher", "student"))
            if not (teacher.exists() and student.exists()):
                continue
            joined.append(self.out / f"part{part}.mp4")
            subprocess.run(  # a part begun with the phone turned is landscape: each is fitted into the same frame
                ["ffmpeg", "-y", "-loglevel", "error", "-i", str(teacher), "-i", str(student), "-filter_complex",
                 f"[0:v]{fit}[a];[1:v]{fit}[b];[a][b]hstack=inputs=2:shortest=1[v]",
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
        "- **Not tested:** the Ask tab, as Gemma needs a phone with 6 GB. The Hindi pass is screenshots only "
        "(41_hindi_*, 42_hindi_*), read by eye", "",
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
