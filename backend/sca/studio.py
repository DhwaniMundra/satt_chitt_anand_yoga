"""The studio's classes and weekly rhythm, and the concrete class sessions made from them."""

import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sca.db import iso, now, parse_iso

IST = timezone(timedelta(hours=5, minutes=30))
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
LANGS = ("en", "hi", "mr")
MEET_LINK = re.compile(r"^https://(meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}|([\w-]+\.)?zoom\.us/j/\d+(\?pwd=[\w.-]+)?)$")
GROUP_LINK = re.compile(r"^https://chat\.whatsapp\.com/[A-Za-z0-9]+$")


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def pick(text: dict, lang: str) -> str:
    """One language out of a {"en": ..., "hi": ..., "mr": ...} dict, falling back to English."""
    return text.get(lang) or text["en"]


def clean_meet_link(raw: str) -> str:
    """A Google Meet or Zoom link, with https:// added when it was left off.

    Raises:
        ValueError: if it is not a Meet or Zoom meeting link.
    """
    link = raw.strip()
    if not link.startswith("https://"):
        link = "https://" + link.removeprefix("http://")
    if not MEET_LINK.match(link):
        raise ValueError("meet_link")
    return link


def clean_group_link(raw: str) -> str:
    """A WhatsApp group invite link, with https:// added when it was left off.

    Raises:
        ValueError: if it is not a chat.whatsapp.com invite link.
    """
    link = raw.strip()
    if not link.startswith("https://"):
        link = "https://" + link.removeprefix("http://")
    if not GROUP_LINK.match(link):
        raise ValueError("group_link")
    return link


def ensure_week(conn: sqlite3.Connection, studio: dict, moment: datetime) -> None:
    """Makes sure a session row exists for each of the 7 days starting with `moment`'s IST date."""
    hour, minute = map(int, studio["class_start_ist"].split(":"))
    today = moment.astimezone(IST).date()
    for offset in range(7):
        day = today + timedelta(days=offset)
        start = datetime(day.year, day.month, day.day, hour, minute, tzinfo=IST)
        conn.execute(
            "INSERT OR IGNORE INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES (?, ?, ?, ?)",
            (studio["weekly"][DAYS[day.weekday()]], iso(start), studio["duration_min"], iso(now())),
        )
    conn.commit()


def upcoming(conn: sqlite3.Connection, studio: dict, moment: datetime, limit: int = 7) -> list[sqlite3.Row]:
    """Sessions that have not ended yet, soonest first."""
    ensure_week(conn, studio, moment)
    rows = conn.execute("SELECT * FROM class_sessions WHERE starts_at >= ? ORDER BY starts_at", (iso(moment - timedelta(hours=2)),))
    return [r for r in rows if parse_iso(r["starts_at"]) + timedelta(minutes=r["duration_min"]) > moment][:limit]


def class_info(studio: dict, key: str, lang: str) -> dict:
    entry = next(c for c in studio["classes"] if c["key"] == key)
    return {"key": key, "name": pick(entry["name"], lang), "level": pick(entry["level"], lang), "about": pick(entry["about"], lang)}


def session_json(studio: dict, row: sqlite3.Row, lang: str, show_link: bool, default_link: str | None) -> dict:
    """A session for the app. The meeting link is only shown to approved members; a session without its own
    link uses the teacher's standing link."""
    link = row["meet_link"] or default_link
    return {
        "id": row["id"],
        "starts_at": row["starts_at"],
        "duration_min": row["duration_min"],
        "class": class_info(studio, row["class_key"], lang),
        "meet_link": link if show_link else None,
        "has_link": link is not None,
    }


def studio_json(studio: dict, lang: str) -> dict:
    teacher = studio["teacher"]
    return {
        "name": pick(studio["name"], lang),
        "tagline": pick(studio["tagline"], lang),
        "since": studio["since"],
        "teacher": {"name": teacher["name"], "title": pick(teacher["title"], lang), "bio": pick(teacher["bio"], lang)},
        "classes": [class_info(studio, c["key"], lang) for c in studio["classes"]],
        "weekly": [{"day": day, "class": class_info(studio, studio["weekly"][day], lang)} for day in DAYS],
        "class_start_ist": studio["class_start_ist"],
        "duration_min": studio["duration_min"],
    }
