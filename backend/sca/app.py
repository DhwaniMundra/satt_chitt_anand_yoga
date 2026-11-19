"""The HTTP API the Android app talks to.

Errors come back as {"detail": "<code>"} with a short machine-readable code that the app translates.
Run with `scripts/run_backend.sh`; settings come from the environment (see `Config.from_env`).
"""

import hashlib
import json
import logging
import os
import sqlite3
import threading
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from sca import auth, db, studio as studio_mod, whatsapp
from sca.assistant import Assistant, Busy
from sca.companion import Companion, practice_summary, tools_json
from sca.backup import GitHubBackup
from sca.studio import IST

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
log = logging.getLogger("sca")
Lang = Literal["en", "hi", "mr"]
CHECKIN_BEFORE_MIN = 60  # how early before class the "before" check-in opens


@dataclass(frozen=True)
class Config:
    db_path: Path
    gemma: str  # "gpu", "cpu" or "off"
    model_path: Path
    cache_dir: Path
    teacher_code: str | None = None
    backup_repo: str | None = None
    github_token: str | None = None
    backup_every_s: int = 600
    public_url: str | None = None  # the address phones use, e.g. http://192.168.1.20:8000; shown in the invite
    studio_path: Path = BACKEND / "content" / "studio.json"
    notes_path: Path = BACKEND / "knowledge" / "yoga_health.md"

    @staticmethod
    def from_env() -> "Config":
        return Config(
            db_path=Path(os.environ.get("SCA_DB", ROOT / "data" / "sca.sqlite3")),
            gemma=os.environ.get("SCA_GEMMA", "gpu"),
            model_path=Path(os.environ.get("SCA_MODEL", ROOT / "models" / "gemma-4-E4B-it" / "gemma-4-E4B-it.litertlm")),
            cache_dir=ROOT / "data" / "litert_cache",
            teacher_code=os.environ.get("SCA_TEACHER_CODE"),
            backup_repo=os.environ.get("SCA_BACKUP_REPO"),
            github_token=os.environ.get("SCA_GITHUB_TOKEN"),
            backup_every_s=int(os.environ.get("SCA_BACKUP_EVERY_S", "600")),
            public_url=os.environ.get("SCA_PUBLIC_URL"),
        )


# ---------- request bodies ----------


class SignupIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str
    password: str = Field(min_length=6, max_length=200)
    role: Literal["student", "teacher"] = "student"
    code: str = ""
    lang: Lang = "en"
    research_consent: bool = False


class LoginIn(BaseModel):
    phone: str
    password: str


class MeIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    lang: Lang | None = None
    research_consent: bool | None = None


class CodeIn(BaseModel):
    code: str


class CheckinIn(BaseModel):
    phase: Literal["before", "after"]
    mood: int = Field(ge=1, le=5)


class FeedbackIn(BaseModel):
    screen: str = Field(max_length=40)
    text: str = Field(min_length=1, max_length=2000)


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    lang: Lang = "en"


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    lang: Lang = "en"


class SharedIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class LinkIn(BaseModel):
    meet_link: str


class SettingsIn(BaseModel):
    group_link: str | None = None
    default_meet_link: str | None = None


class StatusIn(BaseModel):
    status: Literal["approved", "rejected"]


# ---------- helpers ----------


def user_json(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "phone": row["phone"],
        "role": row["role"],
        "status": row["status"],
        "lang": row["lang"],
        "research_consent": bool(row["research_consent"]),
    }


