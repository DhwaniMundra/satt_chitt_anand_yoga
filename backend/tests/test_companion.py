"""The practice companion without the model: its tools, its routes, and the conversation it hands to Gemma (through
a stand-in that calls a tool the way the runtime would)."""

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from sca import db, studio as studio_mod
from sca.app import Config, create_app
from sca.assistant import Assistant
from sca.companion import HISTORY_TURNS, Companion, practice_summary, save_if_asked, tools_for

BACKEND = Path(__file__).resolve().parents[1]
STUDIO = studio_mod.load(BACKEND / "content" / "studio.json")


@pytest.fixture
def setup(tmp_path):
    config = Config(db_path=tmp_path / "t.sqlite3", gemma="off", model_path=tmp_path / "none", cache_dir=tmp_path, teacher_code="T1")
    with TestClient(create_app(config)) as client:
        t = signup(client, "9000000001", "Teacher", role="teacher", code="T1")
        code = client.get("/teacher/home", headers=t).json()["settings"]["group_code"]
        yield client, tmp_path / "t.sqlite3", code


def signup(client, phone, name, role="student", code=""):
    r = client.post("/auth/signup", json={"name": name, "phone": phone, "password": "secret1", "role": role, "code": code})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def user_id(client, headers):
    return client.get("/me", headers=headers).json()["user"]["id"]


def attend(path, uid, class_key, days_ago, before, after):
    conn = db.connect(path)
    start = (db.now() - timedelta(days=days_ago)).replace(second=0, microsecond=0)
    conn.execute("INSERT OR IGNORE INTO class_sessions (class_key, starts_at, duration_min, updated_at) VALUES (?, ?, 55, ?)",
                 (class_key, db.iso(start), db.iso(start)))  # classmates share the day's session
    sid = conn.execute("SELECT id FROM class_sessions WHERE starts_at = ?", (db.iso(start),)).fetchone()[0]
    conn.execute("INSERT INTO checkins VALUES (?, ?, 'before', ?, ?)", (uid, sid, before, db.iso(start)))
    if after is not None:
        conn.execute("INSERT INTO checkins VALUES (?, ?, 'after', ?, ?)", (uid, sid, after, db.iso(start)))
    conn.commit()


def test_practice_summary_does_the_sums_for_one_student(setup):
    client, path, code = setup
    asha = user_id(client, signup(client, "9000000002", "Asha", code=code))
    other = user_id(client, signup(client, "9000000003", "Ravi", code=code))
    attend(path, asha, "hatha", 1, 3, 4)
    attend(path, asha, "hatha", 3, 3, 5)
    attend(path, asha, "pranayama", 2, 2, None)
    attend(path, asha, "hatha", 20, 1, 1)  # outside the week
    attend(path, other, "hatha", 1, 5, 5)  # someone else's
    week = practice_summary(db.connect(path), STUDIO, asha, 7)
    assert week["classes_joined"] == 3
    assert week["average_mood_before"] == round(8 / 3, 1) and week["average_mood_after"] == 4.5
    assert week["by_class"]["Hatha Yoga"] == {"times": 2, "average_mood_before": 3.0, "average_mood_after": 4.5}
    assert week["by_class"]["Pranayama"]["average_mood_after"] is None


def test_notes_belong_to_one_student(setup):
    client, path, code = setup
    asha = user_id(client, signup(client, "9000000002", "Asha", code=code))
    ravi_headers = signup(client, "9000000003", "Ravi", code=code)
    used = []
    tools = {f.__name__: f for f in tools_for(path, STUDIO, Assistant(BACKEND / "knowledge" / "yoga_health.md", "x", "y"), asha, "en", used)}
    tools["save_my_note"]("left knee hurts in Vajrasana")
    assert tools["get_my_notes"]()["notes"][0]["note"] == "left knee hurts in Vajrasana"
    assert used == ["save_my_note", "get_my_notes"]
    assert client.get("/me/notes", headers=ravi_headers).json()["notes"] == []
    note_id = db.connect(path).execute("SELECT id FROM companion_notes").fetchone()[0]
    assert client.delete(f"/me/notes/{note_id}", headers=ravi_headers).status_code == 404  # not Ravi's to delete


def test_chat_is_saved_private_and_clearable(setup):
    client, path, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    ravi = signup(client, "9000000003", "Ravi", code=code)
    r = client.post("/chat", json={"message": "What should I eat before class?", "lang": "en"}, headers=asha)
    assert r.status_code == 200 and r.json()["mode"] == "notes" and r.json()["tools"] == ["notes"]
    messages = client.get("/chat", headers=asha).json()["messages"]
    assert [m["role"] for m in messages] == ["student", "companion"] and messages[1]["tools"] == ["notes"]
    assert client.get("/chat", headers=ravi).json()["messages"] == []
    client.delete("/chat", headers=asha)
    assert client.get("/chat", headers=asha).json()["messages"] == []


def test_chat_urgent_and_pending(setup):
    client, _, code = setup
    asha = signup(client, "9000000002", "Asha", code=code)
    assert client.post("/chat", json={"message": "I have chest pain", "lang": "hi"}, headers=asha).json()["mode"] == "urgent"
    assert client.get("/chat", headers=asha).json()["messages"][-1]["mode"] == "urgent"  # still red after a restart
    pending = signup(client, "9000000004", "Meera")
    assert client.post("/chat", json={"message": "hello", "lang": "en"}, headers=pending).json()["detail"] == "pending"


