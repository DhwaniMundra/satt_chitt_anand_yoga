package com.sattchittanand.yoga.companion

import com.google.ai.edge.litertlm.Tool
import com.google.ai.edge.litertlm.ToolParam
import com.google.ai.edge.litertlm.ToolSet
import java.text.Normalizer
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.temporal.ChronoUnit
import java.util.Locale

/*
 * The practice companion's conversation: the system message, the six tools and the "Remember that…" rule. Tools
 * return summaries worked out in code, so Gemma never adds up rows; the notes section a message names, for a message
 * about classes the coming classes, and for a message about one's own asana that asana's progress are handed to Gemma
 * up front, so it answers from them even when it does not call a tool. Plain Kotlin (the tools use LiteRT-LM's annotations only), so the JVM unit tests run it with a
 * stand-in for the server.
 */

const val HISTORY_TURNS = 6 // earlier messages replayed as context; lasting facts belong in saved notes

/** Words that make a message about the class schedule, in English, Hindi and Marathi: such messages get the coming
 *  classes of the student's batch up front. */
val SCHEDULE_WORDS = listOf("class", "batch", "tomorrow", "today", "next", "schedule", "कक्षा", "क्लास", "बैच", "कल ", "आज", "अगल", "कब",
    "वर्ग", "बॅच", "उद्या", "पुढ", "कधी")

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
1. For anything about this student's practice, classes or moods, call a tool first and use only what it returns; for
   one asana, pranayama or meditation, call asana_progress (its teacher_said is what {teacher} wrote to them about it).
   Never invent numbers or dates. Report summaries exactly as the tool gives them.
2. For yoga or health guidance, call search_studio_notes and answer only from what it returns.
3. When the student asks you to remember something, call save_my_note. When they ask what they told you, call
   get_my_notes.
4. You are not a doctor: never diagnose, never promise a cure, never tell anyone to start, change or stop a medicine.
   For pain, illness, pregnancy or medicine, give only gentle general guidance and say to ask their doctor and to tell
   {teacher} before class.
