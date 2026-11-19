package com.sattchittanand.yoga

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.text.Normalizer
import java.time.Instant
import java.time.LocalDate

/** What the app keeps on the phone: the login token, the chosen language and, in a debug build, the server address. */
class Prefs(context: Context) {
    private val store = context.getSharedPreferences("sca", Context.MODE_PRIVATE)

    var token: String?
        get() = store.getString("token", null)
        set(value) = store.edit().putString("token", value).apply()

    /** The backend, fixed at build time. A debug build may be pointed elsewhere on its first screen. */
    var server: String
        get() = store.getString("server", null)?.takeIf { BuildConfig.DEBUG } ?: BuildConfig.SERVER
        set(value) = store.edit().putString("server", value.trim().trimEnd('/')).apply()

    var lang: String
        get() = store.getString("lang", null) ?: "en"
        set(value) = store.edit().putString("lang", value).apply()

    companion object {
        /** Read before the activity exists, to pick the language its resources load in. */
        fun lang(context: Context): String =
            context.getSharedPreferences("sca", Context.MODE_PRIVATE).getString("lang", null) ?: "en"
    }
}

/** An error the server named ("bad_login", "pending", …) or "network" when it could not be reached. */
class ApiError(val code: String) : Exception(code)

/**
 * The backend's API. The backend is a Google Apps Script web app, which cannot read request headers or set a status,
 * so every call is one POST of an envelope {"method", "path", "token", "body"} (the path carries the query string),
 * and every answer is HTTP 200 with {"status", "body"}: `status` is the call's real status. Apps Script answers the
 * POST with a redirect to script.googleusercontent.com, to be fetched with GET; the dev backend answers the same way.
 */
class Api(private val prefs: Prefs) {

    suspend fun get(path: String) = call("GET", path, null)
    suspend fun post(path: String, body: JSONObject = JSONObject()) = call("POST", path, body)
    suspend fun put(path: String, body: JSONObject) = call("PUT", path, body)

    private suspend fun call(method: String, path: String, body: JSONObject?): JSONObject = withContext(Dispatchers.IO) { request(method, path, body) }

    /** A GET on the calling thread, for the companion's tools, which run on Gemma's own thread. */
    fun getNow(path: String): JSONObject = request("GET", path, null)

    private fun request(method: String, path: String, body: JSONObject?): JSONObject {
        val envelope = JSONObject().put("method", method).put("path", path).put("token", prefs.token ?: "").put("body", body ?: JSONObject.NULL)
        val reply = try {
            JSONObject(exchange(envelope.toString()))
        } catch (e: IOException) {
            throw ApiError("network")
        } catch (e: JSONException) { // not JSON: a sign-in page, a wrong address
            throw ApiError("generic")
        }
        val answer = reply.optJSONObject("body") ?: JSONObject()
        if (reply.optInt("status") !in 200..299) {
            throw ApiError(answer.optString("detail").takeIf { it.isNotEmpty() && !it.startsWith("[") } ?: "generic")
        }
        return answer
    }

    /** POSTs the envelope, then follows the redirect with GET. */
    private fun exchange(envelope: String): String {
        var conn = open(URL(prefs.server))
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        conn.outputStream.use { it.write(envelope.toByteArray()) }
        repeat(MAX_REDIRECTS + 1) {
            val code = conn.responseCode
            if (code !in 300..399) {
                if (code != HttpURLConnection.HTTP_OK) throw IOException("HTTP $code")
                return conn.inputStream.bufferedReader().use { it.readText() }
            }
            val location = conn.getHeaderField("Location") ?: throw IOException("redirect without a Location")
            val next = URL(conn.url, location)
            conn.disconnect()
            conn = open(next)
        }
        throw IOException("too many redirects")
    }

    private fun open(url: URL) = (url.openConnection() as HttpURLConnection).apply {
        instanceFollowRedirects = false
        connectTimeout = 10_000
        readTimeout = 30_000 // Apps Script can take some seconds to start
    }

    private companion object {
        const val MAX_REDIRECTS = 3
    }
}

// ---------- models, parsed from the server's JSON ----------

