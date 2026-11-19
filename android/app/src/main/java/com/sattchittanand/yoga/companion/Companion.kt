package com.sattchittanand.yoga.companion

import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/*
 * The practice companion's conversation: the system message, the five tools and the "Remember that…" rule. Tools
 * return summaries worked out in code, so Gemma never adds up rows; the notes section a message names and, for a
 * message about classes, the coming classes are handed to Gemma up front, so it answers from them even when it does
 * not call a tool. Plain Kotlin (the tools use LiteRT-LM's annotations only), so the JVM unit tests run it with a
 * stand-in for the server.
 */

const val HISTORY_TURNS = 6 // earlier messages replayed as context; lasting facts belong in saved notes

/** Words that make a message about the class schedule, in English, Hindi and Marathi: such messages get the coming
 *  classes up front. */
val SCHEDULE_WORDS = listOf("class", "tomorrow", "today", "next", "schedule", "कक्षा", "क्लास", "कल ", "आज", "अगल", "कब",
    "वर्ग", "उद्या", "पुढ", "कधी")

/** The words the app teaches for saving a note ("Remember that…"), at the start of a message. `\s` spelt out as in
 *  [isUrgent]. */
private const val S = "[\\s\\p{Z}]"
private val REMEMBER = Regex(
    "^(?:$S*(?:please$S+)?remember${S}+that$S+|$S*(?:कृपया$S+)?याद${S}+रख(?:ना|ें|िए|ो)$S+कि$S+|$S*(?:कृपया$S+)?लक्षात${S}+ठेवा$S+की$S+)",
    RegexOption.IGNORE_CASE,
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

/** The next classes, each with an unambiguous day ("tomorrow, Friday 20 November"), so Gemma need not work out dates. */
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
 * this order. Each records its name in [used].
 */
class Tools(private val data: StudentData, private val notes: StudioNotes, private val lang: String, private val now: () -> Instant = Instant::now) {
    val used = mutableListOf<String>()

    fun getMyPractice(days: Int): Map<String, Any?> {
        used += "get_my_practice"
        return try {
            withWeekdays(data.practice(days.coerceIn(1, 90), lang))
        } catch (e: Exception) {
            mapOf("error" to UNREACHABLE)
        }
    }

    /** The summary with the ISO date of each class and each session on one's own written out ("Monday 16 November"), so
     *  Gemma need not work out weekdays. */
    private fun withWeekdays(summary: Map<String, Any?>): Map<String, Any?> = summary + listOf("classes", "solo").mapNotNull { key ->
        @Suppress("UNCHECKED_CAST")
        (summary[key] as? List<Map<String, Any?>>)?.let { days -> key to days.map { it + ("date" to DATE.format(LocalDate.parse(it["date"] as String))) } }
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

    /** The tools as LiteRT-LM reads them: names, descriptions and parameters from the annotations. */
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

/** The system message, with the coming classes and the matching notes handed over up front. */
class PracticeCompanion(val notes: StudioNotes, private val studioName: String, private val teacher: String) {

    fun system(firstName: String, message: String, lang: String, tools: Tools): String {
        val base = SYSTEM.replace("{studio}", studioName).replace("{name}", firstName).replace("{teacher}", teacher)
            .replace("{language}", LANGUAGE_NAMES.getValue(lang))
        val schedule = preloadedSchedule(message, tools)
        return base + schedule + preloadedNotes(message, lang, tools.used, schedule = schedule.isNotEmpty())
    }

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

    /** The notes section on the topic [message] names, as text for the system message (or ""), so a health question
     *  is answered from the notes even when Gemma does not search them. With the [schedule] already handed over, a
     *  class word does not count as naming a topic, so "which class tomorrow?" is answered from the schedule rather
     *  than from "About the studio and classes". */
    fun preloadedNotes(message: String, lang: String, used: MutableList<String>, schedule: Boolean = false): String {
        val ignore = if (schedule) SCHEDULE_WORDS.map { it.trim() } else emptyList()
        val section = notes.retriever.named(message, ignore) ?: return ""
        used += "search_studio_notes"
        return "\n\nThe studio's notes on what the student asks about. Answer from them:\n### ${section.title}\n${notes.text(section, lang)}"
    }
}

/**
 * The note to save when [message] starts with the words the app teaches ("Remember that…") and Gemma did not call
 * save_my_note, which it sometimes skips while saying it has saved. Null when there is nothing to save.
 */
fun noteToSave(message: String, used: List<String>): String? {
    val match = REMEMBER.find(message) ?: return null
    val note = message.substring(match.range.last + 1).trim().take(500)
    if (note.isEmpty() || "save_my_note" in used) return null
    return note.substring(0, 1).uppercase() + note.substring(1) // "My left knee…", as it reads in the health notes
}
