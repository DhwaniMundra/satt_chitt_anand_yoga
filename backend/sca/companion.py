"""The practice companion: a chat with Gemma 4 that can look things up for one student and remember what they ask it to.

Gemma gets five tools, each bound to the student it is talking with, so it can only ever see that student's data:
their practice (classes, moods before and after, computed into summaries here, because a small model adds up rows
badly), the coming classes, the studio's notes, and their own saved notes. The emergency check of assistant.py still
runs first, with no model involved. Each request rebuilds the conversation from the last few saved messages, so no
chat state lives in the server's memory.
"""

import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from sca import db, studio as studio_mod
from sca.assistant import LANGUAGE_NAMES, URGENT_REPLY, Assistant, Busy, is_urgent

HISTORY_TURNS = 6  # earlier messages replayed as context; lasting facts belong in saved notes
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


def upcoming_classes(conn: sqlite3.Connection, studio: dict) -> dict:
    out = []
    for r in studio_mod.upcoming(conn, studio, db.now()):
        info = studio_mod.class_info(studio, r["class_key"], "en")
        start = db.parse_iso(r["starts_at"]).astimezone(studio_mod.IST)
        today = db.now().astimezone(studio_mod.IST).date()
        when = {0: "today", 1: "tomorrow"}.get((start.date() - today).days, start.strftime("%A %d %B"))
        out.append({"when": when, "time": start.strftime("%-I:%M %p") + " India time", "class": info["name"],
                    "level": info["level"], "about": info["about"]})
    return {"classes": out}


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
        c = conn()
        try:
            c.execute("INSERT INTO companion_notes (user_id, text, created_at) VALUES (?, ?, ?)",
                      (user_id, note.strip()[:500], db.iso(db.now())))
            c.commit()
            return {"saved": True}
        finally:
            c.close()

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
        system = SYSTEM.format(studio=self.studio["name"]["en"], name=user["name"].split()[0],
                               teacher=self.studio["teacher"]["short"], language=LANGUAGE_NAMES[lang])
        preface = [{"role": "user" if role == "student" else "assistant", "content": text}
                   for role, text in history[-HISTORY_TURNS:]]
        if not self.assistant.slots.acquire(blocking=False):
            raise Busy
        try:
            text = gemma.chat(system, preface, message, tools, ban_foreign_scripts=lang == "mr")
        finally:
            self.assistant.slots.release()
        return Reply(text, used, "companion", time.perf_counter() - start)


def tools_json(tools: list[str]) -> str:
    return json.dumps([TOOL_LABELS.get(t, t) for t in dict.fromkeys(tools)])
