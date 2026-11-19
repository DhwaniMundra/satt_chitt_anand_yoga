"""The routes Gemma on the phone uses: the student's practice summary, and the one way a note leaves the phone, sharing
it with the teacher. Also the class names the companion's tools give, in the student's language."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sca import db, studio as studio_mod
from sca.app import Config, create_app
from sca.companion import practice_summary, upcoming_classes

BACKEND = Path(__file__).resolve().parents[1]
STUDIO = studio_mod.load(BACKEND / "content" / "studio.json")


@pytest.fixture
def setup(tmp_path):
    config = Config(db_path=tmp_path / "t.sqlite3", gemma="off", model_path=tmp_path / "none", cache_dir=tmp_path, teacher_code="T1")
    with TestClient(create_app(config)) as client:
        teacher = signup(client, "9000000001", "Teacher", role="teacher", code="T1")
        code = client.get("/teacher/home", headers=teacher).json()["settings"]["group_code"]
        yield client, tmp_path / "t.sqlite3", teacher, code


def signup(client, phone, name, role="student", code=""):
    r = client.post("/auth/signup", json={"name": name, "phone": phone, "password": "secret1", "role": role, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def attend(path, uid, class_key, days_ago, before, after):
    conn = db.connect(path)
    start = (db.now() - timedelta(days=days_ago)).replace(second=0, microsecond=0)
    conn.execute("INSERT OR IGNORE INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES (?, ?, 55, ?)",
                 (class_key, db.iso(start), db.iso(start)))
    sid = conn.execute("SELECT id FROM class_sessions WHERE starts_at = ?", (db.iso(start),)).fetchone()[0]
    conn.execute("INSERT INTO checkins VALUES (?, ?, 'before', ?, ?)", (uid, sid, before, db.iso(start)))
    if after is not None:
        conn.execute("INSERT INTO checkins VALUES (?, ?, 'after', ?, ?)", (uid, sid, after, db.iso(start)))
    conn.commit()


def test_practice_summary_route_is_the_tools_summary_for_the_signed_in_student(setup):
    client, path, _, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    ravi = signup(client, "9000000003", "Ravi", code=code)
    asha_id = client.get("/me", headers=asha).json()["user"]["id"]
    attend(path, asha_id, "hatha", 1, 3, 4)
    attend(path, asha_id, "hatha", 3, 3, 5)
    attend(path, asha_id, "pranayama", 20, 2, None)
    week = client.get("/me/practice?days=7", headers=asha).json()
    assert week == practice_summary(db.connect(path), STUDIO, asha_id, 7)
    assert week["classes_joined"] == 2 and week["average_mood_after"] == 4.5
    assert client.get("/me/practice?days=30", headers=asha).json()["classes_joined"] == 3
    assert client.get("/me/practice?days=7", headers=ravi).json()["classes_joined"] == 0  # only one's own
    assert client.get("/me/practice?days=7").status_code == 401
    assert client.get("/me/practice", headers=asha).json()["period_days"] == 7  # a week unless asked
    assert client.get("/me/practice?days=400", headers=asha).json()["period_days"] == 90
    assert client.get("/me/practice?days=0", headers=asha).json()["period_days"] == 1


def test_practice_is_for_members_and_the_teacher(setup):
    client, _, teacher, _ = setup
    pending = signup(client, "9000000004", "Meera")
    assert client.get("/me/practice", headers=pending).json()["detail"] == "pending"
    assert set(client.get("/me/practice", headers=teacher).json()) == {
        "period_days", "classes_joined", "mood_scale", "average_mood_before", "average_mood_after", "by_class", "classes"}


def test_practice_and_schedule_name_classes_in_the_students_language(setup):
    client, path, _, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    attend(path, client.get("/me", headers=asha).json()["user"]["id"], "hatha", 1, 3, 4)
    assert list(client.get("/me/practice?days=7&lang=hi", headers=asha).json()["by_class"]) == ["हठ योग"]
    assert list(client.get("/me/practice?days=7&lang=mr", headers=asha).json()["by_class"]) == ["हठयोग"]
    assert list(client.get("/me/practice?days=7", headers=asha).json()["by_class"]) == ["Hatha Yoga"]
    conn = db.connect(path)
    names = {lang: [c["class"] for c in upcoming_classes(conn, STUDIO, lang=lang)["classes"]] for lang in ("en", "hi", "mr")}
    keys = [next(c["key"] for c in STUDIO["classes"] if c["name"]["en"] == name) for name in names["en"]]
    for lang in ("hi", "mr"):
        assert names[lang] == [studio_mod.class_info(STUDIO, k, lang)["name"] for k in keys]
        assert all(any("ऀ" <= ch <= "ॿ" for ch in name) for name in names[lang]), names[lang]


def test_a_shared_note_reaches_the_teacher_and_only_that_note(setup):
    client, _, teacher, code = setup
    asha = signup(client, "9000000002", "Asha Kulkarni", code=code)
    asha_id = client.get("/me", headers=asha).json()["user"]["id"]
    shared = client.post("/me/shared", json={"text": " My left knee hurts in Vajrasana. "}, headers=asha).json()
    assert shared["ok"] is True and isinstance(shared["id"], int)
    again = client.post("/me/shared", json={"text": "My left knee hurts in Vajrasana."}, headers=asha).json()
    assert again["id"] == shared["id"]  # a retried share is not a second note
    client.post("/me/shared", json={"text": "Sore wrist"}, headers=asha)
    notes = client.get("/teacher/shared", headers=teacher).json()["shared"]
    assert [(n["user_id"], n["name"], n["text"]) for n in notes] == [
        (asha_id, "Asha Kulkarni", "Sore wrist"), (asha_id, "Asha Kulkarni", "My left knee hurts in Vajrasana.")]  # newest first
    assert set(notes[0]) == {"id", "user_id", "name", "text", "created_at"}
    assert client.get("/teacher/shared", headers=asha).status_code == 403  # students cannot read them


def test_the_teacher_sees_the_last_fifty(setup):
    client, _, teacher, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    for i in range(55):
        client.post("/me/shared", json={"text": f"note {i}"}, headers=asha)
    notes = client.get("/teacher/shared", headers=teacher).json()["shared"]
    assert len(notes) == 50 and notes[0]["text"] == "note 54"


def test_sharing_is_for_approved_students_and_checks_the_note(setup):
    client, _, teacher, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    pending = signup(client, "9000000004", "Meera")
    assert client.post("/me/shared", json={"text": "x"}, headers=pending).json()["detail"] == "pending"
    assert client.post("/me/shared", json={"text": "x"}, headers=teacher).json()["detail"] == "pending"
    assert client.post("/me/shared", json={"text": ""}, headers=asha).status_code == 422
    assert client.post("/me/shared", json={"text": "   "}, headers=asha).status_code == 422
    assert client.post("/me/shared", json={"text": "x" * 501}, headers=asha).status_code == 422


def test_shared_notes_are_backed_up_but_chats_are_not():
    assert "shared_notes" in db.BACKUP_TABLES
    assert "chat_messages" not in db.BACKUP_TABLES and "companion_notes" not in db.BACKUP_TABLES