5. Keep replies short and warm: at most 90 words.
6. Reply only in {language}."""

// ---------- what the tools read ----------

/** A coming class of the student's batch, from the server's /home (the batch's name and words in the student's
 *  language). */
data class UpcomingClass(val startsAt: Instant, val name: String, val about: String)

/** A note the companion keeps on this phone. */
data class KeptNote(val text: String, val savedAt: Instant)

/** An item of the studio's library, by all its names, for finding the one a student or Gemma means. */
data class ItemName(val key: String, val sanskrit: String, val name: String, val english: String, val aliases: List<String>) {
    /** "Vajrasana (वज्रासन, Thunderbolt pose)": every way the student may know it. */
    val full get() = "$name ($sanskrit, $english)"

    /** Its names folded for comparing ([foldName]), the key among them. */
    val forms: List<String> by lazy { (listOf(key.replace('_', ' '), sanskrit, name, english) + aliases).map(::foldName).filter { it.isNotEmpty() } }
}

/** What the tools read and write. The practice summary and the classes come from the server, the notes from the phone. */
interface StudentData {
    /** The server's practice summary (GET /me/practice), as maps and lists. Throws when the server cannot be reached. */
    fun practice(days: Int, lang: String): Map<String, Any?>

    /** The coming classes, soonest first (GET /home). Throws when the server cannot be reached. */
    fun upcoming(lang: String): List<UpcomingClass>

    fun saveNote(text: String)
    fun notes(): List<KeptNote>

    /** The studio's library (GET /curricula). Throws when the server cannot be reached. */
    fun library(): List<ItemName>

    /** One item's history for this student, the sums done (GET /me/asanas/{key}). Throws when the server cannot be
     *  reached. */
    fun itemProgress(key: String): Map<String, Any?>
}

// ---------- finding the item a name means ----------

private val SELF_WORDS = listOf("my ", "i ", "i'", "me ", "मेरा", "मेरी", "मेरे", "मैं", "माझ", "मी ", "मला")

/** A name reduced for comparing: lower case, without accents or the nukta, without "pose" or "posture" and without
 *  "asana", "asan" or "आसन" (as a word or an ending), the words run together: "Vajrāsana", "vajrasan", "वज्रासन" and
 *  "वज्र आसन" all become one form, as do "Thunderbolt pose" and "thunderbolt". */
fun foldName(text: String): String {
    val plain = Normalizer.normalize(text.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "")
    return plain.split(Regex("[^\\p{L}\\p{M}\\p{N}]+"))
        .filter { it.isNotEmpty() && it != "pose" && it != "posture" }
        .joinToString("") { word -> listOf("asana", "asan", "ासन", "आसन").fold(word) { w, end -> w.removeSuffix(end) } }
}

/** The library key [asked] names: one of an item's names exactly (folded), else the one item a name starts. */
fun resolveItem(asked: String, library: List<ItemName>): String? {
    val q = foldName(asked)
    if (q.isEmpty()) return null
    library.firstOrNull { q in it.forms }?.let { return it.key }
    return library.filter { item -> item.forms.any { it.startsWith(q) || q.startsWith(it) } }.singleOrNull()?.key
}

/** The items whose names are closest to [asked], for telling Gemma what there is. */
fun closestItems(asked: String, library: List<ItemName>, n: Int = 3): List<String> {
    val q = foldName(asked)
    fun shared(form: String) = form.zip(q).takeWhile { (a, b) -> a == b }.size
    return library.sortedByDescending { item -> item.forms.maxOfOrNull(::shared) ?: 0 }.take(n).map { it.name }
}

private val IST: ZoneId = ZoneId.of("Asia/Kolkata")
private val DATE = DateTimeFormatter.ofPattern("EEEE d MMMM", Locale.ENGLISH)
private val TIME = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)

private val REACTIONS = listOf("not yet", "with effort", "steady", "at ease")

/** An average of the four reactions (1 to 4) in words: "2.0, with effort", "3.7, between steady and at ease". */
fun reactionWords(average: Number): String {
    val a = average.toDouble()
    val low = REACTIONS[(a.toInt() - 1).coerceIn(0, 3)]
    val words = if (a % 1 < 0.05 || a >= 4) low else "between $low and ${REACTIONS[a.toInt().coerceIn(0, 3)]}"
    return String.format(Locale.ENGLISH, "%.1f, %s", a, words)
}

/** An item's progress as Gemma reads it ([Tools.asanaProgress]): the server's sums, each date with its weekday and
 *  each average reaction in words, so the model has nothing to work out. */
fun progressSummary(item: ItemName, p: Map<String, Any?>): Map<String, Any?> {
    fun day(value: Any?) = (value as? String)?.let { DATE.format(LocalDate.parse(it)) }

    @Suppress("UNCHECKED_CAST")
    fun map(key: String) = p[key] as? Map<String, Any?>
    val trend = map("reaction_trend")
    val times = { n: Any?, which: String -> if (n == 1 || n == 1.0) "$which time" else "$which ${(n as Number).toInt()} times" }
    @Suppress("UNCHECKED_CAST")
    val notes = (p["your_notes"] as? List<Map<String, Any?>>).orEmpty()
    return linkedMapOf(
        "asana" to item.full,
        "times_in_class" to p["in_class"],
        "times_on_own" to p["solo"],
        "first" to day(p["first"]),
        "last" to day(p["last"]),
        "how_it_felt" to trend?.let {
            linkedMapOf(times(it["each"], "first") to (it["early_average"] as? Number)?.let(::reactionWords),
                times(it["each"], "last") to (it["recent_average"] as? Number)?.let(::reactionWords))
        },
        "holds" to map("holds"),
        "strain_or_pain" to map("strain_or_pain")?.let { linkedMapOf("times" to it["times"], "last" to day(it["last"])) },
        "teacher_said" to map("teacher_said")?.let { linkedMapOf("date" to day(it["date"]), "text" to it["text"]) },
        "your_notes" to notes.map { linkedMapOf("date" to day(it["date"]), "text" to it["text"]) },
    )
}

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
            linkedMapOf("day" to day, "time" to TIME.format(start) + " India time", "class" to c.name, "about" to c.about)
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
            readable(data.practice(days.coerceIn(1, 90), lang))
        } catch (e: Exception) {
            mapOf("error" to UNREACHABLE)
        }
    }

    /** The summary with the ISO date of each class and each session on one's own written out ("Monday 16 November"),
     *  each item's average reaction in words, and the moods named as the classes' (practice on one's own asks none), so
     *  Gemma need not work out weekdays or read a scale. */
    private fun readable(summary: Map<String, Any?>): Map<String, Any?> = summary.entries.associate { (k, v) ->
        (if (k == "average_mood_before" || k == "average_mood_after") k.replace("mood", "class_mood") else k) to v
    } + listOf("classes", "solo").mapNotNull { key ->
        @Suppress("UNCHECKED_CAST")
        (summary[key] as? List<Map<String, Any?>>)?.let { days -> key to days.map { it + ("date" to DATE.format(LocalDate.parse(it["date"] as String))) } }
    } + listOfNotNull(
        @Suppress("UNCHECKED_CAST")
        (summary["top_items"] as? List<Map<String, Any?>>)?.let { items ->
            "top_items" to items.map { it + ("average_reaction" to (it["average_reaction"] as? Number)?.let(::reactionWords)) }
        },
    )

    /** How this student's practice of one item has gone: the server's sums for it, its dates written out, its average
     *  reactions in words; or what the studio's list has closest when [asana] names nothing in it. */
    fun asanaProgress(asana: String): Map<String, Any?> {
        used += "asana_progress"
        return try {
            val library = data.library()
            val key = resolveItem(asana, library)
                ?: return mapOf("error" to "Nothing called \"$asana\" is in the studio's list. The closest: ${closestItems(asana, library).joinToString(", ")}.")
            progressSummary(library.first { it.key == key }, data.itemProgress(key))
        } catch (e: Exception) {
            mapOf("error" to UNREACHABLE)
        }
    }

    /** The item a message about the student's own practice names (a word, or two or three together), or null. */
    fun itemNamedIn(message: String): String? {
        val lowered = "${message.lowercase()} "
        if (SELF_WORDS.none { it in lowered }) return null
        val library = try {
            data.library()
        } catch (e: Exception) {
            return null
        }
        val words = message.split(Regex("[^\\p{L}\\p{M}\\p{N}']+")).filter { it.isNotEmpty() }
        return (3 downTo 1).asSequence().flatMap { n -> words.windowed(n).map { it.joinToString(" ") } }
            .firstNotNullOfOrNull { phrase -> foldName(phrase).takeIf { it.isNotEmpty() }?.let { f -> library.firstOrNull { f in it.forms }?.key } }
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
    fun toolSets(): List<ToolSet> = listOf(Practice(this), Progress(this), Schedule(this), Search(this), Save(this), Recall(this))

    @Suppress("FunctionName")
    private class Practice(private val t: Tools) : ToolSet {
        @Tool(description = "This student's classes over the last `days` days, with how they felt before and after (summaries included).")
        fun get_my_practice(@ToolParam(description = "how many days back to look, for example 7 for this week or 30 for this month.") days: Int) =
            t.getMyPractice(days)
    }

    @Suppress("FunctionName")
    private class Progress(private val t: Tools) : ToolSet {
        @Tool(description = "How this student's practice of one asana, pranayama or meditation has gone: times in class and on their own, how it felt at first and lately, holds, strain or pain, their notes and what the teacher wrote.")
        fun asana_progress(@ToolParam(description = "the item, by any of its names, for example \"Vajrasana\", \"वज्रासन\" or \"thunderbolt pose\".") asana: String) =
            t.asanaProgress(asana)
    }

    @Suppress("FunctionName")
    private class Schedule(private val t: Tools) : ToolSet {
        @Tool(description = "This student's batch's classes in the coming week, soonest first: when, time, batch.")
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

    /** The system message for [message]; [batch] is the name of the student's batch, once the teacher has placed them. */
    fun system(firstName: String, message: String, lang: String, tools: Tools, batch: String? = null): String {
        val base = SYSTEM.replace("{studio}", studioName).replace("{name}", firstName).replace("{teacher}", teacher)
            .replace("{language}", LANGUAGE_NAMES.getValue(lang))
        val placed = batch?.let { "\n\n$firstName practises in the $it batch; their classes are that batch's, and a move to another batch is $teacher's to decide." }.orEmpty()
        val progress = preloadedProgress(message, tools)
        val schedule = preloadedSchedule(message, tools)
        return base + placed + progress + schedule + preloadedNotes(message, lang, tools.used, schedule = schedule.isNotEmpty())
    }

    /** How the asana a message about the student's own practice names has gone, as text for the system message (or
     *  ""). Recorded as a use of asana_progress. */
    fun preloadedProgress(message: String, tools: Tools): String {
        if (REMEMBER.containsMatchIn(message)) return "" // something to keep, not a question about the asana
        val key = tools.itemNamedIn(message) ?: return ""
        val progress = tools.asanaProgress(key)
        if ("error" in progress) return "".also { tools.used.removeAt(tools.used.lastIndex) }
        val lines = progress.entries.joinToString("\n") { (k, v) -> "- $k: $v" }
        return "\n\nHow ${progress["asana"]} has gone for this student (asana_progress). Answer from it:\n$lines"
    }

    /** The coming classes as text for the system message when [message] is about the schedule (or ""). Recorded as a
     *  use of get_upcoming_classes, since the student sees it the same way. */
    fun preloadedSchedule(message: String, tools: Tools): String {
        val lowered = "${message.lowercase()} "
        if (SCHEDULE_WORDS.none { it in lowered }) return ""
        val schedule = tools.getUpcomingClasses()

        @Suppress("UNCHECKED_CAST")
        val classes = schedule["classes"] as? List<Map<String, Any?>> ?: return "".also { tools.used.removeAt(tools.used.lastIndex) }
        val lines = classes.joinToString("\n") { c -> "- ${c["day"]}: ${c["class"]} at ${c["time"]}" }
        return "\n\nToday is ${schedule["today_is"]}. This student's coming classes, in their batch. Answer from them:\n$lines"
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