def practice_stats(conn: sqlite3.Connection, user_id: int) -> dict:
    """Classes joined, the current run of consecutive days with a class, and the average mood change."""
    days = sorted(
        {
            db.parse_iso(r["starts_at"]).astimezone(IST).date()
            for r in conn.execute(
                "SELECT s.starts_at FROM checkins c JOIN class_sessions s ON s.id = c.session_id "
                "WHERE c.user_id = ? AND c.phase = 'before'",
                (user_id,),
            )
        },
        reverse=True,
    )
    today = db.now().astimezone(IST).date()
    days = [d for d in days if d <= today]  # a check-in for a later class does not count yet
    streak, expected = 0, today
    if days and days[0] < expected:
        expected -= timedelta(days=1)  # today's class may not have happened yet
    for day in days:
        if day != expected:
            break
        streak += 1
        expected -= timedelta(days=1)
    change = conn.execute(
        "SELECT AVG(a.mood - b.mood), COUNT(*) FROM checkins b JOIN checkins a ON a.user_id = b.user_id "
        "AND a.session_id = b.session_id AND a.phase = 'after' WHERE b.phase = 'before' AND b.user_id = ?",
        (user_id,),
    ).fetchone()
    return {"classes_joined": len(days), "streak_days": streak, "mood_change": change[0], "mood_pairs": change[1]}


