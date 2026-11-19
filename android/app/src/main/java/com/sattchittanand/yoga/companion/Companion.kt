package com.sattchittanand.yoga.companion

import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/*
 * The practice companion on the phone: a port of backend/sca/companion.py. What the evaluations proved stays as it was
 * (docs/iterations/v0.5.md): tools return summaries worked out in code; the notes section a message names and, for a
 * message about classes, the coming classes are handed to Gemma up front; "Remember that…" is saved by code if Gemma
 * does not; the emergency check runs first, with no model. Plain Kotlin (the tools use LiteRT-LM's annotations only),
 * so the JVM unit tests run it with a stand-in for the server.
 */

const val HISTORY_TURNS = 6 // earlier messages replayed as context; lasting facts belong in saved notes

/** Words that make a message about the class schedule, in English, Hindi and Marathi: such messages get the coming
 *  classes up front (both models asked for clarification instead of checking the schedule in Marathi). */
val SCHEDULE_WORDS = listOf("class", "tomorrow", "today", "next", "schedule", "कक्षा", "क्लास", "कल ", "आज", "अगल", "कब",
    "वर्ग", "उद्या", "पुढ", "कधी")

/** The words the app teaches for saving a note (Me, "What I remember": say "Remember that…"), at the start of a message.
 *  `\s` spelt out as in [isUrgent]. */
private const val S = "[\\s\\p{Z}]"
private val REMEMBER = Regex(
    "^(?:$S*(?:please$S+)?remember${S}+that$S+|$S*(?:कृपया$S+)?याद${S}+रख(?:ना|ें|िए|ो)$S+कि$S+|$S*(?:कृपया$S+)?लक्षात${S}+ठेवा$S+की$S+)",
    RegexOption.IGNORE_CASE,
)

/** What the app shows under a reply that used a tool. */
val TOOL_LABELS = mapOf(
    "get_my_practice" to "practice",
    "get_upcoming_classes" to "schedule",
    "search_studio_notes" to "notes",
    "save_my_note" to "saved",
    "get_my_notes" to "memory",
)

val LANGUAGE_NAMES = mapOf("en" to "English", "hi" to "Hindi (हिन्दी, Devanagari script)", "mr" to "Marathi (मराठी, Devanagari script)")

const val SYSTEM = """You are the practice companion in the {studio} app, talking with one student, {name}. You can look up their
own practice, the studio's coming classes and the studio's notes, and save notes they ask you to remember.

Rules:
1. For anything about this student's practice, classes or moods, call a tool first and use only what it returns. Never
   invent numbers or dates. Report summaries exactly as the tool gives them.
2. For yoga or health guidance, call search_studio_notes and answer only from what it returns.
3. When the student asks you to remember something, call save_my_note. When they ask what they told you, call
   get_my_notes.
4. You are not a doctor: never diagnose, never promise a cure, never tell anyone to start, change or stop a medicine.
   For pain, illness, pregnancy or medicine, give only gentle general guidance and say to ask their doctor and to tell
   {teacher} before class.
5. Keep replies short and warm: at most 90 words.
6. Reply only in {language}."""

/** One reply: its text, the tools it used (in order) and how it was made: "companion" (Gemma on the phone), "notes"
 *  (the studio's notes, no model) or "urgent" (the fixed emergency reply). */
data class Reply(val text: String, val tools: List<String>, val mode: String)

/** The tools' labels, each once, in the order first used. */
fun labels(tools: List<String>): List<String> = tools.distinct().map { TOOL_LABELS[it] ?: it }

// ---------- what the tools read ----------

/** A coming class, from the server's /home (names, level and description already in the student's language). */
data class UpcomingClass(val startsAt: Instant, val name: String, val level: String, val about: String)

/** A note the companion keeps on this phone. */
data class KeptNote(val text: String, val savedAt: Instant)

/** What the tools read and write. The practice summary and the classes come from the server, the notes from the phone. */
interface StudentData {
    /** The server's practice summary (GET /me/practice), as maps and lists. Throws when the server cannot be reached. */
    fun practice(days: Int, lang: String): Map<String, Any?>

    /** The coming classes, soonest first (GET /home). Throws when the server cannot be reached. */
    fun upcoming(lang: String): List<UpcomingClass>

    fun saveNote(text: String)
    fun notes(): List<KeptNote>
}

private val IST: ZoneId = ZoneId.of("Asia/Kolkata")
private val DATE = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)
private val TIME = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)

/** The next classes, each with an unambiguous day: "tomorrow, Friday 20 November" (as upcoming_classes on the server). */
fun schedule(classes: List<UpcomingClass>, now: Instant, limit: Int = 5): Map<String, Any?> {
    val today = now.atZone(IST).toLocalDate()
    return linkedMapOf(
        "today_is" to DATE.format(today),
        "classes" to classes.take(limit).map { c ->
            val start = c.startsAt.atZone(IST)
            val date = DATE.format(start)
            val day = when (ChronoUnit.DAYS.between(today, start.toLocalDate())) {
                0L -> "today, $date"
                1L -> "tomorrow, $date"
                else -> date
            }
            linkedMapOf("day" to day, "time" to TIME.format(start) + " India time", "class" to c.name, "level" to c.level, "about" to c.about)
        },
    )
}

