"""Walks through the app on the emulator and saves the same screenshots and two screen recordings every time,
so each iteration can be compared with the last: .local/visualization/viz_<major>/screens/<version>/ (gitignored;
scripts/make_figures.py turns the best of it into the committed GIFs and contact sheets in docs/media/).

Needs: `source scripts/env.sh`, the 6 GB emulator running (SCA_AVD=sca_phone_big scripts/run_emulator.sh) with
Gemma downloaded in Ask, and nothing else on port 8000. The tour starts the dev backend on a fresh copy of the
synthetic demo (data/tour.json), adds an Intermediate class under way so both check-ins are open, and starts the app
signed out with no chat or notes, so a second run shows the same screens.

The student, Asha (Intermediate): Today, joining, how the class went, the Practice tab and an asana's history, a
practice on her own with the stopwatch, Ask about her own asana, Me, then Hindi and Marathi. Neha, waiting to be
placed, and her answers about herself. The teacher: Today by batch and a batch's share, Students with Neha's answers,
approving her into the batch they point to, moving a student with a note, Asha's asana with feedback, Insights and the
review of the class.

Usage: python3 scripts/capture_tour.py v1.0
"""

import subprocess
import sys
import time
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
        p.add_class("intermediate", -47)  # under way, 8 minutes left: both check-ins are open
        tour(version)


def tour(version: str) -> None:
    out = viz.screens(version)
    out.mkdir(parents=True, exist_ok=True)

    def shot(name: str) -> None:
        p.screenshot(out / f"{name}.png")  # at the phone's own size, for the film's close-ups

    def log_in(number: str, password: str) -> None:
        p.tap("Log in", exact=True)
        p.type_into("WhatsApp number", number)
        p.type_into("Password", password)
        p.hide_keyboard()
        p.tap("Log in", exact=True, last=True)  # the button under the form, not the switch above it
        time.sleep(3)

    def language(name: str, me: str) -> None:
        p.tap(me, exact=True)
        time.sleep(1.5)
        tap_scrolling(name, exact=True)
        time.sleep(3)

    p.adb("install", "-r", str(APK))
    p.adb("shell", "cmd", "alarm", "set-timezone", "Asia/Kolkata")
    p.demo_mode()
    p.launch(fresh=True)

    # ---- student: a class ----
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
    shot("05a_after_class_items")
    tap_scrolling("Done", exact=True)
    time.sleep(2)
    shot("06_after_sent")
    p.tap("Practice", exact=True)
    time.sleep(2)
    shot("07_practice")
    video.stop()

    tap_scrolling("Vajrasana")
    time.sleep(2)
    shot("08_item_history")
    p.back()

    # ---- student: on her own, with the stopwatch ----
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
    time.sleep(90)  # a hold of about a minute and a half
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
    shot("12_history_solo")
    p.back()

    # ---- student: Ask and Me ----
    p.tap("Ask", exact=True)
    p.find("How is my", timeout=600)  # Gemma starts on the first visit
    shot("13_ask")
    p.tap("How is my")  # the suggestion about her own asana that most needs attention
    p.find("Looked at that asana", timeout=180)
    time.sleep(1)
    shot("14_ask_asana")
    p.type_into("Type your question", "Please remember that my left knee hurts in Vajrasana.")
    shot("14a_ask_typing")  # the box stays above the keyboard
    p.tap("Send", exact=True)
    p.find("Saved a note", timeout=180)
    p.hide_keyboard()
    time.sleep(1)
    shot("15_ask_remember")
    p.tap("Me", exact=True)
    p.find("left knee hurts")  # under "My health notes"
    time.sleep(1)
    shot("16_me")
    p.scroll_down()
    shot("17_me_privacy")

    # ---- student: Hindi and Marathi ----
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
    time.sleep(1.5)

    # ---- a student waiting to be placed: Neha, her answers given ----
    p.tap("I'm a student")
    log_in(*WAITING)
    shot("21_waiting")
    p.tap(f"Tell {p.TEACHER_NAME} about yourself")
    time.sleep(2)
    shot("22_intake")  # her answers, as she gave them
    p.adb("shell", "input", "swipe", "540", "1700", "540", "500", "600")
    time.sleep(1)
    shot("23_intake_poses")
    p.back()
    p.tap("Me", exact=True)
    tap_scrolling("Log out")
    time.sleep(1.5)

    # ---- teacher ----
    video = p.Recording(viz.folder(version) / f"teacher_tour_{version}.mp4")
    p.tap("I'm the teacher")
    log_in(*TEACHER)
    shot("24_teacher_today")
    tap_scrolling("Share on WhatsApp", exact=True)  # the class under way, on its batch's everyday link
    time.sleep(2.5)
    shot("25_teacher_share")  # the message names the batch
    p.back()
    time.sleep(1)
    p.scroll_down()
    shot("26_teacher_batches")
    p.tap("Students", exact=True)
    time.sleep(2)
    shot("27_students_waiting")  # the waiting student's answers and the batch they point to
    p.tap("See all", exact=True)
    time.sleep(1)
    shot("28_students_intake")
    p.type_into("A note for the review (optional)", "Knee pain on stairs; start with the gentle sequence")
    p.hide_keyboard()
    tap_scrolling("Approve into")
    time.sleep(2)
    p.scroll_to_top()
    shot("29_students_placed")  # each with a batch and since when
    p.tap_under("Rohan Desai", "Move to batch")
    p.tap_under("Rohan Desai", "Intermediate")
    p.type_under("Rohan Desai", "Steady in the standing poses; ready for longer holds")
    shot("30_move_batch")
    p.tap_under("Rohan Desai", "Move to Intermediate")
    time.sleep(2)
    p.scroll_to_top()
    p.tap_under("Asha Kulkarni", "How each item has gone ›")
    time.sleep(2)
    shot("31_asha_items")
    p.tap("Vajrasana")
    time.sleep(2)
    p.type_into("Write to Asha", "Good hold at 1:30. Keep the cushion, and come out at the first sign of knee pain.")
    p.hide_keyboard()
    p.tap("Send", exact=True)
    time.sleep(2)
    shot("32_feedback_sent")  # "You wrote"
    p.back()
    p.back()
    p.tap("Insights", exact=True)
    time.sleep(2)
    shot("33_insights")
    tap_scrolling("How each item went")
    time.sleep(2)
    shot("34_class_review")  # strain or pain first
    video.stop()

    # ---- Neha, placed ----
    p.tap("Today", exact=True)
    tap_scrolling("Log out")
    time.sleep(1.5)
    p.tap("I'm a student")
    log_in(*WAITING)
    shot("29b_neha_today")  # her batch now, after the teacher placed her (29)

    for name in ("student_tour", "teacher_tour"):
        make_small(viz.folder(version) / f"{name}_{version}.mp4", out / f"{name}_small.mp4")
    print(f"saved to {out}")


def tap_scrolling(text: str, exact: bool = False) -> None:
    """Taps `text`, scrolling down until it is on screen."""
    for _ in range(12):
        try:
            p.find(text, timeout=1.5, exact=exact)
            break
        except TimeoutError:
            p.scroll_down()
    p.tap(text, exact=exact)


def make_small(video: Path, small: Path) -> None:
    """A 540 px copy, the source for the GIFs and the narrated video."""
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", "scale=540:-2,fps=24", "-c:v", "libx264",
                    "-crf", "30", "-preset", "slow", "-an", "-movflags", "+faststart", str(small)], check=True)


if __name__ == "__main__":
    main(sys.argv[1])
