package com.sattchittanand.yoga

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
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
import kotlin.random.Random

/** What the app keeps on the phone: the login token, the chosen language, the practice on one's own in progress and,
 *  in a debug build, the server address. */
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

    /** The practice on one's own in progress, as [SoloRun.saved] writes it. */
    var solo: String?
        get() = store.getString("solo", null)
        set(value) = store.edit().putString("solo", value).apply()

    companion object {
        /** Read before the activity exists, to pick the language its resources load in. */
        fun lang(context: Context): String =
            context.getSharedPreferences("sca", Context.MODE_PRIVATE).getString("lang", null) ?: "en"
    }
}

/** An error the server named ("bad_login", "pending", …), "network" when it could not be reached, or for a check the
 *  server's validation refused, a [problemCode] naming the field. */
class ApiError(val code: String) : Exception(code)

/** A 422's first problem as a code the app words: "too_long:pain_note:600", "range:height_cm" or "invalid:name", the
 *  field being the last name in its location (["body", "entries", 0, "note"] is "note"). */
fun problemCode(detail: JSONArray): String {
    val first = detail.optJSONObject(0) ?: return "generic"
    val loc = first.optJSONArray("loc") ?: JSONArray()
    val field = (loc.length() - 1 downTo 0).map { loc.opt(it) }.firstOrNull { it is String } as String? ?: "body"
    return when (first.text("type")) {
        "string_too_long" -> "too_long:$field:${first.optJSONObject("ctx")?.intOrNull("max_length") ?: 0}"
        "greater_than_equal", "less_than_equal" -> "range:$field"
        else -> "invalid:$field"
    }
}

/**
 * The backend's API. The backend is a Google Apps Script web app, which cannot read request headers or set a status,
 * so every call is one POST of an envelope {"method", "path", "token", "body"} (the path carries the query string),
 * and every answer is HTTP 200 with {"status", "body"}: `status` is the call's real status. Apps Script answers the
 * POST with a redirect to script.googleusercontent.com, to be fetched with GET; the dev backend answers the same way.
 * A write that creates something carries a request id: the server answers a repeat of it as it did the first time.
 */
class Api(private val prefs: Prefs) {

    suspend fun get(path: String) = call("GET", path, null, null)

    /** [requestId] for a write that creates something: the same id for each try of the same action. */
    suspend fun post(path: String, body: JSONObject = JSONObject(), requestId: String? = null) = call("POST", path, body, requestId)
    suspend fun put(path: String, body: JSONObject, requestId: String? = null) = call("PUT", path, body, requestId)

    /** Tries again, waiting a little longer each time, while the server is busy (its lock was taken, so nothing was
     *  done) and, for a write with a request id, which the server writes once, while the connection fails. */
    private suspend fun call(method: String, path: String, body: JSONObject?, requestId: String?): JSONObject = withContext(Dispatchers.IO) {
        var wait = FIRST_WAIT_MS
        while (wait <= LAST_WAIT_MS) {
            try {
                return@withContext request(method, path, body, requestId)
            } catch (e: ApiError) {
                if (e.code != "busy" && !(e.code == "network" && requestId != null)) throw e
            }
            delay(wait + Random.nextLong(wait / 2))
            wait *= 2
        }
        request(method, path, body, requestId) // the last try: its error is the caller's
    }

    /** A GET on the calling thread, for the companion's tools, which run on Gemma's own thread. */
    fun getNow(path: String): JSONObject = request("GET", path, null, null)

