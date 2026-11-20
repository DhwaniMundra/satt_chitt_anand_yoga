"""Walks through the app on the emulator and saves the same screenshots and two screen recordings every time,
so each iteration can be compared with the last: screenshots in .local/visualization/viz_<major>/screens/<version>/,
each with the screen's UI dump beside it (<name>.xml, every element's bounds), and recordings and their small copies in
viz_<major>/tours/ (gitignored; scripts/make_figures.py turns the best of it into the committed GIFs and contact sheets
in docs/media/). It prints what the edges of a scrolling list cut through in any shot.

Needs: `source scripts/env.sh`, the 6 GB emulator running (SCA_AVD=sca_phone_big scripts/run_emulator.sh) with
Gemma downloaded in Ask, and nothing else on port 8000. The tour starts the dev backend on a fresh copy of the
synthetic demo (data/tour.json), where Meera and Priya joined today's 8:00 Intermediate class and said how it went. Asha
joins it in the tour and says how it went, so run the tour after that class and within 12 hours of it (9:00 to 20:55
in India). It adds an Intermediate class under way, for the before-class check-in, and starts the app signed out with no
chat or notes, so a second run shows the same screens.

The story, in the order it is shot, each screen holding what came before it: Asha joins her class and says how it went
(01-06); Neha, waiting to be placed, tells the teacher about herself (21-23b); the teacher shares a class, places Neha
in the batch her answers point to, moves Rohan, reads the class's review and writes to Asha about the strain she felt
(24-34); Neha placed (27b); then Asha's practice with the teacher's word, a practice on her own with the stopwatch and
her practice after it, Ask about her own asana (asked again in a fresh chat if the answer misreads her data) and asked to
remember her wrists, Me with that note shared, and Hindi and Marathi (07-20).

Usage: python3 scripts/capture_tour.py v1.0
"""

import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import phone as p
import viz

ROOT = Path(__file__).resolve().parents[1]
APK = ROOT / "android" / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
CLEAR_HI = "\u0938\u093e\u092b\u093c \u0915\u0930\u0947\u0902"  # "साफ़ करें" (Clear), spelt as in values-hi/strings.xml
STUDENT = ("9800000002", "demo123")
WAITING = ("9800000007", "demo123")  # Neha, who has told the teacher about herself and waits to be placed
TEACHER = ("9800000001", "demo123")


def main(version: str) -> None:
    with p.dev_backend(ROOT / "data" / "tour.json", demo=True):
        # Under way 5 minutes (the schedule drops a made-up class still to come): the check-in is open, the after-class
        # question not yet. Asha skips the mood, so it stays out of Insights.
        p.add_class("intermediate", -5)
        tour(version)


