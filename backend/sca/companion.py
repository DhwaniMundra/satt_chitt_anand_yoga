"""The practice companion: a chat with Gemma 4 that can look things up for one student and remember what they ask it to.

Gemma gets five tools, each bound to the student it is talking with, so it can only ever see that student's data:
their practice (classes, moods before and after, computed into summaries here, because a small model adds up rows
badly), the coming classes, the studio's notes, and their own saved notes. The emergency check of assistant.py still
runs first, with no model involved. Each request rebuilds the conversation from the last few saved messages, so no
chat state lives in the server's memory.
"""

import json
import re
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sca import db, studio as studio_mod
from sca.assistant import LANGUAGE_NAMES, URGENT_REPLY, Assistant, Busy, is_urgent

HISTORY_TURNS = 6  # earlier messages replayed as context; lasting facts belong in saved notes
# Words that make a message about the class schedule, in English, Hindi and Marathi. Such messages get the coming
# classes up front: both models asked for clarification instead of checking the schedule in Marathi, and E4B gave
# the wrong day for "tomorrow" when it read dates itself (docs/iterations/v0.5.md).
SCHEDULE_WORDS = ("class", "tomorrow", "today", "next", "schedule", "कक्षा", "क्लास", "कल ", "आज", "अगल", "कब",
                  "वर्ग", "उद्या", "पुढ", "कधी")
# The words the app teaches for saving a note (Me, "What I remember": say "Remember that…"), at the start of a message.
REMEMBER = re.compile(r"\s*(?:please\s+)?remember\s+that\s+|\s*(?:कृपया\s+)?याद\s+रख(?:ना|ें|िए|ो)\s+कि\s+"
                      r"|\s*(?:कृपया\s+)?लक्षात\s+ठेवा\s+की\s+", re.IGNORECASE)
TOOL_LABELS = {  # what the app shows under a reply that used a tool
    "get_my_practice": "practice",
    "get_upcoming_classes": "schedule",
    "search_studio_notes": "notes",
    "save_my_note": "saved",
    "get_my_notes": "memory",
}

SYSTEM = """You are the practice companion in the {studio} app, talking with one student, {name}. You can look up their
own practice, the studio's coming classes and the studio's notes, and save notes they ask you to remember.

Rules:
1. For anything about this student's practice, classes or moods, call a tool first and use only what it returns. Never
   invent numbers or dates. Report summaries exactly as the tool gives them.
2. For yoga or health guidance, call search_studio_notes and answer only from what it returns.
3. When the student asks you to remember something, call save_my_note. When they ask what they told you, call
   get_my_notes.
4. You are not a doctor: never diagnose, never promise a cure, never tell anyone to start, change or stop a medicine.
   For pain, illness, pregnancy or medicine, give only gentle general guidance and say to ask their doctor and to tell
   {teacher} before class.
5. Keep replies short and warm: at most 90 words.
6. Reply only in {language}."""


@dataclass(frozen=True)
class Reply:
    text: str
    tools: list[str]  # names of the tools used, in order
    mode: str  # "companion", "notes" (no model loaded) or "urgent"
    latency_s: float


def practice_summary(conn: sqlite3.Connection, studio: dict, user_id: int, days: int) -> dict:
    """The student's classes over the last `days` days, with the sums done: classes joined, average mood before and
    after, and the same per class."""
    days = max(1, min(int(days), 90))
    rows = conn.execute(
        "SELECT s.starts_at, s.class_key, b.mood AS before, a.mood AS after FROM checkins b "
        "JOIN class_sessions s ON s.id = b.session_id LEFT JOIN checkins a ON a.user_id = b.user_id "
        "AND a.session_id = b.session_id AND a.phase = 'after' WHERE b.user_id = ? AND b.phase = 'before' "
        "AND s.starts_at >= ? AND s.starts_at <= ? ORDER BY s.starts_at",
        (user_id, db.iso(db.now() - timedelta(days=days)), db.iso(db.now())),
    ).fetchall()

    def average(values: list[int]) -> float | None:
        return round(sum(values) / len(values), 1) if values else None

    classes, by_class = [], {}
    for r in rows:
        name = studio_mod.class_info(studio, r["class_key"], "en")["name"]
        when = db.parse_iso(r["starts_at"]).astimezone(studio_mod.IST)
        classes.append({"date": when.strftime("%a %d %b"), "class": name, "mood_before": r["before"], "mood_after": r["after"]})
        entry = by_class.setdefault(name, {"times": 0, "before": [], "after": []})
        entry["times"] += 1
        entry["before"].append(r["before"])
        if r["after"] is not None:
            entry["after"].append(r["after"])
    return {
        "period_days": days,
        "classes_joined": len(classes),
        "mood_scale": "1 very low to 5 great",
        "average_mood_before": average([r["before"] for r in rows]),
        "average_mood_after": average([r["after"] for r in rows if r["after"] is not None]),
        "by_class": {name: {"times": e["times"], "average_mood_before": average(e["before"]),
                            "average_mood_after": average(e["after"])} for name, e in by_class.items()},
        "classes": classes,
    }


