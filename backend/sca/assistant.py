"""The practice assistant: finds the relevant sections of the studio's notes and has Gemma answer from them.

Three paths, checked in order:
1. Urgent: a question that names an emergency sign gets a fixed reply sending the person to 112. No model.
2. Gemma: the top sections of `knowledge/yoga_health.md` go into the system prompt and Gemma 4 answers. For Marathi,
   the sections come from the person-made translation `knowledge/yoga_health.mr.md` when it has all of them.
3. Notes: when Gemma is not loaded, the best-matching section is returned as it is.
"""

import itertools
import math
import re
import threading
import time
import unicodedata
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
    + ["योग", "योगा"]  # as uninformative here as "yoga"; it pulled up "Yoga Nidra" for every Hindi or Marathi question
)
KEYWORD_WEIGHT = 3  # a word in a section's title or Keywords line counts as much as three in its text

# Emergency signs in the three languages, matched on normalised text (see `normalise`).
URGENT = re.compile(
    "|".join(
        [
            r"chest\s*(pain|hurt|tight|pressure)", r"pain in (my |the )?chest", r"heart attack",
            r"(can ?not|cant|unable to|could ?not|couldnt) breath", r"(trouble|difficulty) breathing",
            r"faint", r"passed out", r"unconscious", r"stroke", r"suicid", r"kill(ing)? myself", r"self.?harm",
            r"end (my|it) (life|all)", r"heavy bleeding",
            r"(सीने|छाती) (मे|में) (दर्द|दबाव)", r"सांस (नही|नहीं)", r"बेहोश", r"आत्महत्या", r"दिल का दौरा",
            r"खुद को (मार|नुकसान)",
            r"छातीत (दुख|वेदना|कळ)", r"श्वास घेता येत (नाही|नाहीये)", r"बेशुद्ध", r"हृदयविकाराचा झटका", r"स्वतःला (इजा|संपव)",
        ]
    )
)
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
NOTES_LEAD_OWN = {  # the same, when the notes exist in the person's language
    "hi": "सहायक अभी उपलब्ध नहीं है। स्टूडियो के नोट्स में यह लिखा है:",
    "mr": "सहायक सध्या उपलब्ध नाही. स्टुडिओच्या नोंदींमध्ये हे लिहिले आहे:",
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
# Added after the notes when they are already in the student's language. Gemma 4 E4B translating the English notes into
# Marathi itself changed facts ("lie on the back" became "on the belly") and garbled words; copying a translation made
# by a person does not (docs/evals/assistant_v0.4.md).
TRANSLATED_RULE = """

6. The notes above are already in {language}. Answer with their own words and sentences: copy the points that answer the
   question, and always copy the point about the doctor or about stopping when the notes have one. Do not translate
   them again and do not change any word."""
TRANSLATED_LANGS = ("mr",)  # languages with a `<notes>.<lang>.md` translation next to the English notes
CHAT_NGRAM_WINDOW = 16  # tokens the companion's repeat ban looks back over (see Gemma.chat)


class Busy(Exception):
    """Too many questions are already waiting for Gemma; the caller should try again shortly."""


@dataclass(frozen=True)
class Section:
    title: str
    text: str
    terms: Counter
    keys: frozenset[str] = frozenset()  # the words of its title and Keywords line


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
        keys = tokenize(f"{title} {keywords}")
        terms = Counter(tokenize(text))
        for _ in range(KEYWORD_WEIGHT):
            terms.update(keys)
        sections.append(Section(title.strip(), text, terms, frozenset(keys)))
    return sections


def load_translation(path: Path) -> dict[str, str]:
    """A translated notes file: its `## ` headings repeat the English titles, its text is in the other language.
    Returns {English title: translated text}; empty when the file does not exist."""
    if not path.is_file():
        return {}
    parts = re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.MULTILINE)[1:]
    return {title.strip(): body.strip() for title, _, body in (part.partition("\n") for part in parts)}


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

    def named(self, question: str, ignore: tuple[str, ...] = ()) -> Section | None:
        """The best-matching section when the question names its topic, with a word of its title or Keywords line;
        None when the best match rests only on words of its text ("how MANY classes in the LAST month" finds
        "Stress, anxiety and sleep" that way). Words starting with one of `ignore` do not count as naming it."""
        query = [self.expand(w) for w in tokenize(question)]
        score, index = max((self.score(s, query), i) for i, s in enumerate(self.sections))
        section = self.sections[index]
        names = {w for w in query if not w.startswith(ignore)} if ignore else set(query)
        return section if score > 0 and section.keys & names else None

    def top(self, question: str, k: int = 3, keep: float = 0.55) -> list[Section]:
        """Up to `k` sections, dropping any that score under `keep` times the best: a weak third match is noise
        in the prompt and misleading in the list of sources shown to the student."""
        query = [self.expand(w) for w in tokenize(question)]
        scored = sorted(((self.score(s, query), i) for i, s in enumerate(self.sections)), reverse=True)
        best = scored[0][0]
        return [self.sections[i] for score, i in scored[:k] if score > 0 and score >= keep * best]


