"""Retrieval over the studio notes and the urgent path; no model involved."""

from pathlib import Path

import pytest

from sca.assistant import Assistant, Busy, is_urgent, load_sections, load_translation, tokenize

NOTES = Path(__file__).resolve().parents[1] / "knowledge" / "yoga_health.md"


@pytest.fixture(scope="module")
def assistant():
    return Assistant(NOTES, "Satt Chitt Anand Yoga", "Ramit ji")


def test_devanagari_words_stay_whole():
    assert tokenize("कमर दर्द, पाठदुखी!") == ["कमर", "दर्द", "पाठदुखी"]
    assert tokenize("मुझे कमर में दर्द है") == ["कमर", "दर्द"]  # function words dropped


def test_every_section_has_keywords_and_no_keywords_leak_into_text():
    sections = load_sections(NOTES)
    assert len(sections) >= 20
    for s in sections:
        assert s.text and "Keywords:" not in s.text, s.title


@pytest.mark.parametrize(
    ("question", "section"),
    [
        ("I have lower back pain, what can I do?", "Back pain"),
        ("कमर दर्द के लिए योग?", "Back pain"),
        ("मला पाठदुखी आहे", "Back pain"),
        ("Is kapalbhati safe with high BP?", "High blood pressure and the heart"),
        ("I am pregnant, can I join?", "Pregnancy"),
        ("गरोदरपणात योग करू शकते का?", "Pregnancy"),
        ("What time is the class?", "About the studio and classes"),
        ("What does sat chit ananda mean?", "Sat Chit Ananda"),
        ("नींद नहीं आती", "Stress, anxiety and sleep"),
    ],
)
def test_questions_find_the_right_section(assistant, question, section):
    assert assistant.retriever.top(question)[0].title == section


@pytest.mark.parametrize("question", ["I have chest pain during class", "मुझे सीने में दर्द है", "मला छातीत दुखत आहे", "I feel suicidal"])
def test_urgent_questions_skip_the_model(assistant, question):
    answer = assistant.ask(question, "en")
    assert answer.mode == "urgent" and "112" in answer.text


def test_unknown_question_says_so(assistant):
    answer = assistant.ask("qwerty zxcv", "hi")
    assert answer.mode == "notes" and answer.sources == [] and "रमित" in answer.text


# The suggested questions on the Ask screen, exactly as in the app's strings.xml, in all three languages.
SUGGESTIONS = [
    ("I'm a beginner. How do I start?", "Starting as a beginner"),
    ("मैं नया हूँ। शुरुआत कैसे करूँ?", "Starting as a beginner"),
    ("मी नवशिका आहे. सुरुवात कशी करू?", "Starting as a beginner"),
    ("Yoga for back pain?", "Back pain"),
    ("कमर दर्द के लिए योग?", "Back pain"),
    ("पाठदुखीसाठी योग?", "Back pain"),
    ("What should I eat before class?", "Food and water around practice"),
    ("कक्षा से पहले क्या खाएँ?", "Food and water around practice"),
    ("वर्गापूर्वी काय खावे?", "Food and water around practice"),
    ("What does Sat Chit Ananda mean?", "Sat Chit Ananda"),
    ("सत् चित् आनंद का अर्थ क्या है?", "Sat Chit Ananda"),
    ("सत् चित् आनंद म्हणजे काय?", "Sat Chit Ananda"),
]


@pytest.mark.parametrize(("question", "section"), SUGGESTIONS)
def test_suggested_questions_find_their_section(assistant, question, section):
    assert assistant.retriever.top(question)[0].title == section


def test_suggestions_match_the_app():
    root = Path(__file__).resolve().parents[2] / "android" / "app" / "src" / "main" / "res"
    shown = set()
    for folder in ("values", "values-hi", "values-mr"):
        text = (root / folder / "strings.xml").read_text(encoding="utf-8")
        shown |= {line.split(">")[1].split("<")[0].replace("\\'", "'") for line in text.splitlines() if 'name="sugg_' in line}
    assert shown == {q for q, _ in SUGGESTIONS}


def test_marathi_notes_have_every_section():
    assert set(load_translation(NOTES.with_name("yoga_health.mr.md"))) == {s.title for s in load_sections(NOTES)}


@pytest.mark.parametrize(
    "question",
    ["I can’t breathe after pranayama", "i cant breath", "my chest hurts badly", "I feel faint", "मुझे साँस नहीं आ रही",
     "सीने मे दर्द हो रहा है", "मला छातीत कळ येते", "मुझे ख़ुद को नुकसान पहुँचाने का मन करता है"],
)
def test_urgent_signs_however_they_are_written(question):
    assert is_urgent(question)


@pytest.mark.parametrize("question", ["How do I breathe in cat-cow?", "Chest opening poses for posture?", "सांस कैसे लें?", "श्वास कसा घ्यावा?"])
def test_ordinary_breathing_questions_are_not_urgent(question):
    assert not is_urgent(question)


def test_marathi_answers_from_marathi_notes_when_gemma_is_off(assistant):
    answer = assistant.ask("गरोदरपणात योग करू शकते का?", "mr")
    assert answer.sources == ["Pregnancy"] and "पाठीवर" in answer.text and "इंग्रजीत" not in answer.text


def test_too_many_waiting_questions_are_refused():
    import threading

    gate = threading.Event()

    class SlowGemma:
        def reply(self, system, question, ban_foreign_scripts=False):
            gate.wait(5)
            return "ok"

    a = Assistant(NOTES, "Satt Chitt Anand Yoga", "Ramit ji")
    a.gemma = SlowGemma()
    threads = [threading.Thread(target=a.ask, args=("back pain", "en")) for _ in range(4)]
    for th in threads:
        th.start()
    import time
    time.sleep(0.2)
    with pytest.raises(Busy):
        a.ask("back pain", "en")
    gate.set()
    for th in threads:
        th.join()