def tour(version: str) -> None:
    out = viz.fresh_screens(version)  # swapped in for screens/<version>/ at the end of a run that succeeds

    def shot(name: str) -> None:
        p.screenshot(out / f"{name}.png")  # at the phone's own size, for the film's close-ups
        xml = p.hierarchy()  # and beside it every element's bounds, for the film's checks of where rings and crops go
        (out / f"{name}.xml").write_text(xml, encoding="utf-8")
        for cut in p.cut_at_edges(xml):
            print(f"{name}: {cut}")

    def log_in(number: str, password: str) -> None:
        p.tap("Log in", exact=True)
        p.type_into("Phone number", number)
        p.type_into("Password", password)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)  # the button under the form, not the switch above it
        time.sleep(3)

    def log_out(tab: str) -> None:
        p.tap(tab, exact=True)
        tap_scrolling("Log out")
        time.sleep(1.5)

    def language(name: str, me: str) -> None:
        p.tap(me, exact=True)
        time.sleep(1.5)
        tap_scrolling(name, exact=True)
        time.sleep(3)

    p.adb("install", "-r", str(APK))
    p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
    p.demo_mode()
    p.launch(fresh=True)

    # ---- Asha: today's class ----
    video = p.Recording(viz.tours(version) / f"student_tour_{version}.mp4")
    shot("01_welcome")
    p.tap("I'm a student")
    shot("02_signup")
    log_in(*STUDENT)
    shot("03_today")
    p.tap("Join class")
    shot("04_checkin_before")
    p.tap("Skip", exact=True)
    time.sleep(3)
    p.join_class(STUDENT[0], todays_class(), 2)  # she joined the 8:00 class; the film tells it as this one
    p.launch()  # back from the Meet link in the browser, the class over
    tap_scrolling(f"Tell {p.TEACHER_NAME}")
    time.sleep(1.5)
    p.tap("Good")  # the after-class mood, by its spoken label
    shot("05_after_class")
    p.tap_under("Sectional", "Steady")
    p.tap_under("Surya Namaskar", "With effort")
    p.tap_under("Surya Namaskar", "Felt strain or pain")
    p.tap_under("Surya Namaskar", "Add a note")
    p.type_under("Surya Namaskar", "Wrists ached in the plank; rested after round three")
    p.tap_under("Virabhadrasana", "At ease")
    p.frame("Sectional", "Virabhadrasana")  # the first item's card starts the screen, the mood card above it out of sight
    shot("05a_after_class_items")
    tap_scrolling("Done", exact=True)
    time.sleep(2)
    shot("06_after_sent")
    video.stop()
    log_out("Me")

    # ---- Neha, waiting to be placed, tells the teacher about herself ----
    p.tap("I'm a student")
    log_in(*WAITING)
    shot("21_waiting")
    p.tap(f"Tell {p.TEACHER_NAME} about yourself")
    time.sleep(2)
    shot("22_intake")  # her answers, as she gave them
    p.adb("shell", "input", "swipe", "540", "1700", "540", "500", "600")
    time.sleep(1)
    shot("23_intake_poses")
    tap_scrolling(f"Send to {p.TEACHER_NAME}", exact=True)
    time.sleep(1.3)
    shot("23b_intake_thanks")  # "Thank you. The teacher will place you soon."
    time.sleep(3)
    log_out("Me")

    # ---- the teacher: Today, Neha placed, Rohan moved, the class's review, then feedback for Asha ----
    video = p.Recording(viz.tours(version) / f"teacher_tour_{version}.mp4")
    p.tap("I'm the teacher")
    log_in(*TEACHER)
    shot("24_teacher_today")
    tap_scrolling("Share", exact=True)  # the next class, on its batch's everyday link: the share sheet
    time.sleep(2.5)
    shot("25_teacher_share")  # the message names the batch
    p.back()
    time.sleep(1)
    find_scrolling("https://meet.google.com/def-ghij-klm")  # the last batch's everyday link
    bring("https://meet.google.com/def-ghij-klm", 1950)  # the four links in frame, the group code below them out of it
    shot("26_teacher_batches")
    p.tap("Students", exact=True)
    time.sleep(2)
    p.frame("Neha Rao", "New password")  # her whole card, below the shared notes
    shot("27_students_waiting")  # the waiting student's answers and the batch they point to
    p.tap("See all", exact=True)
    time.sleep(1)
    shot("28_students_intake")
    p.type_into("A note for the review (optional)", "Knee pain on stairs; start with the gentle sequence")
    p.hide_keyboard()
    tap_scrolling("Approve into")
    time.sleep(2)
    p.frame(None, "How each item has gone")  # the shared notes, then the first student's whole card
    shot("29_students_placed")  # each with a batch and since when
    p.tap_under("Rohan Desai", "Move to batch")
    p.tap_under("Rohan Desai", "Intermediate")
    p.type_under("Rohan Desai", "Steady now; ready for longer holds")
    p.frame("Rohan Desai", "How each item has gone")
    shot("30_move_batch")
    p.tap_under("Rohan Desai", "Move to Intermediate")
    time.sleep(2)
    p.scroll_to_top()
    p.frame("Rohan Desai", "How each item has gone")
    shot("30b_rohan_moved")  # "Intermediate · since" today
    p.tap("Insights", exact=True)
    time.sleep(2)
    shot("33_insights")
    tap_scrolling("How each item went")
    time.sleep(2)
    shot("34_class_review")  # strain or pain first: Asha's wrists in Surya Namaskar
    p.back()
    p.tap("Students", exact=True)
    time.sleep(2)
    p.tap_under("Asha Kulkarni", "How each item has gone ›")
    time.sleep(2)
    shot("31_asha_items")
    tap_scrolling("Surya Namaskar")
    time.sleep(2)
    p.type_into("Write to Asha", "Spread your fingers and press through the knuckles; in the plank, knees down for now.")
    p.hide_keyboard()
    p.tap("Send", exact=True)
    time.sleep(2)
    shot("32_feedback_sent")  # "You wrote", an answer to her strain
    video.stop()
    p.back()
    p.back()
    log_out("Today")

    # ---- Neha, placed ----
    p.tap("I'm a student")
    log_in(*WAITING)
    shot("27b_neha_today")  # her batch now, after the teacher placed her
    log_out("Me")

    # ---- Asha: her practice, with the teacher's word on Surya Namaskar ----
    p.tap("I'm a student")
    log_in(*STUDENT)
    p.tap("Practice", exact=True)
    time.sleep(2)
    p.frame(None, "Vajrasana")
    shot("07_practice")
    tap_scrolling("Surya Namaskar")
    time.sleep(2)
    shot("08_item_history")  # the teacher's note, and her strain in today's class
    p.back()

    # ---- Asha: on her own, with the stopwatch ----
    p.tap("Practise on your own")
    time.sleep(1)
    p.type_into("Search by name", "vajra")
    p.tap("+ Vajrasana")
    p.tap("vajra", exact=True)  # the search box, to search again
    p.adb("shell", "input", "keyevent", "KEYCODE_MOVE_END")
    for _ in range(5):
        p.adb("shell", "input", "keyevent", "KEYCODE_DEL")
    p.type_text("bhuj")
    p.tap("+ Bhujangasana")
    p.hide_keyboard()
    shot("09_solo_choose")
    tap_scrolling("Start (2)", exact=True)
    time.sleep(1)
    p.tap("Start the stopwatch")
    time.sleep(39)
    shot_at = time.time()
    shot("10a_solo_running")  # about 0:40
    time.sleep(50 - (time.time() - shot_at))  # a hold of about a minute and a half, the dump's seconds included
    p.tap("Stop", exact=True)
    p.tap("Steady", exact=True)
    p.type_into("Add a note", "Cushion under the ankles; no knee pain")
    p.hide_keyboard()
    shot("10_solo_item")
    tap_scrolling("Next", exact=True)
    p.tap("Start the stopwatch")
    time.sleep(40)
    p.tap("Stop", exact=True)
    p.tap("At ease", exact=True)
    tap_scrolling("Finish", exact=True)
    time.sleep(1.3)
    shot("11_solo_saved")
    tap_scrolling("Vajrasana")
    time.sleep(2)
    shot("12_history_solo")  # this practice the latest
    p.back()  # to the Practice screen
    time.sleep(2)
    p.frame(None, "Vajrasana")
    shot("12b_practice_after_solo")  # as 07, with this practice counted

    # ---- Asha: Ask and Me ----
    p.tap("Ask", exact=True)
    p.find("How is my", timeout=600)  # Gemma starts on the first visit
    shot("13_ask")
    for attempt in range(1, 4):  # the answer must hold to her data; a wrong one is asked again in a fresh chat
        p.tap("How is my")  # the suggestion about her own asana that most needs attention: Surya Namaskar
        p.find("Looked at that asana", timeout=180)
        answer = settled_answer()
        wrong = misreadings(answer)
        print(f"14_ask_asana, try {attempt}: {'holds' if not wrong else 'wrong: ' + '; '.join(wrong)}\n  {answer}")
        if not wrong or attempt == 3:
            break
        p.tap("Clear", exact=True)
    shot("14_ask_asana")
    p.type_into("Type your question", "Please remember that my wrists ache after planks.")
    shot("14a_ask_typing")  # the box stays above the keyboard
    p.tap("Send", exact=True)
    p.find("Saved a note", timeout=180)
    p.hide_keyboard()
    time.sleep(1)
    shot("15_ask_remember")
    p.tap("Me", exact=True)
    p.find("plank")  # under "My health notes", in the words Gemma saved it in
    time.sleep(1)
    shot("16_me")
    p.tap(f"Share with {p.TEACHER_NAME}")
    p.tap("Share", exact=True)  # in the dialog that asks first
    time.sleep(1.3)
    shot("16b_me_shared")
    p.scroll_down()
    shot("17_me_privacy")

    # ---- Asha: Hindi and Marathi ----
    language("हिन्दी", "Me")
    p.tap("आज", exact=True)
    time.sleep(1.5)
    shot("18_today_hindi")
    p.tap("पूछें", exact=True)
    p.tap(CLEAR_HI, exact=True)  # the English conversation stays on the phone; cleared, the Hindi suggestions show
    p.tap("कैसा चल रहा है")  # the Hindi suggestion about her own asana
    p.find("उस आसन को देखा", timeout=180)
    time.sleep(1)
    shot("19_ask_hindi")
    language("मराठी", "मैं")
    p.tap("सराव", exact=True)
    time.sleep(2)
    shot("20_practice_marathi")
    language("English", "मी")
    tap_scrolling("Log out")

    for name in ("student_tour", "teacher_tour"):
        make_small(viz.tours(version) / f"{name}_{version}.mp4", viz.tours(version) / f"{name}_{version}_small.mp4")
    viz.keep_screens(version)
    print(f"saved to {viz.screens(version)}")