fun JSONObject.str(key: String): String? = if (isNull(key)) null else getString(key)
fun JSONObject.dbl(key: String): Double? = if (isNull(key)) null else getDouble(key)
fun <T> JSONArray.map(transform: (JSONObject) -> T): List<T> = (0 until length()).map { transform(getJSONObject(it)) }
fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }

/** A user; a student's [batch] (a key) and since when, once the teacher has placed them. */
data class User(val id: Int, val name: String, val phone: String, val role: String, val status: String, val batch: String?, val batchSince: Instant?) {
    val isTeacher get() = role == "teacher"
    val isApproved get() = status == "approved"

    companion object {
        fun from(o: JSONObject) = User(o.getInt("id"), o.getString("name"), o.getString("phone"), o.getString("role"), o.getString("status"),
            o.str("batch"), o.str("batch_since")?.let(Instant::parse))
    }
}

/** A batch: its name and words in the chosen language, its days ("mon"…) and start in India ("07:00"). */
data class BatchInfo(val key: String, val name: String, val about: String, val days: List<String>, val time: String?) {
    companion object {
        fun from(o: JSONObject) = BatchInfo(o.getString("key"), o.getString("name"), o.getString("about"), o.getJSONArray("days").strings(), o.str("time"))
    }
}

data class ClassSession(
    val id: Int,
    val startsAt: Instant,
    val minutes: Int,
    val batch: BatchInfo,
    val meetLink: String?,
    val hasLink: Boolean,
    val checkedIn: Boolean,
    val ownLink: Boolean,
    val joined: Int,
    /** The key of the curriculum the class follows. */
    val curriculum: String?,
) {
    val endsAt: Instant get() = startsAt.plusSeconds(minutes * 60L)

    companion object {
        fun from(o: JSONObject) = ClassSession(
            o.getInt("id"), Instant.parse(o.getString("starts_at")), o.getInt("duration_min"), BatchInfo.from(o.getJSONObject("batch")),
            o.str("meet_link"), o.getBoolean("has_link"), o.optBoolean("checked_in"), o.optBoolean("own_link"), o.optInt("joined"),
            o.optString("curriculum").ifEmpty { null },
        )
    }
}

/** An asana, pranayama or meditation of the studio's library. */
data class LibraryItem(val key: String, val type: String, val sanskrit: String, val name: String, val english: String, val aliases: List<String>) {
    /** Its name as the student reads it: "Vajrasana · Thunderbolt pose" in English, "वज्रासन" in Hindi and Marathi. */
    fun title(lang: String) = if (lang == "en") "$name · $english" else sanskrit

    /** Its name alone, for a sentence: "Vajrasana", or "वज्रासन". */
    fun short(lang: String) = if (lang == "en") name else sanskrit

    /** Whether a search finds it: one of its names or aliases with a word starting as typed, accents and case aside. */
    fun matches(query: String): Boolean {
        val q = fold(query)
        if (q.isEmpty()) return false
        val atWordStart = Regex("(?<![\\p{L}\\p{M}])" + Regex.escape(q))
        return (listOf(sanskrit, name, english) + aliases).any { atWordStart.containsMatchIn(fold(it)) }
    }

    private fun fold(text: String) = Normalizer.normalize(text.trim().lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{Mn}+"), "")
}

/** One item of a curriculum: so many breaths, seconds, minutes, rounds or strokes, and how to do it. */
data class PlanItem(val item: String, val dose: Int, val unit: String, val cue: String)

data class Curriculum(val key: String, val name: String, val about: String, val items: List<PlanItem>)

/** The studio's library and curricula, in the chosen language (GET /curricula). */
data class Curricula(val library: Map<String, LibraryItem>, val curricula: List<Curriculum>) {
    fun find(key: String?) = curricula.firstOrNull { it.key == key }

    companion object {
        fun from(o: JSONObject) = Curricula(
            o.getJSONArray("library").map {
                LibraryItem(it.getString("key"), it.getString("type"), it.getString("sanskrit"), it.getString("name"), it.getString("english"),
                    it.getJSONArray("aliases").let { a -> List(a.length()) { i -> a.getString(i) } })
            }.associateBy { it.key },
            o.getJSONArray("curricula").map { c ->
                Curriculum(c.getString("key"), c.getString("name"), c.getString("about"),
                    c.getJSONArray("items").map { PlanItem(it.getString("item"), it.getInt("dose"), it.getString("unit"), it.getString("cue")) })
            },
        )
    }
}

/** What a student says after class about one item: reaction 1 (not yet) to 4 (at ease), strain or pain, a note. */
data class ItemFeedback(val item: String, val reaction: Int?, val pain: Boolean, val note: String, val heldSeconds: Int = 0) {
    val said get() = reaction != null || pain || note.isNotBlank() || heldSeconds > 0

