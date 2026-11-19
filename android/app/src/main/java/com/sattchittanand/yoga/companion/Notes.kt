package com.sattchittanand.yoga.companion

import java.text.Normalizer
import kotlin.math.ln

/*
 * The studio's notes on the phone, the search over them, and the emergency check. Plain Kotlin, no Android, so the JVM
 * unit tests run it as it is.
 */

val STOPWORDS: Set<String> = (
    ("a am an and are as at be but by can do does for from how i if in is it its me my of on or should so that the this " +
        "to was what when where which who why will with you your yoga").split(" ") +
        // Common Hindi and Marathi function words.
        ("का की के को में से है हैं पर और या क्या कैसे करें कर मैं मुझे मेरा मेरी भी तो यह वह लिए नहीं " +
            "आहे आहेत मला माझा माझी मी ला ने चा ची चे मध्ये साठी आणि किंवा कसे काय करू करा शकते शकतो नाही").split(" ") +
        listOf("योग", "योगा") // as uninformative here as "yoga": otherwise every Hindi or Marathi question finds "Yoga Nidra"
    ).filter { it.isNotEmpty() }.toSet()
const val KEYWORD_WEIGHT = 3 // a word in a section's title or Keywords line counts as much as three in its text

/** Letters, numbers and underscore in any script, plus the Devanagari block, so vowel signs stay inside words. */
private val WORD = Regex("[\\p{L}\\p{N}_\\u0900-\\u097F]+")

/** Lowercase words, keeping Devanagari vowel signs inside words, without the stop words. */
fun tokenize(text: String): List<String> = WORD.findAll(text.lowercase()).map { it.value }.filter { it !in STOPWORDS }.toList()

class Section(val title: String, val text: String, val terms: Map<String, Int>, val keys: Set<String>)

private fun parts(markdown: String): List<Pair<String, String>> =
    Regex("^## ", RegexOption.MULTILINE).split(markdown).drop(1).map { part ->
        val newline = part.indexOf('\n')
        if (newline < 0) part to "" else part.substring(0, newline) to part.substring(newline + 1)
    }

/** The `## ` sections of the notes file. A section's `Keywords:` line is used for matching only, never shown. */
fun loadSections(markdown: String): List<Section> = parts(markdown).map { (title, body) ->
    val lines = body.lines()
    val keywords = lines.filter { it.startsWith("Keywords:") }.joinToString("\n")
    val text = lines.filterNot { it.startsWith("Keywords:") }.joinToString("\n").trim()
    val keys = tokenize("$title $keywords")
    val terms = LinkedHashMap<String, Int>()
    for (word in tokenize(text)) terms[word] = (terms[word] ?: 0) + 1
    repeat(KEYWORD_WEIGHT) { for (word in keys) terms[word] = (terms[word] ?: 0) + 1 }
    Section(title.trim(), text, terms, keys.toSet())
}

/** A translated notes file: {English title: translated text}. Its `## ` headings repeat the English titles. */
fun loadTranslation(markdown: String): Map<String, String> = parts(markdown).associate { (title, body) -> title.trim() to body.trim() }

/** BM25 over the sections: rare words that appear in a section count most. */
class Retriever(val sections: List<Section>, private val k1: Double = 1.5, private val b: Double = 0.75) {
    private val avgLen = sections.sumOf { s -> s.terms.values.sum() }.toDouble() / sections.size
    val idf: Map<String, Double>

    init {
        val docsWith = LinkedHashMap<String, Int>()
        for (s in sections) for (term in s.terms.keys) docsWith[term] = (docsWith[term] ?: 0) + 1
        val n = sections.size
        idf = docsWith.mapValuesTo(LinkedHashMap()) { (_, df) -> ln(1 + (n - df + 0.5) / (df + 0.5)) }
    }