def todays_class() -> str:
    """The start of today's 8:00 class in India, in UTC, as the dev backend takes it."""
    india = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(india).replace(hour=8, minute=0, second=0, microsecond=0).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def tap_scrolling(text: str, exact: bool = False) -> None:
    """Taps `text`, scrolling down until it is on screen."""
    for _ in range(12):
        try:
            p.find(text, timeout=1.5, exact=exact)
            break
        except TimeoutError:
            p.scroll_down()
    p.tap(text, exact=exact)


def find_scrolling(text: str) -> None:
    """Scrolls down until `text` is on screen."""
    for _ in range(12):
        try:
            p.find(text, timeout=1.5)
            return
        except TimeoutError:
            p.scroll_down()
    raise TimeoutError(f"'{text}' not on screen")


def bring(text: str, y: int) -> None:
    """Scrolls so the element showing `text` sits at height `y` on the screen: a slow swipe, so the page stops there."""
    _, at = p.center(p.find(text))
    p.adb("shell", "input", "swipe", "540", "1200", "540", str(max(150, min(2200, 1200 + y - at))), "1500")
    time.sleep(1)


TOOLS = ("Looked at", "Checked the", "Read the studio", "Read your notes", "Saved a note")  # the pills under an answer


def settled_answer() -> str:
    """Gemma's answer on screen once it has stopped growing: the text between the question and the tools it used."""
    answer = ""
    for _ in range(20):
        texts = [p.label(n) for n, _ in p.nodes() if p.label(n)]
        asked = next(i for i, t in enumerate(texts) if t.startswith("How is my"))
        words = []
        for t in texts[asked + 1:]:
            if t.startswith(TOOLS):
                break
            words.append(t)
        if " ".join(words) == answer:
            return answer
        answer = " ".join(words)
        time.sleep(2)
    return answer