def create_app(config: Config) -> FastAPI:
    studio = studio_mod.load(config.studio_path)
    assistant = Assistant(config.notes_path, studio["name"]["en"], studio["teacher"]["short"])
    backup = GitHubBackup(config.backup_repo, config.github_token) if config.backup_repo and config.github_token else None
    stop = threading.Event()

    def backup_loop() -> None:
        last = None
        while not stop.wait(config.backup_every_s):
            conn = db.connect(config.db_path)
            try:
                data = db.export_rows(conn)
            finally:
                conn.close()
            digest = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            if digest != last:
                try:
                    backup.push(data)
                    last = digest
                    log.info("backup pushed to %s", config.backup_repo)
                except Exception as error:  # noqa: BLE001 - keep serving; the next round retries
                    log.warning("backup failed: %s", error)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        conn = db.connect(config.db_path)
        if backup is not None and db.is_empty(conn):
            saved = backup.pull()
            if saved is not None:
                db.import_rows(conn, saved)
                log.info("restored the database from %s", config.backup_repo)
        if config.teacher_code:
            db.set_setting(conn, "teacher_code", config.teacher_code.strip().upper())
        elif db.get_setting(conn, "teacher_code") is None:
            db.set_setting(conn, "teacher_code", auth.new_code(8))
        if db.get_setting(conn, "group_code") is None:
            db.set_setting(conn, "group_code", auth.new_code())
        if conn.execute("SELECT 1 FROM users WHERE role = 'teacher'").fetchone() is None:
            log.warning("Teacher sign-up code: %s", db.get_setting(conn, "teacher_code"))
        conn.close()
        if config.gemma != "off":
            threading.Thread(
                target=assistant.load_gemma, args=(config.model_path, config.gemma, config.cache_dir), daemon=True
            ).start()
        if backup is not None:
            threading.Thread(target=backup_loop, daemon=True).start()
        yield
        stop.set()

    app = FastAPI(title="Satt Chitt Anand", lifespan=lifespan)
    app.state.assistant = assistant
    companion = Companion(assistant, studio, config.db_path)
    logins = auth.Attempts()  # per phone number
    codes = auth.Attempts()  # per user entering a group code

    def get_db() -> Iterator[sqlite3.Connection]:
        conn = db.connect(config.db_path)
        try:
            yield conn
        finally:
            conn.close()

    def current_user(authorization: str = Header(default=""), conn: sqlite3.Connection = Depends(get_db)) -> sqlite3.Row:
        token = authorization.removeprefix("Bearer ").strip()
        row = conn.execute(
            "SELECT u.* FROM tokens t JOIN users u ON u.id = t.user_id WHERE t.token = ?", (token,)
        ).fetchone()
        if row is None:
            raise HTTPException(401, "signed_out")
        return row

    def teacher(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
        if user["role"] != "teacher":
            raise HTTPException(403, "teacher_only")
        return user

    def sign_in(conn: sqlite3.Connection, user: sqlite3.Row) -> dict:
        token = auth.new_token()
        conn.execute("INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)", (token, user["id"], db.iso(db.now())))
        conn.commit()
        return {"token": token, "user": user_json(user)}

    def session_row(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
        row = conn.execute("SELECT * FROM class_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            raise HTTPException(404, "no_session")
        return row

    def share_for(conn: sqlite3.Connection, row: sqlite3.Row, lang: str) -> dict:
        link = row["meet_link"] or db.get_setting(conn, "default_meet_link")
        if link is None:
            raise HTTPException(400, "no_link")
        name = studio_mod.class_info(studio, row["class_key"], lang)["name"]
        text = whatsapp.class_message(studio, name, db.parse_iso(row["starts_at"]), row["duration_min"], link, lang)
        return {"text": text, "url": whatsapp.share_url(text), "group_link": db.get_setting(conn, "group_link")}

    # ---------- public ----------

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "assistant": assistant.status, "model": assistant.gemma.name if assistant.gemma else None}

    @app.get("/studio")
    def get_studio(lang: Lang = "en") -> dict:
        return studio_mod.studio_json(studio, lang)

    @app.post("/auth/signup")
    def signup(body: SignupIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
        try:
            phone = auth.normalize_phone(body.phone)
        except ValueError:
            raise HTTPException(400, "bad_phone") from None
        code = body.code.strip().upper()
        if body.role == "teacher":
            if conn.execute("SELECT 1 FROM users WHERE role = 'teacher'").fetchone() is not None:
                raise HTTPException(409, "teacher_exists")  # one teacher per studio; the code no longer works
            if logins.blocked("teacher-code"):
                raise HTTPException(429, "too_many_attempts")
            if code != db.get_setting(conn, "teacher_code"):
                logins.fail("teacher-code")
                raise HTTPException(400, "bad_teacher_code")
            status = "approved"
        elif code:
            if code != db.get_setting(conn, "group_code"):
                raise HTTPException(400, "bad_group_code")
            status = "approved"
        else:
            status = "pending"
        try:
            cursor = conn.execute(
                "INSERT INTO users (name, phone, role, status, pw_hash, lang, research_consent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (body.name.strip(), phone, body.role, status, auth.hash_password(body.password), body.lang,
                 int(body.research_consent), db.iso(db.now())),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(409, "phone_taken") from None
        conn.commit()
        return sign_in(conn, conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone())

    @app.post("/auth/login")
    def login(body: LoginIn, conn: sqlite3.Connection = Depends(get_db)) -> dict:
        try:
            phone = auth.normalize_phone(body.phone)
        except ValueError:
            raise HTTPException(400, "bad_phone") from None
        if logins.blocked(phone):
            raise HTTPException(429, "too_many_attempts")
        row = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
        if row is None or not auth.check_password(body.password, row["pw_hash"]):
            logins.fail(phone)
            raise HTTPException(401, "bad_login")
        logins.clear(phone)
        return sign_in(conn, row)

    # ---------- signed in ----------

    @app.post("/auth/logout")
    def logout(authorization: str = Header(default=""), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        conn.execute("DELETE FROM tokens WHERE token = ?", (authorization.removeprefix("Bearer ").strip(),))
        conn.commit()
        return {"ok": True}

    @app.get("/me")
    def me(user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        return {"user": user_json(user), "stats": practice_stats(conn, user["id"])}

    @app.post("/me")
    def update_me(body: MeIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if body.name is not None:
            conn.execute("UPDATE users SET name = ? WHERE id = ?", (body.name.strip(), user["id"]))
        if body.lang is not None:
            conn.execute("UPDATE users SET lang = ? WHERE id = ?", (body.lang, user["id"]))
        if body.research_consent is not None:
            conn.execute("UPDATE users SET research_consent = ? WHERE id = ?", (int(body.research_consent), user["id"]))
            if not body.research_consent:  # withdrawing consent removes what it allowed
                conn.execute("UPDATE questions SET user_id = NULL, question = NULL, sources = '[]' WHERE user_id = ?", (user["id"],))
        conn.commit()
        return {"user": user_json(conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())}

    @app.post("/me/group_code")
    def join_group(body: CodeIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """A pending student who later gets the group code from the WhatsApp group is approved at once."""
        key = str(user["id"])
        if codes.blocked(key):
            raise HTTPException(429, "too_many_attempts")
        if body.code.strip().upper() != db.get_setting(conn, "group_code"):
            codes.fail(key)
            raise HTTPException(400, "bad_group_code")
        conn.execute("UPDATE users SET status = 'approved' WHERE id = ? AND status = 'pending'", (user["id"],))
        conn.commit()
        return {"user": user_json(conn.execute("SELECT * FROM users WHERE id = ?", (user["id"],)).fetchone())}

    @app.get("/home")
    def home(lang: Lang = "en", user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """Everything the student's Today screen needs in one call."""
        moment = db.now()
        member = user["status"] == "approved"
        default_link = db.get_setting(conn, "default_meet_link")
        sessions = [
            studio_mod.session_json(studio, r, lang, member, default_link) for r in studio_mod.upcoming(conn, studio, moment)
        ]
        for s in sessions:
            s["checked_in"] = conn.execute(
                "SELECT 1 FROM checkins WHERE user_id = ? AND session_id = ? AND phase = 'before'", (user["id"], s["id"])
            ).fetchone() is not None
        # The last class this person joined that has (nearly) ended and has no "after" check-in yet.
        waiting = conn.execute(
            "SELECT s.* FROM checkins b JOIN class_sessions s ON s.id = b.session_id "
            "WHERE b.user_id = ? AND b.phase = 'before' AND s.starts_at <= ? AND NOT EXISTS (SELECT 1 FROM checkins a "
            "WHERE a.user_id = b.user_id AND a.session_id = b.session_id AND a.phase = 'after') "
            "ORDER BY s.starts_at DESC LIMIT 1",
            (user["id"], db.iso(moment)),
        ).fetchone()
        after = None
        if waiting is not None:
            end = db.parse_iso(waiting["starts_at"]) + timedelta(minutes=waiting["duration_min"])
            if end - timedelta(minutes=10) <= moment <= end + timedelta(hours=12):
                after = studio_mod.session_json(studio, waiting, lang, False, None)
        return {
            "user": user_json(user),
            "studio": studio_mod.studio_json(studio, lang),
            "sessions": sessions,
            "after_checkin": after,
            "group_link": db.get_setting(conn, "group_link") if member else None,
        }

    @app.post("/sessions/{session_id}/checkin")
    def checkin(
        session_id: int, body: CheckinIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
    ) -> dict:
        if user["status"] != "approved":
            raise HTTPException(403, "pending")
        row = session_row(conn, session_id)
        start = db.parse_iso(row["starts_at"])
        end = start + timedelta(minutes=row["duration_min"])
        moment = db.now()
        if body.phase == "before":
            open_ = start - timedelta(minutes=CHECKIN_BEFORE_MIN) <= moment <= end
        else:
            joined = conn.execute(
                "SELECT 1 FROM checkins WHERE user_id = ? AND session_id = ? AND phase = 'before'", (user["id"], session_id)
            ).fetchone()
            open_ = joined is not None and end - timedelta(minutes=10) <= moment <= end + timedelta(hours=12)
        if not open_:
            raise HTTPException(400, "checkin_closed")
        conn.execute(
            "INSERT INTO checkins (user_id, session_id, phase, mood, created_at) VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id, session_id, phase) DO UPDATE SET mood = excluded.mood",
            (user["id"], session_id, body.phase, body.mood, db.iso(db.now())),
        )
        conn.commit()
        return {"ok": True, "stats": practice_stats(conn, user["id"])}

    @app.post("/feedback")
    def feedback(body: FeedbackIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        conn.execute(
            "INSERT INTO feedback (user_id, screen, text, created_at) VALUES (?, ?, ?, ?)",
            (user["id"], body.screen, body.text.strip(), db.iso(db.now())),
        )
        conn.commit()
        return {"ok": True}

    @app.post("/ask")
    def ask(body: AskIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if user["status"] != "approved":
            raise HTTPException(403, "pending")
        try:
            answer = assistant.ask(body.question.strip(), body.lang)
        except Busy:
            raise HTTPException(503, "busy") from None
        # Health questions are personal. Without research consent the studio keeps only that a question was asked
        # (language, path, time taken): not the words, not the topic, not who asked.
        consent = bool(user["research_consent"])
        conn.execute(
            "INSERT INTO questions (user_id, lang, question, sources, mode, latency_s, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"] if consent else None, body.lang, body.question if consent else None,
             json.dumps(answer.sources if consent else []), answer.mode, answer.latency_s, db.iso(db.now())),
        )
        conn.commit()
        return {"answer": answer.text, "sources": answer.sources, "mode": answer.mode, "latency_s": round(answer.latency_s, 2)}

    # ---------- the practice companion ----------

    def chat_rows(conn: sqlite3.Connection, user_id: int, limit: int) -> list[sqlite3.Row]:
        rows = conn.execute(
            "SELECT * FROM chat_messages WHERE user_id = ? ORDER BY id DESC LIMIT ?", (user_id, limit)
        ).fetchall()
        return rows[::-1]

    @app.get("/chat")
    def chat_history(user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """This student's conversation with the companion, oldest first. Only they can read it."""
        return {"messages": [{"role": r["role"], "text": r["text"], "tools": json.loads(r["tools"]), "mode": r["mode"],
                              "created_at": r["created_at"]} for r in chat_rows(conn, user["id"], 60)]}

    @app.post("/chat")
    def chat(body: ChatIn, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if user["role"] == "student" and user["status"] != "approved":
            raise HTTPException(403, "pending")
        history = [(r["role"], r["text"]) for r in chat_rows(conn, user["id"], 12)]
        try:
            reply = companion.chat(user, body.message.strip(), body.lang, history)
        except Busy:
            raise HTTPException(503, "busy") from None
        moment = db.iso(db.now())
        conn.execute("INSERT INTO chat_messages (user_id, role, text, created_at) VALUES (?, 'student', ?, ?)",
                     (user["id"], body.message.strip(), moment))
        labels = tools_json(reply.tools)
        conn.execute("INSERT INTO chat_messages (user_id, role, text, tools, mode, created_at) VALUES (?, 'companion', ?, ?, ?, ?)",
                     (user["id"], reply.text, labels, reply.mode, moment))
        # What the studio may see, as for /ask: without research consent, not the words, not the topic, not who asked.
        consent = bool(user["research_consent"])
        conn.execute(
            "INSERT INTO questions (user_id, lang, question, sources, mode, latency_s, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user["id"] if consent else None, body.lang, body.message if consent else None,
             labels if consent else "[]", reply.mode, reply.latency_s, moment),
        )
        conn.commit()
        return {"reply": reply.text, "tools": json.loads(labels), "mode": reply.mode, "latency_s": round(reply.latency_s, 2)}

    @app.delete("/chat")
    def clear_chat(user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        conn.execute("DELETE FROM chat_messages WHERE user_id = ?", (user["id"],))
        conn.commit()
        return {"ok": True}

    @app.get("/me/notes")
    def my_notes(user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """What the companion remembers for this student."""
        rows = conn.execute("SELECT id, text, created_at FROM companion_notes WHERE user_id = ? ORDER BY id", (user["id"],))
        return {"notes": [dict(r) for r in rows]}

    @app.delete("/me/notes/{note_id}")
    def forget_note(note_id: int, user: sqlite3.Row = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if conn.execute("DELETE FROM companion_notes WHERE id = ? AND user_id = ?", (note_id, user["id"])).rowcount == 0:
            raise HTTPException(404, "no_note")
        conn.commit()
        return {"ok": True}

    # ---------- for Gemma on the phone ----------
    # The companion runs on the student's phone. It asks the server only for the student's own practice summary (the
    # schedule comes from /home); its chat and notes stay on the phone, and a note reaches the teacher only when the
    # student shares it, one note at a time.

    def member(user: sqlite3.Row = Depends(current_user)) -> sqlite3.Row:
        if user["role"] == "student" and user["status"] != "approved":
            raise HTTPException(403, "pending")
        return user

    @app.get("/me/practice")
    def my_practice(days: int = 7, lang: Lang = "en", user: sqlite3.Row = Depends(member),
                    conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """This student's classes over the last `days` days (1 to 90) with the sums done: what the get_my_practice tool
        returns. Class names in `lang`, as on /home."""
        return practice_summary(conn, studio, user["id"], days, lang)

    @app.post("/me/shared")
    def share_note(body: SharedIn, user: sqlite3.Row = Depends(member), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """One note the student chose to share with the teacher. Sharing the same words again returns the same note."""
        if user["role"] != "student":
            raise HTTPException(403, "pending")
        text = body.text.strip()
        if not text:
            raise HTTPException(422, "empty_note")
        row = conn.execute("SELECT id FROM shared_notes WHERE user_id = ? AND text = ?", (user["id"], text)).fetchone()
        if row is None:
            row = {"id": conn.execute("INSERT INTO shared_notes (user_id, text, created_at) VALUES (?, ?, ?)",
                                      (user["id"], text, db.iso(db.now()))).lastrowid}
            conn.commit()
        return {"ok": True, "id": row["id"]}

    # ---------- teacher ----------

    @app.get("/teacher/home")
    def teacher_home(lang: Lang = "en", _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        default_link = db.get_setting(conn, "default_meet_link")
        sessions = []
        for row in studio_mod.upcoming(conn, studio, db.now()):
            s = studio_mod.session_json(studio, row, lang, True, default_link)
            s["own_link"] = row["meet_link"] is not None
            s["joined"] = conn.execute(
                "SELECT COUNT(*) FROM checkins WHERE session_id = ? AND phase = 'before'", (row["id"],)
            ).fetchone()[0]
            sessions.append(s)
        return {
            "sessions": sessions,
            "settings": {
                "group_link": db.get_setting(conn, "group_link"),
                "group_code": db.get_setting(conn, "group_code"),
                "default_meet_link": default_link,
            },
            "pending_students": conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0],
        }

    @app.put("/teacher/sessions/{session_id}")
    def set_link(
        session_id: int, body: LinkIn, lang: Lang = "en", _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)
    ) -> dict:
        session_row(conn, session_id)
        try:
            link = studio_mod.clean_meet_link(body.meet_link)
        except ValueError:
            raise HTTPException(400, "bad_meet_link") from None
        conn.execute("UPDATE class_sessions SET meet_link = ?, updated_at = ? WHERE id = ?", (link, db.iso(db.now()), session_id))
        conn.commit()
        return share_for(conn, session_row(conn, session_id), lang)

    @app.get("/teacher/sessions/{session_id}/share")
    def share(session_id: int, lang: Lang = "en", _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        return share_for(conn, session_row(conn, session_id), lang)

    @app.put("/teacher/settings")
    def update_settings(body: SettingsIn, _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        # Check both before saving either, so a bad link never leaves the other half-saved.
        updates = {}
        if body.group_link is not None:
            try:
                updates["group_link"] = studio_mod.clean_group_link(body.group_link)
            except ValueError:
                raise HTTPException(400, "bad_group_link") from None
        if body.default_meet_link is not None:
            try:
                updates["default_meet_link"] = studio_mod.clean_meet_link(body.default_meet_link)
            except ValueError:
                raise HTTPException(400, "bad_meet_link") from None
        for key, value in updates.items():
            db.set_setting(conn, key, value)
        return {key: db.get_setting(conn, key) for key in ("group_link", "group_code", "default_meet_link")}

    @app.post("/teacher/group_code")
    def rotate_group_code(_: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        db.set_setting(conn, "group_code", auth.new_code())
        return {"group_code": db.get_setting(conn, "group_code")}

    @app.get("/teacher/invite")
    def invite(lang: Lang = "en", _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        text = whatsapp.invite_message(studio, db.get_setting(conn, "group_code"), lang, config.public_url)
        return {"text": text, "url": whatsapp.share_url(text), "group_link": db.get_setting(conn, "group_link")}

    @app.get("/teacher/students")
    def students(_: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        rows = conn.execute(
            "SELECT u.*, (SELECT COUNT(*) FROM checkins c WHERE c.user_id = u.id AND c.phase = 'before') AS joined "
            "FROM users u WHERE u.role = 'student' ORDER BY u.status = 'pending' DESC, u.created_at DESC"
        )
        return {"students": [{**user_json(r), "joined": r["joined"], "created_at": r["created_at"]} for r in rows]}

    @app.get("/teacher/shared")
    def shared_notes(_: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """The notes students chose to share, newest first (the last 50)."""
        rows = conn.execute(
            "SELECT n.id, n.user_id, u.name, n.text, n.created_at FROM shared_notes n JOIN users u ON u.id = n.user_id "
            "ORDER BY n.created_at DESC, n.id DESC LIMIT 50"
        )
        return {"shared": [dict(r) for r in rows]}

    @app.post("/teacher/students/{user_id}/status")
    def set_status(
        user_id: int, body: StatusIn, _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)
    ) -> dict:
        if conn.execute("UPDATE users SET status = ? WHERE id = ? AND role = 'student'", (body.status, user_id)).rowcount == 0:
            raise HTTPException(404, "no_student")
        conn.commit()
        return {"ok": True}

    @app.post("/teacher/students/{user_id}/password")
    def reset_password(user_id: int, _: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """A new temporary password for a student who forgot theirs; the teacher passes it on in person or on
        WhatsApp. Signs the student out everywhere."""
        password = auth.new_code(8)
        if conn.execute(
            "UPDATE users SET pw_hash = ? WHERE id = ? AND role = 'student'", (auth.hash_password(password), user_id)
        ).rowcount == 0:
            raise HTTPException(404, "no_student")
        conn.execute("DELETE FROM tokens WHERE user_id = ?", (user_id,))
        conn.commit()
        return {"password": password}

    @app.get("/teacher/insights")
    def insights(_: sqlite3.Row = Depends(teacher), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        """How the last two weeks of classes went, from the students' one-tap check-ins and feedback."""
        moment = db.now()
        rows = conn.execute(
            "SELECT s.id, s.class_key, s.starts_at, "
            "SUM(c.phase = 'before') AS joined, AVG(CASE WHEN c.phase = 'before' THEN c.mood END) AS mood_before, "
            "AVG(CASE WHEN c.phase = 'after' THEN c.mood END) AS mood_after, SUM(c.phase = 'after') AS answered_after "
            "FROM class_sessions s LEFT JOIN checkins c ON c.session_id = s.id "
            "WHERE s.starts_at BETWEEN ? AND ? GROUP BY s.id ORDER BY s.starts_at DESC",
            (db.iso(moment - timedelta(days=14)), db.iso(moment)),
        )
        sessions = [
            {
                "id": r["id"],
                "starts_at": r["starts_at"],
                "class": studio_mod.class_info(studio, r["class_key"], "en")["name"],
                "joined": r["joined"] or 0,
                "mood_before": r["mood_before"],
                "mood_after": r["mood_after"],
                "answered_after": r["answered_after"] or 0,
            }
            for r in rows
        ]
        change = conn.execute(
            "SELECT AVG(a.mood - b.mood), COUNT(*) FROM checkins b JOIN checkins a ON a.user_id = b.user_id "
            "AND a.session_id = b.session_id AND a.phase = 'after' WHERE b.phase = 'before'"
        ).fetchone()
        counts = dict(conn.execute("SELECT status, COUNT(*) FROM users WHERE role = 'student' GROUP BY status").fetchall())
        asked = conn.execute("SELECT COUNT(*), AVG(CASE WHEN mode IN ('gemma', 'companion') THEN latency_s END) FROM questions").fetchone()
        notes = conn.execute(
            "SELECT f.screen, f.text, f.created_at, u.name FROM feedback f JOIN users u ON u.id = f.user_id "
            "ORDER BY f.created_at DESC LIMIT 20"
        )
        return {
            "students": {"approved": counts.get("approved", 0), "pending": counts.get("pending", 0)},
            "mood_change": change[0],
            "mood_pairs": change[1],
            "sessions": sessions,
            "questions": {"count": asked[0], "gemma_latency_s": asked[1]},
            "feedback": [dict(r) for r in notes],
        }

    return app


def main() -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    uvicorn.run(create_app(Config.from_env()), host=os.environ.get("SCA_HOST", "0.0.0.0"), port=int(os.environ.get("SCA_PORT", "8000")))


if __name__ == "__main__":
    main()