private const val UNREACHABLE = "The studio server could not be reached just now, so this is not available."

/**
 * The companion's five tools, bound to the student on this phone, each in its own [ToolSet] so Gemma sees them in
 * the server's order. Each records its name in [used].
 */
class Tools(private val data: StudentData, private val notes: StudioNotes, private val lang: String, private val now: () -> Instant = Instant::now) {
    val used = mutableListOf<String>()

    fun getMyPractice(days: Int): Map<String, Any?> {
        used += "get_my_practice"
        return try {
            data.practice(days.coerceIn(1, 90), lang)
        } catch (e: Exception) {
            mapOf("error" to UNREACHABLE)
        }
    }

    fun getUpcomingClasses(): Map<String, Any?> {
        used += "get_upcoming_classes"
        return try {
            schedule(data.upcoming(lang), now())
        } catch (e: Exception) {
            mapOf("error" to UNREACHABLE)
        }
    }

    fun searchStudioNotes(query: String): Map<String, Any?> {
        used += "search_studio_notes"
        return mapOf("notes" to notes.retriever.top(query).map { mapOf("title" to it.title, "text" to notes.text(it, lang)) })
    }

    fun saveMyNote(note: String): Map<String, Any?> {
        used += "save_my_note"
        data.saveNote(note)
        return mapOf("saved" to true)
    }

    fun getMyNotes(): Map<String, Any?> {
        used += "get_my_notes"
        return mapOf("notes" to data.notes().map { mapOf("note" to it.text, "saved" to it.savedAt.toString().take(10)) })
    }

    /** The tools as LiteRT-LM reads them: names, descriptions and parameters as the server's Python functions give them. */
    fun toolSets(): List<ToolSet> = listOf(Practice(this), Schedule(this), Search(this), Save(this), Recall(this))

    @Suppress("FunctionName")
    private class Practice(private val t: Tools) : ToolSet {
        @Tool(description = "This student's classes over the last `days` days, with how they felt before and after (summaries included).")
        fun get_my_practice(@ToolParam(description = "how many days back to look, for example 7 for this week or 30 for this month.") days: Int) =
            t.getMyPractice(days)
    }

    @Suppress("FunctionName")
    private class Schedule(private val t: Tools) : ToolSet {
        @Tool(description = "The studio's classes in the coming week, soonest first: when, time, class, level.")
        fun get_upcoming_classes() = t.getUpcomingClasses()
    }

    @Suppress("FunctionName")
    private class Search(private val t: Tools) : ToolSet {
        @Tool(description = "The studio's notes on yoga practice and everyday health that best match a question.")
        fun search_studio_notes(@ToolParam(description = "what to look up, in a few words, for example \"back pain\" or \"food before class\".") query: String) =
            t.searchStudioNotes(query)
    }

    @Suppress("FunctionName")
    private class Save(private val t: Tools) : ToolSet {
        @Tool(description = "Saves something this student asks you to remember about their practice, such as a sore knee.")
        fun save_my_note(@ToolParam(description = "the note, in the student's own words.") note: String) = t.saveMyNote(note)
    }

    @Suppress("FunctionName")
    private class Recall(private val t: Tools) : ToolSet {
        @Tool(description = "The notes this student has asked you to remember, oldest first.")
        fun get_my_notes() = t.getMyNotes()
    }
}

// ---------- the conversation handed to Gemma ----------

/** The system message, with the coming classes and the matching notes handed over up front, as Companion.prompt()
 *  builds it on the server. [history] holds the earlier messages, oldest first, as (from the student?, text). */
class PracticeCompanion(val notes: StudioNotes, private val studioName: String, private val teacher: String) {

    fun system(firstName: String, message: String, lang: String, tools: Tools): String {
        val base = SYSTEM.replace("{studio}", studioName).replace("{name}", firstName).replace("{teacher}", teacher)
            .replace("{language}", LANGUAGE_NAMES.getValue(lang))
        val schedule = preloadedSchedule(message, tools)
        return base + schedule + preloadedNotes(message, lang, tools.used, schedule = schedule.isNotEmpty())
    }

    fun preface(history: List<Pair<Boolean, String>>): List<Pair<Boolean, String>> = history.takeLast(HISTORY_TURNS)

    /** The coming classes as text for the system message when [message] is about the schedule (or ""). Recorded as a
     *  use of get_upcoming_classes, since the student sees it the same way. */
    fun preloadedSchedule(message: String, tools: Tools): String {
        val lowered = "${message.lowercase()} "
        if (SCHEDULE_WORDS.none { it in lowered }) return ""
        val schedule = tools.getUpcomingClasses()

        @Suppress("UNCHECKED_CAST")
        val classes = schedule["classes"] as? List<Map<String, Any?>> ?: return "".also { tools.used.removeAt(tools.used.lastIndex) }
        val lines = classes.joinToString("\n") { c -> "- ${c["day"]}: ${c["class"]} at ${c["time"]} (${c["level"]})" }
        return "\n\nToday is ${schedule["today_is"]}. The studio's coming classes. Answer from them:\n$lines"
    }