def misreadings(answer: str) -> list[str]:
    """Where an answer about Asha's Surya Namaskar parts from her data: at ease twice, then steady, then today with
    effort and a strain in the wrists, and the teacher's word on it. Leaving one out is wrong, and so are words for the
    strain that the data does not hold, and counts that do not add up. Empty when nothing is found; read it as well."""
    text = answer.lower()
    wrong = [f"leaves out {what}" for what, words in (
        ("at ease", ("at ease",)), ("steady", ("steady",)), ("with effort", ("effort",)), ("the wrists", ("wrist",)),
        ("the teacher's word", ("knuckle", "fingers", "knees down"))) if not any(w in text for w in words)]
    wrong += [f"says '{w}'" for w in ("slight", "mild", "minor", "a little", "a bit", "small", "severe", "always") if w in text]
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if re.search(r"\b(two|twice|both|three|all)\b(?:(?!ease)[^.;]){0,40}\bsteady\b|\bsteady\b[^.;]{0,20}\b(twice|two times|both)\b",
                     sentence):
            wrong.append(f"counts steady more than once: '{sentence}'")
        if re.search(r"\b(three|3|all|every)\b(?:(?!steady)[^.;]){0,40}\bat ease\b|\bat ease\b[^.;]{0,25}\b(three|3|all|every)\b", sentence):
            wrong.append(f"counts at ease more than twice: '{sentence}'")
    return wrong


def make_small(video: Path, small: Path) -> None:
    """A 540 px copy, the source for the GIFs and the narrated video."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=540:-2,fps=24", "-c:v", "libx264",
                    "-crf", "30", "-preset", "slow", "-an", "-movflags", "+faststart", str(small)], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