def normalise(text: str) -> str:
    """Lowercase, one spelling per sound: curly and straight apostrophes dropped ("can’t" = "cant"), chandrabindu
    as anusvara (साँस = सांस), nukta dropped (ख़ुद = खुद)."""
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"['’‘`]", "", text)
    return text.replace("\u0901", "\u0902").replace("\u093c", "")


def is_urgent(question: str) -> bool:
    return URGENT.search(normalise(question)) is not None


def is_foreign(text: str) -> bool:
    """Whether `text` holds a letter or a digit from a script other than Latin and Devanagari: 0-9 and ०-९ are
    fine, Bengali ০-৯ or Arabic ٠-٩ are not. Punctuation, symbols and marks never count."""
    return any((ch.isalpha() or ch.isdecimal())
               and not ("0" <= ch <= "9" or unicodedata.name(ch, "").startswith(("LATIN", "DEVANAGARI")))
               for ch in text)


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
        self._engine = litert_lm.Engine(str(model_path), backend=make_backend(), max_num_tokens=8192, cache_dir=str(cache_dir))  # room for tools and chat history
        self._lock = threading.Lock()
        self._foreign: list[int] | None = None
        self.name = f"{model_path.stem} ({backend})"

    def foreign_tokens(self) -> list[int]:
        """Tokens holding a letter or digit that is neither Latin nor Devanagari (see `is_foreign`; about 80,000 of
        262,144, listed once, < 1 s). Marathi answers otherwise slip in a Japanese, Korean or Arabic word now and then
        (ともに, 전에, يكا), or Bengali digits in a time (8:০০, docs/iterations/v0.5.md)."""
        if self._foreign is None:
            ids = []
            for i in itertools.count():
                try:
                    text = self._engine.detokenize([i])
                except RuntimeError:  # past the end of the vocabulary
                    break
                if is_foreign(text):
                    ids.append(i)
            self._foreign = ids
        return self._foreign

    def reply(self, system: str, question: str, max_output_tokens: int = 320, ban_foreign_scripts: bool = False) -> str:
        with self._lock:
            conversation = self._engine.create_conversation(
                max_output_tokens=max_output_tokens,
                sampler_config=self._lm.SamplerConfig(top_k=1),
                system_message=system,
            )
            try:
                # Without this, Marathi answers could loop on one word (docs/evals/assistant_v0.2.md, mr-sleep).
                options = {"no_repeat_ngram_config": self._lm.NoRepeatNgramConfig(no_repeat_ngram_size=8)}
                if ban_foreign_scripts:
                    options["suppress_tokens_config"] = self._lm.SuppressTokensConfig(suppress_tokens=self.foreign_tokens())
                answer = conversation.send_message(question, **options).to_json()
            finally:
                conversation.close()
        return "".join(p.get("text", "") for p in answer.get("content", []) if isinstance(p, dict)).strip()

    def chat(self, system: str, preface: list[dict], message: str, tools: list, max_output_tokens: int = 400,
             ban_foreign_scripts: bool = False) -> str:
        """One reply in a conversation that starts with `preface` (earlier messages) and may call `tools`, Python
        functions the runtime runs for Gemma until it has its answer."""
        with self._lock:
            conversation = self._engine.create_conversation(
                messages=preface or None,
                tools=[self._lm.tool_from_function(f) for f in tools],
                automatic_tool_calling=True,
                max_output_tokens=max_output_tokens,
                sampler_config=self._lm.SamplerConfig(top_k=1),
                system_message=system,
            )
            try:
                # The 8-token ban only looks back CHAT_NGRAM_WINDOW tokens: a word loop is still stopped, but a list may
                # repeat "नोव्हेंबर रोजी सकाळी ८:००" on each line. Banned over the whole reply, the second "००" was
                # forbidden, and Gemma wrote a look-alike instead (८:০০ in Bengali digits, or ८:०७).
                options = {"no_repeat_ngram_config": self._lm.NoRepeatNgramConfig(no_repeat_ngram_size=8,
                                                                                   window_size=CHAT_NGRAM_WINDOW)}
                if ban_foreign_scripts:
                    options["suppress_tokens_config"] = self._lm.SuppressTokensConfig(suppress_tokens=self.foreign_tokens())
                answer = conversation.send_message(message, **options).to_json()
            finally:
                conversation.close()
        return "".join(p.get("text", "") for p in answer.get("content", []) if isinstance(p, dict)).strip()