    /** The notes section on the topic [message] names, as text for the system message (or ""): Gemma 4 E2B often
     *  answered health questions without searching. With the [schedule] already handed over, a class word does not name
     *  a topic: told to answer from "About the studio and classes", E2B answered "which class tomorrow?" with today's. */
    fun preloadedNotes(message: String, lang: String, used: MutableList<String>, schedule: Boolean = false): String {
        val ignore = if (schedule) SCHEDULE_WORDS.map { it.trim() } else emptyList()
        val section = notes.retriever.named(message, ignore) ?: return ""
        used += "search_studio_notes"
        return "\n\nThe studio's notes on what the student asks about. Answer from them:\n### ${section.title}\n${notes.text(section, lang)}"
    }

    /** The answer without Gemma, from the notes on the phone (the old notes-only path), saying why. */
    fun notesOnly(message: String, lang: String, reason: NotesReason, save: (String) -> Unit): Reply {
        if (isUrgent(message)) return Reply(URGENT_REPLY.getValue(lang), emptyList(), "urgent")
        noteToSave(message, emptyList())?.let { note ->
            save(note)
            return Reply(SAVED.getValue(lang).format(note), listOf("save_my_note"), "notes")
        }
        val sections = notes.retriever.top(message)
        if (sections.isEmpty()) return Reply(NO_MATCH.getValue(lang), emptyList(), "notes")
        val best = sections.first()
        val own = notes.translations[lang]?.get(best.title)
        val tail = if (lang == "en") NOTES_TAIL.getValue("en") else if (own != null) NOTES_TAIL_OWN.getValue(lang) else NOTES_TAIL.getValue(lang)
        return Reply("${reason.text.getValue(lang)} $tail\n\n${own ?: best.text}", listOf("search_studio_notes"), "notes")
    }
}

/**
 * The note to save when [message] starts with the words the app teaches ("Remember that…") and Gemma did not call
 * save_my_note: in a conversation that began with another question, E4B replied "I have saved that" without saving
 * (docs/iterations/v0.5.md). Null when there is nothing to save.
 */
fun noteToSave(message: String, used: List<String>): String? {
    val match = REMEMBER.find(message) ?: return null
    val note = message.substring(match.range.last + 1).trim().take(500)
    if (note.isEmpty() || "save_my_note" in used) return null
    return note.substring(0, 1).uppercase() + note.substring(1) // "My left knee…", as it reads in "What I remember"
}

/** Why the phone answered from the notes alone. */
enum class NotesReason(val text: Map<String, String>) {
    NOT_DOWNLOADED(mapOf("en" to "Gemma is not on this phone yet.", "hi" to "Gemma अभी इस फ़ोन पर नहीं है।", "mr" to "Gemma अजून या फोनवर नाही.")),
    TOO_LITTLE_MEMORY(mapOf("en" to "This phone has too little memory for Gemma.", "hi" to "इस फ़ोन में Gemma के लिए पर्याप्त मेमोरी नहीं है।",
        "mr" to "या फोनमध्ये Gemma साठी पुरेशी मेमरी नाही.")),
    NOT_STARTED(mapOf("en" to "Gemma could not answer on this phone just now.", "hi" to "Gemma अभी इस फ़ोन पर जवाब नहीं दे पाया।",
        "mr" to "Gemma ला आत्ता या फोनवर उत्तर देता आले नाही.")),
}

private val NOTES_TAIL = mapOf(
    "en" to "Here is what the studio's notes say:",
    "hi" to "स्टूडियो के नोट्स में यह लिखा है (अंग्रेज़ी में):",
    "mr" to "स्टुडिओच्या नोंदींमध्ये हे लिहिले आहे (इंग्रजीत):",
)
private val NOTES_TAIL_OWN = mapOf( // when the notes exist in the student's language
    "hi" to "स्टूडियो के नोट्स में यह लिखा है:",
    "mr" to "स्टुडिओच्या नोंदींमध्ये हे लिहिले आहे:",
)
private val NO_MATCH = mapOf(
    "en" to "I don't have notes on that. Please ask Ramit ji in class or in the WhatsApp group.",
    "hi" to "इस बारे में मेरे पास जानकारी नहीं है। कृपया कक्षा में या व्हाट्सऐप ग्रुप में रमित जी से पूछें।",
    "mr" to "याबद्दल माझ्याकडे माहिती नाही. कृपया वर्गात किंवा व्हॉट्सॲप ग्रुपमध्ये रमित जींना विचारा.",
)
private val SAVED = mapOf(
    "en" to "I have saved that: “%s”",
    "hi" to "मैंने यह सेव कर लिया है: “%s”",
    "mr" to "मी हे सेव्ह केले आहे: “%s”",
)