    fun score(section: Section, query: List<String>): Double {
        val length = section.terms.values.sum()
        var total = 0.0
        for (term in query) {
            val tf = section.terms[term] ?: 0
            if (tf > 0) total += idf.getValue(term) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * length / avgLen))
        }
        return total
    }

    /** A word the notes do not contain, mapped to the longest word of the notes it starts with (4+ letters):
     *  गरोदरपणात finds गरोदरपणा, "stretches" finds "stretch". */
    fun expand(word: String): String {
        if (word in idf) return word
        return idf.keys.filter { it.length >= 4 && word.startsWith(it) }.maxByOrNull { it.length } ?: word
    }

    /** The best-matching section when the question names its topic, with a word of its title or Keywords line; null
     *  when the best match rests only on words of its text ("how MANY classes in the LAST month" finds "Stress,
     *  anxiety and sleep" that way). Words starting with one of [ignore] do not count as naming it. */
    fun named(question: String, ignore: List<String> = emptyList()): Section? {
        val query = tokenize(question).map(::expand)
        var best = Double.NEGATIVE_INFINITY
        var index = -1
        sections.forEachIndexed { i, s -> score(s, query).let { if (it >= best) { best = it; index = i } } } // ties: the later section, as in top()
        val section = sections[index]
        val names = if (ignore.isEmpty()) query.toSet() else query.filter { w -> ignore.none { w.startsWith(it) } }.toSet()
        return section.takeIf { best > 0 && section.keys.any { it in names } }
    }

    /** Up to [k] sections, dropping any that score under [keep] times the best: a weak third match is noise. */
    fun top(question: String, k: Int = 3, keep: Double = 0.55): List<Section> {
        val query = tokenize(question).map(::expand)
        val scored = sections.indices.map { score(sections[it], query) to it }
            .sortedWith(compareByDescending<Pair<Double, Int>> { it.first }.thenByDescending { it.second })
        val best = scored.first().first
        return scored.take(k).filter { (score, _) -> score > 0 && score >= keep * best }.map { sections[it.second] }
    }
}

/** The English notes and, for Marathi, a translation made by a person, which the companion copies from: Gemma
 *  translating the English notes itself changed facts. */
class StudioNotes(english: String, marathi: String) {
    val retriever = Retriever(loadSections(english))
    val translations: Map<String, Map<String, String>> = mapOf("mr" to loadTranslation(marathi))

    /** A section's text in [lang] when the notes exist in it, else in English. */
    fun text(section: Section, lang: String): String = translations[lang]?.get(section.title) ?: section.text
}

// ---------- the emergency check: runs first, with no model ----------

/** Emergency signs in the three languages, matched on [normalise]d text. `\s` is spelt out so the JVM and Android
 *  (whose regex engines read `\s` differently) match the same spaces, Unicode ones included. */
private val URGENT = Regex(
    listOf(
        "chest[\\s\\p{Z}]*(pain|hurt|tight|pressure)", "pain in (my |the )?chest", "heart attack",
        "(can ?not|cant|unable to|could ?not|couldnt) breath", "(trouble|difficulty) breathing",
        "faint", "passed out", "unconscious", "stroke", "suicid", "kill(ing)? myself", "self.?harm",
        "end (my|it) (life|all)", "heavy bleeding",
        "(सीने|छाती) (मे|में) (दर्द|दबाव)", "सांस (नही|नहीं)", "बेहोश", "आत्महत्या", "दिल का दौरा",
        "खुद को (मार|नुकसान)",
        "छातीत (दुख|वेदना|कळ)", "श्वास घेता येत (नाही|नाहीये)", "बेशुद्ध", "हृदयविकाराचा झटका", "स्वतःला (इजा|संपव)",
    ).joinToString("|"),
)

val URGENT_REPLY = mapOf(
    "en" to "This could be urgent. Please stop practising and get medical help now: call 112 or go to the nearest " +
        "hospital. If you are thinking of harming yourself, please call Tele-MANAS on 14416 (free, any time).",
    "hi" to "यह गंभीर हो सकता है। कृपया अभ्यास रोकें और तुरंत चिकित्सा सहायता लें: 112 पर कॉल करें या नज़दीकी अस्पताल " +
        "जाएँ। अगर आपके मन में ख़ुद को नुकसान पहुँचाने के विचार हैं, तो टेली-मानस 14416 पर कॉल करें (निःशुल्क, कभी भी)।",
    "mr" to "हे गंभीर असू शकते. कृपया सराव थांबवा आणि लगेच वैद्यकीय मदत घ्या: 112 वर कॉल करा किंवा जवळच्या " +
        "रुग्णालयात जा. स्वतःला इजा करण्याचे विचार येत असल्यास टेली-मानस 14416 वर कॉल करा (मोफत, कधीही).",
)

/** Lowercase, one spelling per sound: apostrophes dropped ("can’t" = "cant"), chandrabindu as anusvara
 *  (साँस = सांस), nukta dropped (ख़ुद = खुद). */
fun normalise(text: String): String =
    Normalizer.normalize(text, Normalizer.Form.NFC).lowercase().replace(Regex("['’‘`]"), "")
        .replace('ँ', 'ं').replace("़", "")

fun isUrgent(question: String): Boolean = URGENT.containsMatchIn(normalise(question))