    private fun request(method: String, path: String, body: JSONObject?, requestId: String?): JSONObject {
        val envelope = JSONObject().put("method", method).put("path", path).put("token", prefs.token ?: "").put("body", body ?: JSONObject.NULL)
        if (requestId != null) envelope.put("request_id", requestId)
        val reply = try {
            JSONObject(exchange(envelope.toString()))
        } catch (e: IOException) {
            throw ApiError("network")
        } catch (e: JSONException) { // not JSON: a sign-in page, a wrong address
            throw ApiError("generic")
        }
        val answer = reply.optJSONObject("body") ?: JSONObject()
        if (reply.optInt("status") !in 200..299) {
            throw ApiError(when (val detail = answer.opt("detail")) {
                is JSONArray -> problemCode(detail)
                is String -> detail.ifEmpty { "generic" }
                else -> "generic"
            })
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
        const val FIRST_WAIT_MS = 1_000L // then 2 s and 4 s, and a last try: four in all
        const val LAST_WAIT_MS = 4_000L
    }
}

// ---------- models, parsed from the server's JSON ----------
// Much of it comes from cells the owner types in the Sheet (the batches, the library, the curricula), any of which
// may be left empty: those are read with [text] and [intOrNull], so one odd row never stops a screen.

fun JSONObject.str(key: String): String? = if (isNull(key)) null else getString(key)
fun JSONObject.dbl(key: String): Double? = if (isNull(key)) null else getDouble(key)

/** Text, "" when null or missing. */
fun JSONObject.text(key: String): String = if (isNull(key)) "" else optString(key)

/** A whole number, or null when it is null, missing or not one. */
fun JSONObject.intOrNull(key: String): Int? = when (val v = opt(key)) {
    is Number -> v.toInt()
    is String -> v.trim().toIntOrNull()
    else -> null
}

fun <T> JSONArray.map(transform: (JSONObject) -> T): List<T> = (0 until length()).map { transform(getJSONObject(it)) }
fun JSONArray.strings(): List<String> = (0 until length()).map { getString(it) }
private fun JSONObject.list(key: String): JSONArray = optJSONArray(key) ?: JSONArray()

/** A user; a student's [batch] (a key) and since when, once the teacher has placed them. */
data class User(val id: Int, val name: String, val phone: String, val role: String, val status: String, val batch: String?, val batchSince: Instant?) {
    val isTeacher get() = role == "teacher"
    val isApproved get() = status == "approved"

