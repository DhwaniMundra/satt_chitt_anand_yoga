"""Fills a fresh database with SYNTHETIC demo data for screenshots and screen recordings.

Every person, check-in and comment here is invented. Never present the Insights screen of a demo database as
results: real numbers come only from real students who agreed to take part.

Usage (from backend/): .venv/bin/python -m scripts.seed_demo ../data/demo.sqlite3
Logins it creates (password "demo123" for all): teacher +919800000001, students +919800000002 to +919800000007.
"""

import random
import sys
from datetime import timedelta
from pathlib import Path

from sca import auth, db
from sca.studio import IST, ensure_week, load

STUDIO = Path(__file__).resolve().parents[1] / "content" / "studio.json"
STUDENTS = ["Asha Kulkarni", "Meera Iyer", "Rohan Desai", "Kavita Joshi", "Sunil Patil", "Neha Rao"]
FEEDBACK = [
    ("Asha Kulkarni", "The breathing circle helps me before sleep. Can it have a longer exhale option?"),
    ("Rohan Desai", "Join button is easy. I missed the link once because I opened WhatsApp first."),
    ("Meera Iyer", "Please add the Marathi names of the poses."),
]


def main(path: Path) -> None:
    if path.exists():
        sys.exit(f"{path} exists; delete it first so the demo starts clean")
    rng = random.Random(7)
    conn = db.connect(path)
    created = db.iso(db.now() - timedelta(days=20))
    password = auth.hash_password("demo123")
    conn.execute(
        "INSERT INTO users (name, phone, role, status, pw_hash, lang, created_at) VALUES (?, ?, 'teacher', 'approved', ?, 'en', ?)",
        ("Ramit (demo)", "+919800000001", password, created),
    )
    ids = []
    for i, name in enumerate(STUDENTS):
        status = "pending" if i == len(STUDENTS) - 1 else "approved"
        cur = conn.execute(
            "INSERT INTO users (name, phone, role, status, pw_hash, lang, research_consent, created_at) VALUES (?, ?, 'student', ?, ?, ?, 1, ?)",
            (name, f"+9198000000{i + 2:02d}", status, password, "en" if i % 3 else "hi", created),
        )
        ids.append((cur.lastrowid, status))
    conn.commit()
    db.set_setting(conn, "group_code", "SATT94")
    db.set_setting(conn, "default_meet_link", "https://meet.google.com/abc-defg-hij")

    # Two weeks of past classes, most students joining most days, with a before and (usually) an after check-in.
    studio = load(STUDIO)
    ensure_week(conn, studio, db.now() - timedelta(days=13))
    ensure_week(conn, studio, db.now() - timedelta(days=6))
    ensure_week(conn, studio, db.now())
    today = db.now().astimezone(IST).date()
    for row in conn.execute("SELECT * FROM class_sessions ORDER BY starts_at").fetchall():
        start = db.parse_iso(row["starts_at"])
        if start.astimezone(IST).date() >= today:
            continue
        for user_id, status in ids:
            if status != "approved" or rng.random() < 0.3:
                continue
            before = rng.choice([2, 3, 3, 3, 4])
            at = db.iso(start - timedelta(minutes=3))
            conn.execute("INSERT INTO checkins VALUES (?, ?, 'before', ?, ?)", (user_id, row["id"], before, at))
            if rng.random() < 0.8:
                after = min(5, before + rng.choice([0, 1, 1, 2]))
                conn.execute("INSERT INTO checkins VALUES (?, ?, 'after', ?, ?)", (user_id, row["id"], after, db.iso(start + timedelta(minutes=60))))
    for name, text in FEEDBACK:
        user_id = conn.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()[0]
        conn.execute("INSERT INTO feedback (user_id, screen, text, created_at) VALUES (?, 'me', ?, ?)", (user_id, text, db.iso(db.now())))
    conn.commit()
    print(f"demo database written to {path}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