def test_chat_is_not_backed_up():
    assert "chat_messages" not in db.BACKUP_TABLES and "companion_notes" not in db.BACKUP_TABLES


def test_conversation_handed_to_gemma(setup):
    client, path, code = setup
    headers = signup(client, "9000000002", "Asha Kulkarni", code=code)
    asha = db.connect(path).execute("SELECT * FROM users WHERE phone = '+919000000002'").fetchone()
    attend(path, asha["id"], "hatha", 1, 3, 5)
    seen = {}

    class StandIn:
        """Calls a tool the way LiteRT-LM's automatic tool calling would, then answers from it."""

        def chat(self, system, preface, message, tools, ban_foreign_scripts=False):
            seen.update(system=system, preface=preface, tools=[t.__name__ for t in tools], ban=ban_foreign_scripts)
            practice = {t.__name__: t for t in tools}["get_my_practice"](7)
            return f"You joined {practice['classes_joined']} class."

    assistant = Assistant(BACKEND / "knowledge" / "yoga_health.md", "Satt Chitt Anand Yoga", "Ramit ji")
    assistant.gemma = StandIn()
    history = [("student", f"q{i}") if i % 2 == 0 else ("companion", f"a{i}") for i in range(10)]
    reply = Companion(assistant, STUDIO, path).chat(asha, "How was my week?", "mr", history)
    assert reply.text == "You joined 1 class." and reply.tools == ["get_my_practice"] and reply.mode == "companion"
    assert len(seen["preface"]) == HISTORY_TURNS and seen["preface"][-1] == {"role": "assistant", "content": "a9"}
    assert "Asha" in seen["system"] and "Marathi" in seen["system"] and seen["ban"] is True
    assert seen["tools"] == ["get_my_practice", "get_upcoming_classes", "search_studio_notes", "save_my_note", "get_my_notes"]
    assert headers  # the account exists for the route tests above


def test_matching_notes_are_handed_over_up_front():
    from sca.companion import preloaded_notes

    assistant = Assistant(BACKEND / "knowledge" / "yoga_health.md", "x", "y")
    used = []
    assert "पाठीवर" in preloaded_notes(assistant, "पाठदुखीसाठी योग?", "mr", used) and used == ["search_studio_notes"]
    assert preloaded_notes(assistant, "How was my practice this week?", "en", []) == ""
    assert "### Pregnancy" in preloaded_notes(assistant, "I am pregnant, can I join?", "en", [])
    assert "### Diabetes" in preloaded_notes(assistant, "Can I lower my metformin dose?", "en", [])
    # With the schedule handed over, "class" names no topic of its own; "back" still does.
    assert preloaded_notes(assistant, "कल कौन सी कक्षा है?", "hi", [], schedule=True) == ""
    assert "### Back pain" in preloaded_notes(assistant, "My lower back is stiff. Which class tomorrow?", "en", [], schedule=True)
    # Matches on words of a section's text only, not its topic: no notes, and no "Read the studio notes" under the reply.
    for message in ["How many classes did I join in the last 30 days?", "Do I usually feel better after class than before?",
                    "What did I tell you about my knee?"]:
        assert preloaded_notes(assistant, message, "en", []) == "", message


def test_a_note_asked_for_is_saved_even_if_gemma_only_says_so(setup):
    client, path, code = setup
    headers = signup(client, "9000000002", "Asha Kulkarni", code=code)
    asha = db.connect(path).execute("SELECT * FROM users WHERE phone = '+919000000002'").fetchone()

    class SaysSaved:
        def __init__(self, calls_tool):
            self.calls_tool = calls_tool

        def chat(self, system, preface, message, tools, ban_foreign_scripts=False):
            if self.calls_tool:
                {t.__name__: t for t in tools}["save_my_note"]("left knee hurts in Vajrasana")
            return "I have saved that for you."

    assistant = Assistant(BACKEND / "knowledge" / "yoga_health.md", "Satt Chitt Anand Yoga", "Ramit ji")
    companion = Companion(assistant, STUDIO, path)
    assistant.gemma = SaysSaved(calls_tool=False)
    reply = companion.chat(asha, "Please remember that my left knee hurts in Vajrasana.", "en", [("student", "How was my week?")])
    assert "save_my_note" in reply.tools
    assistant.gemma = SaysSaved(calls_tool=True)  # Gemma saved it: not saved twice
    companion.chat(asha, "Remember that my left knee hurts in Vajrasana", "en", [])
    notes = [n["text"] for n in client.get("/me/notes", headers=headers).json()["notes"]]
    assert notes == ["My left knee hurts in Vajrasana.", "left knee hurts in Vajrasana"]


@pytest.mark.parametrize(("message", "note"), [
    ("याद रखना कि मेरे घुटने में दर्द है", "मेरे घुटने में दर्द है"),
    ("कृपया लक्षात ठेवा की माझा गुडघा दुखतो", "माझा गुडघा दुखतो"),
    ("Do you remember that my knee hurts?", None),  # asking, not telling
    ("What did I tell you about my knee?", None),
])
def test_the_words_the_app_teaches_for_saving(setup, message, note):
    _, path, _ = setup
    used = []
    assert save_if_asked(path, 1, message, used) is (note is not None)
    rows = [r[0] for r in db.connect(path).execute("SELECT text FROM companion_notes")]
    assert rows == ([note] if note else [])