def upcoming_classes(conn: sqlite3.Connection, studio: dict, limit: int = 5) -> dict:
    """The next classes, each with an unambiguous day: "tomorrow, Friday 20 November"."""
    out = []
    today = db.now().astimezone(studio_mod.IST).date()
    for r in studio_mod.upcoming(conn, studio, db.now(), limit):
        info = studio_mod.class_info(studio, r["class_key"], "en")
        start = db.parse_iso(r["starts_at"]).astimezone(studio_mod.IST)
        date = start.strftime("%A %-d %B")
        day = {0: f"today, {date}", 1: f"tomorrow, {date}"}.get((start.date() - today).days, date)
        out.append({"day": day, "time": start.strftime("%-I:%M %p") + " India time", "class": info["name"],
                    "level": info["level"], "about": info["about"]})
    return {"today_is": today.strftime("%A %-d %B"), "classes": out}


def tools_for(db_path: Path, studio: dict, assistant: Assistant, user_id: int, lang: str, used: list[str]) -> list[Callable]:
    """The companion's tools, bound to one student. Each records its own name in `used`."""

    def conn() -> sqlite3.Connection:
        return db.connect(db_path)

    def get_my_practice(days: int) -> dict:
        """This student's classes over the last `days` days, with how they felt before and after (summaries included).

        Args:
            days: how many days back to look, for example 7 for this week or 30 for this month.
        """
        used.append("get_my_practice")
        c = conn()
        try:
            return practice_summary(c, studio, user_id, days)
        finally:
            c.close()

    def get_upcoming_classes() -> dict:
        """The studio's classes in the coming week, soonest first: when, time, class, level."""
        used.append("get_upcoming_classes")
        c = conn()
        try:
            return upcoming_classes(c, studio)
        finally:
            c.close()

    def search_studio_notes(query: str) -> dict:
        """The studio's notes on yoga practice and everyday health that best match a question.

        Args:
            query: what to look up, in a few words, for example "back pain" or "food before class".
        """
        used.append("search_studio_notes")
        sections = assistant.retriever.top(query)
        own = assistant.translations.get(lang, {})
        return {"notes": [{"title": s.title, "text": own.get(s.title) or s.text} for s in sections]}

    def save_my_note(note: str) -> dict:
        """Saves something this student asks you to remember about their practice, such as a sore knee.

        Args:
            note: the note, in the student's own words.
        """
        used.append("save_my_note")
        save_note(db_path, user_id, note)
        return {"saved": True}

    def get_my_notes() -> dict:
        """The notes this student has asked you to remember, oldest first."""
        used.append("get_my_notes")
        c = conn()
        try:
            rows = c.execute("SELECT text, created_at FROM companion_notes WHERE user_id = ? ORDER BY id", (user_id,))
            return {"notes": [{"note": r["text"], "saved": r["created_at"][:10]} for r in rows]}
        finally:
            c.close()

    return [get_my_practice, get_upcoming_classes, search_studio_notes, save_my_note, get_my_notes]