    companion object {
        fun from(o: JSONObject) = User(o.getInt("id"), o.text("name"), o.text("phone"), o.text("role"), o.text("status"),
            o.str("batch"), o.str("batch_since")?.let(Instant::parse))
    }
}

/** A batch: its name and words in the chosen language, and its start in India ("07:00"). */
data class BatchInfo(val key: String, val name: String, val about: String, val time: String?) {
    companion object {
        fun from(o: JSONObject) = BatchInfo(o.text("key"), o.text("name"), o.text("about"), o.str("time"))
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
            o.getInt("id"), Instant.parse(o.getString("starts_at")), o.intOrNull("duration_min") ?: 55, BatchInfo.from(o.getJSONObject("batch")),
            o.str("meet_link"), o.optBoolean("has_link"), o.optBoolean("checked_in"), o.optBoolean("own_link"), o.optInt("joined"),
            o.str("curriculum")?.ifEmpty { null },
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

/** One item of a curriculum: so many breaths, seconds, minutes, rounds or strokes, and how to do it. [dose] is null
 *  when the owner left it empty or wrote words; the unit or the cue then says it alone. */
data class PlanItem(val item: String, val dose: Int?, val unit: String, val cue: String)

data class Curriculum(val key: String, val name: String, val about: String, val items: List<PlanItem>)

/** The studio's library and curricula, in the chosen language (GET /curricula). */
data class Curricula(val library: Map<String, LibraryItem>, val curricula: List<Curriculum>) {
    fun find(key: String?) = curricula.firstOrNull { it.key == key }

    companion object {
        fun from(o: JSONObject) = Curricula(
            o.list("library").map {
                LibraryItem(it.text("key"), it.text("type"), it.text("sanskrit"), it.text("name"), it.text("english"), it.list("aliases").strings())
            }.associateBy { it.key },
            o.list("curricula").map { c ->
                Curriculum(c.text("key"), c.text("name"), c.text("about"),
                    c.list("items").map { PlanItem(it.text("item"), it.intOrNull("dose"), it.text("unit"), it.text("cue")) })
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
    val painTimes: Int, val entries: List<ItemEntry>, val feedback: List<Pair<Instant, String>>) {
    companion object {
        fun from(o: JSONObject) = ItemHistory(
            o.getString("item"), o.getInt("in_class"), o.getInt("solo"), o.date("first"), Trend.from(o, "reaction_trend"),
            if (o.isNull("holds")) null else o.getJSONObject("holds").let { Holds(it.getInt("recent_seconds"), it.getInt("longest_seconds")) },
            o.getJSONObject("strain_or_pain").getInt("times"),
            o.getJSONArray("entries").map {
                ItemEntry(Instant.parse(it.getString("at")), it.getString("kind") == "solo", it.intOrNull("hold_s"), it.intOrNull("reaction"), it.getInt("pain") == 1, it.str("note"))
            },
            o.getJSONArray("feedback").map { Instant.parse(it.getString("at")) to it.getString("text") },
        )
    }
}

/** Practice on one's own, kept on the phone until Finish: what was said about each item, the one in front of the
 *  student ([at]), each item's stopwatch time ([heldMs], an hour at most), and since when the stopwatch has been
 *  running. Times are SystemClock.elapsedRealtime() milliseconds. [curriculum] is the sequence repeated, for its doses
 *  and cues. */
data class SoloRun(val startedAt: Long, val curriculum: String?, val said: List<ItemFeedback>, val heldMs: List<Long>, val at: Int = 0,
    val runningSince: Long? = null) {
    val current get() = said[at]

    /** The stopwatch stops at 60:00, as long as the server keeps. */
    fun held(now: Long) = (heldMs[at] + (runningSince?.let { now - it } ?: 0)).coerceAtMost(MAX_HOLD_MS)

    fun toggled(now: Long) = if (runningSince == null) copy(runningSince = now) else stopped(now)

    fun stopped(now: Long) = if (runningSince == null) this else copy(heldMs = heldMs.toMutableList().also { it[at] = held(now) }, runningSince = null)

    fun changed(f: ItemFeedback) = copy(said = said.toMutableList().also { it[at] = f })

    fun moved(to: Int, now: Long) = stopped(now).copy(at = to)

    /** What to send at Finish: each item with its stopwatch time, those with something timed or said. */
    fun entries() = said.mapIndexed { i, f -> f.copy(heldSeconds = (heldMs[i] / 1000).toInt()) }.filter { it.said }

    /** The same run with its times moved by [ms]: after the phone restarted, elapsedRealtime counts from the new start. */
    fun shifted(ms: Long) = copy(startedAt = startedAt + ms, runningSince = runningSince?.plus(ms))

    /** The run as the phone keeps it, every note as typed so far. */
    fun saved(): String = JSONObject().put("started_at", startedAt).put("curriculum", curriculum ?: JSONObject.NULL).put("at", at)
        .put("running_since", runningSince ?: JSONObject.NULL).put("held_ms", JSONArray(heldMs))
        .put("said", JSONArray(said.map { JSONObject().put("item", it.item).put("reaction", it.reaction ?: JSONObject.NULL).put("pain", it.pain).put("note", it.note) }))
        .toString()

    companion object {
        const val MAX_HOLD_MS = 3_600_000L

        fun start(items: List<String>, curriculum: String?, now: Long) =
            SoloRun(now, curriculum, items.map { ItemFeedback(it, null, false, "") }, items.map { 0L })

        /** A run [saved] wrote, or null if the text is not one. */
        fun restore(text: String): SoloRun? = try {
            val o = JSONObject(text)
            val said = o.getJSONArray("said").map { ItemFeedback(it.getString("item"), it.intOrNull("reaction"), it.optBoolean("pain"), it.text("note")) }
            val held = o.getJSONArray("held_ms").let { a -> List(a.length()) { a.getLong(it) } }
            SoloRun(o.getLong("started_at"), o.str("curriculum"), said, held, o.getInt("at"), if (o.isNull("running_since")) null else o.getLong("running_since"))
                .takeIf { said.isNotEmpty() && held.size == said.size && it.at in said.indices }
        } catch (e: JSONException) {
            null
        }
    }
}

/** The stopwatch's holds, in seconds: the latest and the longest. */
data class Holds(val recent: Int, val longest: Int)

data class ItemEntry(val at: Instant, val solo: Boolean, val heldSeconds: Int?, val reaction: Int?, val pain: Boolean, val note: String?)

/** How a class went, item by item, for the teacher (GET /teacher/sessions/{id}/practice). */
data class ClassReview(val curriculum: String?, val joined: Int, val answered: Int, val items: List<ItemReview>) {
    companion object {
        fun from(o: JSONObject) = ClassReview(
            o.str("curriculum"), o.getInt("joined"), o.getInt("answered"),
            o.getJSONArray("items").map { i ->
                ItemReview(
                    i.getString("item"), (0 until 4).map { i.getJSONArray("reactions").getInt(it) },
                    i.list("pain").map { it.str("name") to it.str("note") },
                    i.list("notes").map { it.str("name") to it.text("text") },
                )
            },
        )
    }
}

/** One item of a class review: how many said each reaction (not yet … at ease), who felt strain or pain, the notes. A
 *  name is null for a student no longer in the Sheet. */
data class ItemReview(val item: String, val reactions: List<Int>, val pain: List<Pair<String?, String?>>, val notes: List<Pair<String?, String>>)

data class Studio(val tagline: String, val teacherName: String, val teacherTitle: String, val teacherBio: String) {
    companion object {
        fun from(o: JSONObject): Studio {
            val t = o.optJSONObject("teacher") ?: JSONObject()
            return Studio(o.text("tagline"), t.text("name"), t.text("title"), t.text("bio"))
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

/** [batch]: the student's batch, once placed; [sessions]: its coming classes. [afterClass]: the class whose after-class
 *  window is open, whether or not the student checked in to it (its `checkedIn`); [afterSaid]: what the student said
 *  about it, if anything. */
data class Home(val user: User, val batch: BatchInfo?, val studio: Studio, val sessions: List<ClassSession>, val afterClass: ClassSession?,
    val afterSaid: Said?, val groupLink: String?) {
    /** This home as it is once the student has checked in to [sessionId], or not. */
    fun checkedIn(sessionId: Int, yes: Boolean) = copy(sessions = sessions.map { if (it.id == sessionId) it.copy(checkedIn = yes) else it })

    companion object {
        fun from(o: JSONObject): Home {
            // after_class may be a class the student did not check in to; a server without it gives after_checkin alone.
            val any = o.has("after_class")
            val after = o.optJSONObject(if (any) "after_class" else "after_checkin")
            return Home(
                User.from(o.getJSONObject("user")), o.optJSONObject("batch")?.let(BatchInfo::from),
                Studio.from(o.getJSONObject("studio")), o.list("sessions").map(ClassSession::from),
                after?.let(ClassSession::from)?.let { if (any) it else it.copy(checkedIn = true) },
                after?.optJSONObject("said")?.let(Said::from), o.str("group_link"),
            )
        }
    }
}

/** What a student said after a class: the mood, if given, and each item's answer. */
data class Said(val mood: Int?, val items: List<ItemFeedback>) {
    companion object {
        fun from(o: JSONObject) = Said(o.intOrNull("mood"), o.list("items").map {
            ItemFeedback(it.text("item"), it.intOrNull("reaction"), it.intOrNull("pain") == 1, it.text("note"))
        })
    }
}

data class Stats(val classesJoined: Int, val streakDays: Int, val moodChange: Double?) {
    companion object {
        fun from(o: JSONObject) = Stats(o.getInt("classes_joined"), o.getInt("streak_days"), o.dbl("mood_change"))
    }
}

/** A class the student joined, from GET /me/practice: when, its name, and the moods (1 to 5). No mood before when the
 *  student said how it went without checking in first. */
data class JoinedClass(val at: Instant, val name: String, val curriculum: String?, val moodBefore: Int?, val moodAfter: Int?) {
    companion object {
        fun from(o: JSONObject) =
            JoinedClass(Instant.parse(o.getString("at")), o.text("class"), o.str("curriculum"), o.intOrNull("mood_before"), o.intOrNull("mood_after"))
    }
}

/** A session of practice on one's own (GET /me/practice): when it began, how long, and its items' names. */
data class SoloSession(val at: Instant, val minutes: Int, val items: List<String>) {
    companion object {
        fun from(o: JSONObject) = SoloSession(Instant.parse(o.getString("at")), o.getInt("minutes"), o.getJSONArray("items").let { a -> List(a.length()) { a.getString(it) } })
    }
}

/** The class group's link, if the teacher gave one, and the group code (null if the owner cleared it in the Sheet). */
data class TeacherSettings(val groupLink: String?, val groupCode: String?)

/** A batch with its everyday Meet link, for its classes without their own. */
data class BatchLink(val info: BatchInfo, val meetLink: String?)

data class TeacherHome(val sessions: List<ClassSession>, val batches: List<BatchLink>, val settings: TeacherSettings, val pendingStudents: Int) {
    fun batch(key: String?) = batches.firstOrNull { it.info.key == key }

    companion object {
        fun from(o: JSONObject): TeacherHome {
            val s = o.optJSONObject("settings") ?: JSONObject()
            return TeacherHome(
                o.list("sessions").map(ClassSession::from),
                o.list("batches").map { BatchLink(BatchInfo.from(it), it.str("meet_link")) },
                TeacherSettings(s.str("group_link"), s.str("group_code")),
                o.optInt("pending_students"),
            )
        }
    }
}

data class Student(val user: User, val joined: Int, val intake: Intake?) {
    companion object {
        fun from(o: JSONObject) = Student(User.from(o), o.optInt("joined"), o.optJSONObject("intake")?.let(Intake::from))
    }
}

/** A student's answers about themselves, for the teacher to place them in a batch ([suggestedBatch], from the server). */
data class Intake(val age: Int, val heightCm: Int, val weightKg: Int, val food: String, val meals: String?, val pain: List<String>, val painNote: String?,
    val ratings: List<IntakeRating>, val suggestedBatch: String?) {
    fun json(): JSONObject = JSONObject().put("age", age).put("height_cm", heightCm).put("weight_kg", weightKg).put("food", food)
        .put("meals", meals ?: JSONObject.NULL).put("pain", pain.joinToString(", ").ifEmpty { null } ?: JSONObject.NULL)
        .put("pain_note", painNote ?: JSONObject.NULL)
        .put("ratings", JSONArray(ratings.map { JSONObject().put("item", it.item).put("reaction", it.reaction ?: JSONObject.NULL).put("pain", if (it.pain) 1 else 0) }))

    companion object {
        fun from(o: JSONObject) = Intake(
            o.optInt("age"), o.optInt("height_cm"), o.optInt("weight_kg"), o.text("food"), o.str("meals"), o.list("pain").strings(),
            o.str("pain_note"), o.list("ratings").map { IntakeRating(it.text("item"), it.intOrNull("reaction"), it.intOrNull("pain") == 1) },
            o.str("suggested_batch"),
        )
    }
}

/** How one assessment asana went in the intake: 1 (not yet) to 4 (at ease), and strain or pain. */
data class IntakeRating(val item: String, val reaction: Int?, val pain: Boolean)

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
                SessionInsight(it.getInt("id"), Instant.parse(it.getString("starts_at")), it.text("class"), it.optInt("joined"), it.dbl("mood_before"), it.dbl("mood_after"))
            },
            o.list("feedback").map { Feedback(it.text("name"), it.text("text")) },
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
        fun from(o: JSONObject) = SharedNote(o.text("name"), o.text("text"), Instant.parse(o.getString("created_at")))
    }
}