class Assistant:
    def __init__(self, notes_path: Path, studio_name: str, teacher: str) -> None:
        self.retriever = Retriever(load_sections(notes_path))
        self.translations = {lang: load_translation(notes_path.with_name(f"{notes_path.stem}.{lang}.md")) for lang in TRANSLATED_LANGS}
        self.studio_name = studio_name
        self.teacher = teacher
        self.gemma: Gemma | None = None
        self.status = "off"  # off, loading, ready, failed
        # Questions allowed to wait for Gemma at once; beyond that, ask() raises Busy instead of tying up a server
        # thread for minutes (each waiting request holds one of the server's 40 worker threads).
        self.slots = threading.BoundedSemaphore(4)

    def load_gemma(self, model_path: Path, backend: str, cache_dir: Path) -> None:
        """Loads the model; meant to run on a background thread so the server answers meanwhile."""
        self.status = "loading"
        try:
            self.gemma = Gemma(model_path, backend, cache_dir)
            self.gemma.foreign_tokens()  # listed now, so the first Marathi question does not wait for it
            self.status = "ready"
        except Exception as error:  # noqa: BLE001 - any load failure leaves the notes-only path working
            self.status = f"failed: {error}"

    def ask(self, question: str, lang: str) -> Answer:
        start = time.perf_counter()
        if is_urgent(question):
            return Answer(URGENT_REPLY[lang], ["When to stop and get help"], "urgent", time.perf_counter() - start)
        sections = self.retriever.top(question)
        sources = [s.title for s in sections]
        translation = self.translations.get(lang, {})
        if self.gemma is None:
            if not sections:
                return Answer(NO_MATCH[lang], [], "notes", time.perf_counter() - start)
            best = sections[0]
            text = translation.get(best.title) or best.text
            lead = NOTES_LEAD["en"] if lang == "en" else (NOTES_LEAD_OWN[lang] if best.title in translation else NOTES_LEAD[lang])
            return Answer(f"{lead}\n\n{text}", sources[:1], "notes", time.perf_counter() - start)
        translated = bool(sections) and all(s.title in translation for s in sections)
        notes = "\n\n".join(f"### {s.title}\n{translation[s.title] if translated else s.text}" for s in sections)
        system = SYSTEM.format(
            studio=self.studio_name, teacher=self.teacher, language=LANGUAGE_NAMES[lang], notes=notes or "(no notes match this question)"
        )
        if translated:
            system += TRANSLATED_RULE.format(language=LANGUAGE_NAMES[lang])
        if not self.slots.acquire(blocking=False):
            raise Busy
        try:
            text = self.gemma.reply(system, question, ban_foreign_scripts=lang in TRANSLATED_LANGS)
        finally:
            self.slots.release()
        return Answer(text, sources, "gemma", time.perf_counter() - start)
