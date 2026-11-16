"""The API end to end, with Gemma off (the assistant answers from the notes)."""

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient

from sca import db
from sca.app import Config, create_app


@pytest.fixture
def client(tmp_path):
    config = Config(db_path=tmp_path / "t.sqlite3", gemma="off", model_path=tmp_path / "none", cache_dir=tmp_path, teacher_code="TEACH123")
    with TestClient(create_app(config)) as c:
        yield c


def signup(client, phone, role="student", code="", consent=False):
    r = client.post(
        "/auth/signup",
        json={"name": f"{role} {phone}", "phone": phone, "password": "secret1", "role": role, "code": code, "research_consent": consent},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}, r.json()["user"]


def test_teacher_needs_the_teacher_code(client):
    r = client.post("/auth/signup", json={"name": "x", "phone": "9000000001", "password": "secret1", "role": "teacher", "code": "nope"})
    assert r.json()["detail"] == "bad_teacher_code"
    _, user = signup(client, "9000000001", role="teacher", code="teach123")
    assert user["role"] == "teacher" and user["phone"] == "+919000000001"


def test_student_with_group_code_is_approved_and_without_is_pending(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
    _, with_code = signup(client, "9000000002", code=code.lower())
    _, without = signup(client, "9000000003")
    assert with_code["status"] == "approved" and without["status"] == "pending"
    r = client.post("/auth/signup", json={"name": "x", "phone": "9000000004", "password": "secret1", "code": "WRONG1"})
    assert r.json()["detail"] == "bad_group_code"


def test_duplicate_phone_and_login(client):
    signup(client, "+91 90000 00002")
    r = client.post("/auth/signup", json={"name": "x", "phone": "9000000002", "password": "secret1"})
    assert r.status_code == 409
    assert client.post("/auth/login", json={"phone": "9000000002", "password": "wrong"}).status_code == 401
    assert client.post("/auth/login", json={"phone": "09000000002"[1:], "password": "secret1"}).status_code == 200


def test_pending_student_sees_no_link_until_approved(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    s, student = signup(client, "9000000002")
    session = client.get("/teacher/home", headers=t).json()["sessions"][0]
    r = client.put(f"/teacher/sessions/{session['id']}", json={"meet_link": "meet.google.com/abc-defg-hij"}, headers=t)
    assert r.status_code == 200
    assert "https://meet.google.com/abc-defg-hij" in r.json()["text"] and r.json()["url"].startswith("https://wa.me/?text=")
    first = client.get("/home", headers=s).json()["sessions"][0]
    assert first["meet_link"] is None and first["has_link"]
    assert client.post(f"/sessions/{session['id']}/checkin", json={"phase": "before", "mood": 3}, headers=s).status_code == 403
    assert client.post(f"/teacher/students/{student['id']}/status", json={"status": "approved"}, headers=t).status_code == 200
    assert client.get("/home", headers=s).json()["sessions"][0]["meet_link"] == "https://meet.google.com/abc-defg-hij"


def test_bad_links_are_refused(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    session = client.get("/teacher/home", headers=t).json()["sessions"][0]
    r = client.put(f"/teacher/sessions/{session['id']}", json={"meet_link": "https://evil.example/meet"}, headers=t)
    assert r.json()["detail"] == "bad_meet_link"
    assert client.put("/teacher/settings", json={"group_link": "https://example.com"}, headers=t).json()["detail"] == "bad_group_link"
    ok = client.put("/teacher/settings", json={"group_link": "https://chat.whatsapp.com/AbC123", "default_meet_link": "https://meet.google.com/xyz-abcd-efg"}, headers=t)
    assert ok.json()["group_link"] == "https://chat.whatsapp.com/AbC123"


def test_standing_link_is_used_when_a_session_has_none(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    client.put("/teacher/settings", json={"default_meet_link": "https://meet.google.com/xyz-abcd-efg"}, headers=t)
    code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
    s, _ = signup(client, "9000000002", code=code)
    assert all(x["meet_link"] == "https://meet.google.com/xyz-abcd-efg" for x in client.get("/home", headers=s).json()["sessions"])


def test_students_cannot_use_teacher_routes(client):
    s, _ = signup(client, "9000000002")
    assert client.get("/teacher/students", headers=s).status_code == 403
    assert client.get("/home").status_code == 401


def test_checkins_feed_stats_and_insights(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
    s, _ = signup(client, "9000000002", code=code)
    session_id = client.get("/teacher/home", headers=t).json()["sessions"][0]["id"]
    assert client.post(f"/sessions/{session_id}/checkin", json={"phase": "before", "mood": 2}, headers=s).status_code == 200
    assert client.post(f"/sessions/{session_id}/checkin", json={"phase": "after", "mood": 5}, headers=s).status_code == 200
    stats = client.get("/me", headers=s).json()["stats"]
    assert stats["classes_joined"] == 1 and stats["mood_change"] == 3 and stats["mood_pairs"] == 1
    insights = client.get("/teacher/insights", headers=t).json()
    assert insights["mood_change"] == 3 and insights["students"] == {"approved": 1, "pending": 0}


def test_after_checkin_is_offered_once_class_ends(client, tmp_path):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
    s, _ = signup(client, "9000000002", code=code)
    conn = db.connect(tmp_path / "t.sqlite3")
    start = db.now() - timedelta(minutes=60)
    cur = conn.execute(
        "INSERT INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES ('hatha', ?, 55, ?)",
        (db.iso(start), db.iso(db.now())),
    )
    conn.commit()
    client.post(f"/sessions/{cur.lastrowid}/checkin", json={"phase": "before", "mood": 3}, headers=s)
    assert client.get("/home", headers=s).json()["after_checkin"]["id"] == cur.lastrowid
    client.post(f"/sessions/{cur.lastrowid}/checkin", json={"phase": "after", "mood": 4}, headers=s)
    assert client.get("/home", headers=s).json()["after_checkin"] is None


def test_question_text_is_kept_only_with_consent(client, tmp_path):
    s1, _ = signup(client, "9000000002", consent=True)
    s2, _ = signup(client, "9000000003", consent=False)
    for headers in (s1, s2):
        r = client.post("/ask", json={"question": "What should I eat before class?", "lang": "en"}, headers=headers)
        assert r.json()["mode"] == "notes" and r.json()["sources"] == ["Food and water around practice"]
    kept = [r[0] for r in db.connect(tmp_path / "t.sqlite3").execute("SELECT question FROM questions ORDER BY id")]
    assert kept == ["What should I eat before class?", None]


def test_reset_password_signs_the_student_out(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    s, student = signup(client, "9000000002")
    password = client.post(f"/teacher/students/{student['id']}/password", headers=t).json()["password"]
    assert client.get("/me", headers=s).status_code == 401
    assert client.post("/auth/login", json={"phone": "9000000002", "password": password}).status_code == 200


def test_pending_student_can_enter_the_group_code_later(client):
    t, _ = signup(client, "9000000001", role="teacher", code="TEACH123")
    s, _ = signup(client, "9000000002")
    assert client.post("/me/group_code", json={"code": "WRONG1"}, headers=s).json()["detail"] == "bad_group_code"
    code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
    assert client.post("/me/group_code", json={"code": code}, headers=s).json()["user"]["status"] == "approved"
    assert client.post("/me", json={"lang": "mr", "research_consent": True}, headers=s).json()["user"]["lang"] == "mr"