class Companion:
    def __init__(self, assistant: Assistant, studio: dict, db_path: Path) -> None:
        self.assistant = assistant
        self.studio = studio
        self.db_path = db_path

    def prompt(self, user: sqlite3.Row, message: str, lang: str, history: list[tuple[str, str]], used: list[str]) -> tuple[str, list[dict]]:
        """The system message (with matching notes handed over up front) and the earlier messages, as Gemma gets them.
        One place, so the evaluation (scripts/eval_companion.py) sends exactly what the app sends."""
        system = SYSTEM.format(studio=self.studio["name"]["en"], name=user["name"].split()[0],
                               teacher=self.studio["teacher"]["short"], language=LANGUAGE_NAMES[lang])
        schedule = preloaded_schedule(self.db_path, self.studio, message, used)
        system += schedule + preloaded_notes(self.assistant, message, lang, used, schedule=bool(schedule))
        preface = [{"role": "user" if role == "student" else "assistant", "content": text}
                   for role, text in history[-HISTORY_TURNS:]]
        return system, preface

    def chat(self, user: sqlite3.Row, message: str, lang: str, history: list[tuple[str, str]]) -> Reply:
        """One reply to `message`. `history` holds the earlier messages, oldest first, as (role, text) with role
        "student" or "companion".

        Raises:
            Busy: if too many questions are already waiting for Gemma.
        """
        start = time.perf_counter()
        if is_urgent(message):
            return Reply(URGENT_REPLY[lang], [], "urgent", time.perf_counter() - start)
        gemma = self.assistant.gemma
        if gemma is None:  # no model: answer from the notes, as the Ask screen did before
            answer = self.assistant.ask(message, lang)
            return Reply(answer.text, ["search_studio_notes"] if answer.sources else [], answer.mode,
                         time.perf_counter() - start)
        used: list[str] = []
        tools = tools_for(self.db_path, self.studio, self.assistant, user["id"], lang, used)
        system, preface = self.prompt(user, message, lang, history, used)
        if not self.assistant.slots.acquire(blocking=False):
            raise Busy
        try:
            text = gemma.chat(system, preface, message, tools, ban_foreign_scripts=lang == "mr")
        finally:
            self.assistant.slots.release()
        save_if_asked(self.db_path, user["id"], message, used)
        return Reply(text, used, "companion", time.perf_counter() - start)


def save_note(db_path: Path, user_id: int, note: str) -> None:
    conn = db.connect(db_path)
    try:
        conn.execute("INSERT INTO companion_notes (user_id, text, created_at) VALUES (?, ?, ?)",
                     (user_id, note.strip()[:500], db.iso(db.now())))
        conn.commit()
    finally:
        conn.close()


def save_if_asked(db_path: Path, user_id: int, message: str, used: list[str]) -> bool:
    """Saves the note when `message` starts with the words the app teaches ("Remember that…") and Gemma did not call
    save_my_note: in a conversation that began with another question, E4B replied "I have saved that" without saving
    (docs/iterations/v0.5.md). Returns whether it saved."""
    match = REMEMBER.match(message)
    note = message[match.end():].strip() if match else ""
    if not note or "save_my_note" in used:
        return False
    save_note(db_path, user_id, note[0].upper() + note[1:])  # "My left knee…", as it reads in "What I remember"
    used.append("save_my_note")
    return True


def preloaded_schedule(conn_path: Path, studio: dict, message: str, used: list[str]) -> str:
    """The coming classes as text for the system message when `message` is about the schedule (or "")."""
    lowered = f"{message.lower()} "
    if not any(word in lowered for word in SCHEDULE_WORDS):
        return ""
    conn = db.connect(conn_path)
    try:
        schedule = upcoming_classes(conn, studio)
    finally:
        conn.close()
    used.append("get_upcoming_classes")
    lines = "\n".join(f"- {c['day']}: {c['class']} at {c['time']} ({c['level']})" for c in schedule["classes"])
    return f"\n\nToday is {schedule['today_is']}. The studio's coming classes. Answer from them:\n{lines}"


def preloaded_notes(assistant: Assistant, message: str, lang: str, used: list[str], schedule: bool = False) -> str:
    """The studio notes section on the topic `message` names, as text for the system message (or ""); records it as
    a use of search_studio_notes, since the student sees it the same way. Handed over up front rather than left to
    Gemma to search for: Gemma 4 E2B often answered health questions without searching (docs/iterations/v0.5.md).

    With the `schedule` already handed over, a class word does not name a topic: told to answer from "About the
    studio and classes", E2B answered "which class tomorrow?" with today's class."""
    ignore = tuple(w.strip() for w in SCHEDULE_WORDS) if schedule else ()
    section = assistant.retriever.named(message, ignore)
    if section is None:
        return ""
    text = assistant.translations.get(lang, {}).get(section.title) or section.text
    used.append("search_studio_notes")
    return f"\n\nThe studio's notes on what the student asks about. Answer from them:\n### {section.title}\n{text}"


def tools_json(tools: list[str]) -> str:
    return json.dumps([TOOL_LABELS.get(t, t) for t in dict.fromkeys(tools)])
