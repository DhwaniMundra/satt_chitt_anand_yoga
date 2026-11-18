"""The practice assistant: finds the relevant sections of the studio's notes and has Gemma answer from them.

Three paths, checked in order:
1. Urgent: a question that names an emergency sign gets a fixed reply sending the person to 112. No model.
2. Gemma: the top sections of `knowledge/yoga_health.md` go into the system prompt and Gemma 4 answers.
3. Notes: when Gemma is not loaded, the best-matching section is returned as it is.
"""

import math
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

LANGUAGE_NAMES = {"en": "English", "hi": "Hindi (हिन्दी, Devanagari script)", "mr": "Marathi (मराठी, Devanagari script)"}
STOPWORDS = set(
    "a am an and are as at be but by can do does for from how i if in is it its me my of on or should so that the this "
    "to was what when where which who why will with you your yoga".split()
    # Common Hindi and Marathi function words.
    + "का की के को में से है हैं पर और या क्या कैसे करें कर मैं मुझे मेरा मेरी भी तो यह वह लिए नहीं "
    "आहे आहेत मला माझा माझी मी ला ने चा ची चे मध्ये साठी आणि किंवा कसे काय करू करा शकते शकतो नाही".split()
)
KEYWORD_WEIGHT = 3  # a word in a section's title or Keywords line counts as much as three in its text

# Emergency signs in the three languages. Matching is on lowercase text, by substring.
URGENT = [
    "chest pain", "pain in my chest", "chest pressure", "heart attack", "can't breathe", "cannot breathe",
    "unable to breathe", "fainted", "fainting", "passed out", "unconscious", "stroke", "suicid", "kill myself",
    "self harm", "self-harm", "end my life", "heavy bleeding",
    "सीने में दर्द", "छाती में दर्द", "सांस नहीं", "बेहोश", "आत्महत्या", "दिल का दौरा",
    "छातीत दुख", "छातीत वेदना", "श्वास घेता येत नाही", "बेशुद्ध", "हृदयविकाराचा झटका",
]
URGENT_REPLY = {
    "en": "This could be urgent. Please stop practising and get medical help now: call 112 or go to the nearest "
    "hospital. If you are thinking of harming yourself, please call Tele-MANAS on 14416 (free, any time).",
    "hi": "यह गंभीर हो सकता है। कृपया अभ्यास रोकें और तुरंत चिकित्सा सहायता लें: 112 पर कॉल करें या नज़दीकी अस्पताल "
    "जाएँ। अगर आपके मन में ख़ुद को नुकसान पहुँचाने के विचार हैं, तो टेली-मानस 14416 पर कॉल करें (निःशुल्क, कभी भी)।",
    "mr": "हे गंभीर असू शकते. कृपया सराव थांबवा आणि लगेच वैद्यकीय मदत घ्या: 112 वर कॉल करा किंवा जवळच्या "
    "रुग्णालयात जा. स्वतःला इजा करण्याचे विचार येत असल्यास टेली-मानस 14416 वर कॉल करा (मोफत, कधीही).",
}
NOTES_LEAD = {
    "en": "The assistant is resting right now. Here is what the studio's notes say:",
    "hi": "सहायक अभी उपलब्ध नहीं है। स्टूडियो के नोट्स में यह लिखा है (अंग्रेज़ी में):",
    "mr": "सहायक सध्या उपलब्ध नाही. स्टुडिओच्या नोंदींमध्ये हे लिहिले आहे (इंग्रजीत):",
}
NO_MATCH = {
    "en": "I don't have notes on that. Please ask Ramit ji in class or in the WhatsApp group.",
    "hi": "इस बारे में मेरे पास जानकारी नहीं है। कृपया कक्षा में या व्हाट्सऐप ग्रुप में रमित जी से पूछें।",
    "mr": "याबद्दल माझ्याकडे माहिती नाही. कृपया वर्गात किंवा व्हॉट्सॲप ग्रुपमध्ये रमित जींना विचारा.",
}
SYSTEM = """You are the practice assistant of {studio}, an online yoga studio in India. Students ask you about yoga
practice and everyday health habits. The teacher is {teacher} (written रमित जी in Hindi and Marathi).

Answer using only the studio notes below. Rules:
1. You are not a doctor. Never diagnose, never promise a cure, never tell anyone to start, change or stop a medicine.
2. If the question involves pain, illness, pregnancy, surgery or medicine, give only the gentle general guidance in the
   notes, then say to check with their doctor and to tell {teacher} before class.
3. If the notes do not cover the question, say so in one sentence and suggest asking {teacher} in class.
4. Keep it short and warm: at most 120 words, simple words, short bullet points when listing steps.
5. Reply only in {language}. When that is not English, translate the relevant points of the notes closely and simply.
   Never change their meaning and never add advice that is not in the notes.

Studio notes:
{notes}"""


class Busy(Exception):
    """Too many questions are already waiting for Gemma; the caller should try again shortly."""


@dataclass(frozen=True)
class Section:
    title: str
    text: str
    terms: Counter


@dataclass(frozen=True)
class Answer:
    text: str
    sources: list[str]
    mode: str  # "gemma", "notes" or "urgent"
    latency_s: float


def tokenize(text: str) -> list[str]:
    """Lowercase words, keeping Devanagari vowel signs inside words (Python's \\w alone splits at them)."""
    return [w for w in re.findall(r"[\wऀ-ॿ]+", text.lower()) if w not in STOPWORDS]