    fun json(): JSONObject = JSONObject().put("item", item).put("reaction", reaction ?: JSONObject.NULL).put("pain", if (pain) 1 else 0)
        .put("note", note.trim().ifEmpty { null } ?: JSONObject.NULL).apply { if (heldSeconds > 0) put("hold_s", heldSeconds) }
}

/** The first reactions against the latest, as averages on the 1 to 4 scale. */
data class Trend(val early: Double, val recent: Double) {
    companion object {
        fun from(o: JSONObject, key: String) = if (o.isNull(key)) null else o.getJSONObject(key).let { Trend(it.getDouble("early_average"), it.getDouble("recent_average")) }
    }
}

private fun JSONObject.date(key: String): LocalDate? = str(key)?.let(LocalDate::parse)

private fun JSONObject.intOrNull(key: String): Int? = if (isNull(key)) null else getInt(key)

/** One item of a student's practice list (GET /me/asanas): how often in class and solo, the trend, strain or pain, the
 *  teacher's word. */
data class ItemSummary(val item: String, val inClass: Int, val solo: Int, val trend: Trend?, val painTimes: Int, val teacherSaid: LocalDate?) {
    companion object {
        fun from(o: JSONObject) =
            ItemSummary(o.getString("item"), o.getInt("in_class"), o.getInt("solo"), Trend.from(o, "reaction_trend"), o.getInt("pain_times"), o.date("teacher_said"))
    }
}

/** One item's history for one student (GET /me/asanas/{item}): each time, newest first, the holds timed solo, and the
 *  teacher's feedback. */
data class ItemHistory(val item: String, val inClass: Int, val solo: Int, val first: LocalDate?, val trend: Trend?, val holds: Holds?,
    val painTimes: Int, val entries: List<ItemEntry>, val feedback: List<Pair<LocalDate, String>>) {
    companion object {
        fun from(o: JSONObject) = ItemHistory(
            o.getString("item"), o.getInt("in_class"), o.getInt("solo"), o.date("first"), Trend.from(o, "reaction_trend"),
            if (o.isNull("holds")) null else o.getJSONObject("holds").let { Holds(it.getInt("recent_seconds"), it.getInt("longest_seconds")) },
            o.getJSONObject("strain_or_pain").getInt("times"),
            o.getJSONArray("entries").map {
                ItemEntry(LocalDate.parse(it.getString("date")), it.getString("kind") == "solo", it.intOrNull("hold_s"), it.intOrNull("reaction"), it.getInt("pain") == 1, it.str("note"))
            },
            o.getJSONArray("feedback").map { LocalDate.parse(it.getString("date")) to it.getString("text") },
        )
    }
}

/** Practice on one's own, kept in memory until Finish: what was said about each item, the one in front of the student
 *  ([at]), each item's stopwatch time ([heldMs]), and since when the stopwatch has been running. Times are
 *  SystemClock.elapsedRealtime() milliseconds. [curriculum] is the sequence repeated, for its doses and cues. */
data class SoloRun(val startedAt: Long, val curriculum: String?, val said: List<ItemFeedback>, val heldMs: List<Long>, val at: Int = 0,
    val runningSince: Long? = null) {
    val current get() = said[at]

    fun held(now: Long) = heldMs[at] + (runningSince?.let { now - it } ?: 0)

    fun toggled(now: Long) = if (runningSince == null) copy(runningSince = now) else stopped(now)

    fun stopped(now: Long) = if (runningSince == null) this else copy(heldMs = heldMs.toMutableList().also { it[at] = held(now) }, runningSince = null)

    fun changed(f: ItemFeedback) = copy(said = said.toMutableList().also { it[at] = f })

    fun moved(to: Int, now: Long) = stopped(now).copy(at = to)

    /** What to send at Finish: each item with its stopwatch time, those with something timed or said. */
    fun entries() = said.mapIndexed { i, f -> f.copy(heldSeconds = (heldMs[i] / 1000).toInt()) }.filter { it.said }

    companion object {
        fun start(items: List<String>, curriculum: String?, now: Long) =
            SoloRun(now, curriculum, items.map { ItemFeedback(it, null, false, "") }, items.map { 0L })
    }
}

/** The stopwatch's holds, in seconds: the latest and the longest. */
data class Holds(val recent: Int, val longest: Int)

data class ItemEntry(val date: LocalDate, val solo: Boolean, val heldSeconds: Int?, val reaction: Int?, val pain: Boolean, val note: String?)

/** How a class went, item by item, for the teacher (GET /teacher/sessions/{id}/practice). */
data class ClassReview(val curriculum: String?, val joined: Int, val answered: Int, val items: List<ItemReview>) {
    companion object {
        fun from(o: JSONObject) = ClassReview(
            o.str("curriculum"), o.getInt("joined"), o.getInt("answered"),
            o.getJSONArray("items").map { i ->
                ItemReview(
                    i.getString("item"), (0 until 4).map { i.getJSONArray("reactions").getInt(it) },
                    i.getJSONArray("pain").map { it.getString("name") to it.str("note") },
                    i.getJSONArray("notes").map { it.getString("name") to it.getString("text") },
                )
            },
        )
    }
}

/** One item of a class review: how many said each reaction (not yet … at ease), who felt strain or pain, the notes. */
data class ItemReview(val item: String, val reactions: List<Int>, val pain: List<Pair<String, String?>>, val notes: List<Pair<String, String>>)

data class Studio(val tagline: String, val teacherName: String, val teacherTitle: String, val teacherBio: String) {
    companion object {
        fun from(o: JSONObject): Studio {
            val t = o.getJSONObject("teacher")
            return Studio(o.getString("tagline"), t.getString("name"), t.getString("title"), t.getString("bio"))
        }
    }
}

/** The studio's own words, in one language, from content/studio.json as the app bundles it. [name] holds the three
 *  parts of the studio's name: (Devanagari, Latin, meaning); [teacher] is how the app names the teacher. */
data class StudioWords(
    val blessing: String,
    val blessingMeaning: String,
    val nameIsAMap: String,
    val name: List<Triple<String, String, String>>,
    val week: String,
    val teacherHeading: String,
    val teacher: String,
) {
    companion object {
        fun from(studio: JSONObject, lang: String): StudioWords {
            fun JSONObject.pick(key: String) = getJSONObject(key).let { it.optString(lang).ifEmpty { it.getString("en") } }
            val w = studio.getJSONObject("words")
            val name = w.getJSONObject("name")
            return StudioWords(
                w.getJSONObject("blessing").getString("sa"), w.pick("blessing"), name.pick("map"),
                name.getJSONArray("parts").map { Triple(it.getString("sa"), it.getString("name"), it.pick("meaning")) },
                w.pick("week"), w.pick("teacher"), studio.getJSONObject("teacher").pick("short"),
            )
        }
    }
}

/** [batch]: the student's batch, once placed; [sessions]: its coming classes. [afterCheckin]: the class whose after-class
 *  window is open; [afterSaid]: what the student said about it, if anything. */
data class Home(val user: User, val batch: BatchInfo?, val studio: Studio, val sessions: List<ClassSession>, val afterCheckin: ClassSession?,
    val afterSaid: Said?, val groupLink: String?) {
    companion object {
        fun from(o: JSONObject): Home {
            val after = if (o.isNull("after_checkin")) null else o.getJSONObject("after_checkin")
            return Home(
                User.from(o.getJSONObject("user")), if (o.isNull("batch")) null else BatchInfo.from(o.getJSONObject("batch")),
                Studio.from(o.getJSONObject("studio")), o.getJSONArray("sessions").map(ClassSession::from),
                after?.let(ClassSession::from), after?.takeUnless { it.isNull("said") }?.getJSONObject("said")?.let(Said::from), o.str("group_link"),
            )
        }
    }
}

/** What a student said after a class: the mood, if given, and each item's answer. */
data class Said(val mood: Int?, val items: List<ItemFeedback>) {
    companion object {
        fun from(o: JSONObject) = Said(o.intOrNull("mood"), o.getJSONArray("items").map {
            ItemFeedback(it.getString("item"), it.intOrNull("reaction"), it.getInt("pain") == 1, it.str("note").orEmpty())
        })
    }
}

data class Stats(val classesJoined: Int, val streakDays: Int, val moodChange: Double?) {
    companion object {
        fun from(o: JSONObject) = Stats(o.getInt("classes_joined"), o.getInt("streak_days"), o.dbl("mood_change"))
    }
}

/** A class the student joined, from GET /me/practice: its date in India, its name, and the moods (1 to 5). */
data class JoinedClass(val date: LocalDate, val name: String, val curriculum: String?, val moodBefore: Int, val moodAfter: Int?) {
    companion object {
        fun from(o: JSONObject) =
            JoinedClass(LocalDate.parse(o.getString("date")), o.getString("class"), o.str("curriculum"), o.getInt("mood_before"), o.intOrNull("mood_after"))
    }
}

/** A session of practice on one's own (GET /me/practice): its day, how long, and its items' names. */
data class SoloSession(val date: LocalDate, val minutes: Int, val items: List<String>) {
    companion object {
        fun from(o: JSONObject) = SoloSession(LocalDate.parse(o.getString("date")), o.getInt("minutes"), o.getJSONArray("items").let { a -> List(a.length()) { a.getString(it) } })
    }
}

data class TeacherSettings(val groupLink: String?, val groupCode: String)

/** A batch with its everyday Meet link, for its classes without their own. */
data class BatchLink(val info: BatchInfo, val meetLink: String?)

data class TeacherHome(val sessions: List<ClassSession>, val batches: List<BatchLink>, val settings: TeacherSettings, val pendingStudents: Int) {
    fun batch(key: String?) = batches.firstOrNull { it.info.key == key }

    companion object {
        fun from(o: JSONObject): TeacherHome {
            val s = o.getJSONObject("settings")
            return TeacherHome(
                o.getJSONArray("sessions").map(ClassSession::from),
                o.getJSONArray("batches").map { BatchLink(BatchInfo.from(it), it.str("meet_link")) },
                TeacherSettings(s.str("group_link"), s.getString("group_code")),
                o.getInt("pending_students"),
            )
        }
    }
}

data class Student(val user: User, val joined: Int) {
    companion object {
        fun from(o: JSONObject) = Student(User.from(o), o.getInt("joined"))
    }
}

data class SessionInsight(val id: Int, val startsAt: Instant, val className: String, val joined: Int, val moodBefore: Double?, val moodAfter: Double?)
data class Feedback(val name: String, val text: String)

data class Insights(
    val approved: Int,
    val moodChange: Double?,
    val moodPairs: Int,
    val sessions: List<SessionInsight>,
    val feedback: List<Feedback>,
) {
    companion object {
        fun from(o: JSONObject) = Insights(
            o.getJSONObject("students").getInt("approved"), o.dbl("mood_change"), o.getInt("mood_pairs"),
            o.getJSONArray("sessions").map {
                SessionInsight(it.getInt("id"), Instant.parse(it.getString("starts_at")), it.getString("class"), it.getInt("joined"), it.dbl("mood_before"), it.dbl("mood_after"))
            },
            o.getJSONArray("feedback").map { Feedback(it.getString("name"), it.getString("text")) },
        )
    }
}

/**
 * One message in the chat with the practice companion, kept on this phone ([LocalStore]). A reply's `tools` are the
 * companion's tools it used, by name, each once; an urgent reply stays marked after a restart.
 */
data class ChatLine(val text: String, val fromStudent: Boolean, val tools: List<String> = emptyList(), val urgent: Boolean = false)

/** One of the student's health notes, kept on this phone; [sharedId] once shared with the teacher. */
data class Note(val id: Int, val text: String, val savedAt: Instant, val sharedId: Int? = null)

/** A note a student shared with the teacher, as the teacher's Students screen shows it (GET /teacher/shared). */
data class SharedNote(val student: String, val text: String, val sharedAt: Instant) {
    companion object {
        fun from(o: JSONObject) = SharedNote(o.getString("name"), o.getString("text"), Instant.parse(o.getString("created_at")))
    }
}