def load_sections(path: Path) -> list[Section]:
    """The `## ` sections of the notes file; the text before the first heading is the file's own preamble.
    A section's `Keywords:` line is used for matching only, and is not shown to Gemma or the student."""
    parts = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]
    sections = []
    for part in parts:
        title, _, body = part.partition("\n")
        keywords = "\n".join(line for line in body.splitlines() if line.startswith("Keywords:"))
        text = "\n".join(line for line in body.splitlines() if not line.startswith("Keywords:")).strip()
        terms = Counter(tokenize(text))
        for _ in range(KEYWORD_WEIGHT):
            terms.update(tokenize(f"{title} {keywords}"))
        sections.append(Section(title.strip(), text, terms))
    return sections


class Retriever:
    """BM25 over the sections: rare words that appear in a section count most."""

    def __init__(self, sections: list[Section], k1: float = 1.5, b: float = 0.75) -> None:
        self.sections = sections
        self.k1, self.b = k1, b
        self.avg_len = sum(sum(s.terms.values()) for s in sections) / len(sections)
        docs_with = Counter(term for s in sections for term in s.terms)
        n = len(sections)
        self.idf = {t: math.log(1 + (n - df + 0.5) / (df + 0.5)) for t, df in docs_with.items()}

    def score(self, section: Section, query: list[str]) -> float:
        length = sum(section.terms.values())
        total = 0.0
        for term in query:
            tf = section.terms.get(term, 0)
            if tf:
                total += self.idf[term] * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * length / self.avg_len))
        return total

    def expand(self, word: str) -> str:
        """A word the notes do not contain, mapped to the longest word of the notes it starts with (4+ letters).
        This catches inflected forms: गरोदरपणात finds गरोदरपणा, "stretches" finds "stretch"."""
        if word in self.idf:
            return word
        stems = [t for t in self.idf if len(t) >= 4 and word.startswith(t)]
        return max(stems, key=len) if stems else word

    def top(self, question: str, k: int = 3, keep: float = 0.55) -> list[Section]:
        """Up to `k` sections, dropping any that score under `keep` times the best: a weak third match is noise
        in the prompt and misleading in the list of sources shown to the student."""
        query = [self.expand(w) for w in tokenize(question)]
        scored = sorted(((self.score(s, query), i) for i, s in enumerate(self.sections)), reverse=True)
        best = scored[0][0]
        return [self.sections[i] for score, i in scored[:k] if score > 0 and score >= keep * best]


def is_urgent(question: str) -> bool:
    lowered = question.lower()
    return any(sign in lowered for sign in URGENT)


class Gemma:
    """Gemma 4 through LiteRT-LM, the runtime that also runs the same `.litertlm` file on a phone.

    One engine, shared by all requests; requests take turns because the engine is not thread-safe.
    """

    def __init__(self, model_path: Path, backend: str, cache_dir: Path) -> None:
        import litert_lm  # imported here so the server and tests run without the runtime when Gemma is off

        if not model_path.is_file():
            raise FileNotFoundError(f"Gemma model file not found: {model_path}")
        cache_dir.mkdir(parents=True, exist_ok=True)
        self._lm = litert_lm
        make_backend = litert_lm.Backend.GPU if backend == "gpu" else litert_lm.Backend.CPU
        self._engine = litert_lm.Engine(str(model_path), backend=make_backend(), max_num_tokens=4096, cache_dir=str(cache_dir))
        self._lock = threading.Lock()
        self.name = f"{model_path.stem} ({backend})"

    def reply(self, system: str, question: str, max_output_tokens: int = 320) -> str:
        with self._lock:
            conversation = self._engine.create_conversation(
                max_output_tokens=max_output_tokens,
                sampler_config=self._lm.SamplerConfig(top_k=1),
                system_message=system,
            )
            try:
                # Without this, Marathi answers could loop on one word (docs/evals/assistant_v0.2.md, mr-sleep).
                no_repeat = self._lm.NoRepeatNgramConfig(no_repeat_ngram_size=8)
                answer = conversation.send_message(question, no_repeat_ngram_config=no_repeat).to_json()
            finally:
                conversation.close()
        return "".join(p.get("text", "") for p in answer.get("content", []) if isinstance(p, dict)).strip()


class Assistant:
    def __init__(self, notes_path: Path, studio_name: str, teacher: str) -> None:
        self.retriever = Retriever(load_sections(notes_path))
        self.studio_name = studio_name
        self.teacher = teacher
        self.gemma: Gemma | None = None
        self.status = "off"  # off, loading, ready, failed

    def load_gemma(self, model_path: Path, backend: str, cache_dir: Path) -> None:
        """Loads the model; meant to run on a background thread so the server answers meanwhile."""
        self.status = "loading"
        try:
            self.gemma = Gemma(model_path, backend, cache_dir)
            self.status = "ready"
        except Exception as error:  # noqa: BLE001 - any load failure leaves the notes-only path working
            self.status = f"failed: {error}"

    def ask(self, question: str, lang: str) -> Answer:
        start = time.perf_counter()
        if is_urgent(question):
            return Answer(URGENT_REPLY[lang], ["When to stop and get help"], "urgent", time.perf_counter() - start)
        sections = self.retriever.top(question)
        sources = [s.title for s in sections]
        if self.gemma is None:
            text = f"{NOTES_LEAD[lang]}\n\n{sections[0].text}" if sections else NO_MATCH[lang]
            return Answer(text, sources[:1], "notes", time.perf_counter() - start)
        notes = "\n\n".join(f"### {s.title}\n{s.text}" for s in sections) or "(no notes match this question)"
        system = SYSTEM.format(studio=self.studio_name, teacher=self.teacher, language=LANGUAGE_NAMES[lang], notes=notes)
        text = self.gemma.reply(system, question)
        return Answer(text, sources, "gemma", time.perf_counter() - start)
