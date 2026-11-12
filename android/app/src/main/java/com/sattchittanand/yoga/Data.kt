package com.sattchittanand.yoga

import android.content.Context
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.time.Instant

/** What the app keeps on the phone: the login token, the server address and the chosen language. */
class Prefs(context: Context) {
    private val store = context.getSharedPreferences("sca", Context.MODE_PRIVATE)

    var token: String?
        get() = store.getString("token", null)
        set(value) = store.edit().putString("token", value).apply()

    var server: String
        get() = store.getString("server", null) ?: BuildConfig.DEFAULT_SERVER
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

/** JSON over HTTP to the backend, with the platform's own HttpURLConnection. */
class Api(private val prefs: Prefs) {

    suspend fun get(path: String) = call("GET", path, null)
    suspend fun post(path: String, body: JSONObject = JSONObject()) = call("POST", path, body)
    suspend fun put(path: String, body: JSONObject) = call("PUT", path, body)

    private suspend fun call(method: String, path: String, body: JSONObject?): JSONObject = withContext(Dispatchers.IO) {
        try {
            val conn = URL(prefs.server + path).openConnection() as HttpURLConnection
            conn.requestMethod = method
            conn.connectTimeout = 8_000
            conn.readTimeout = 120_000 // the assistant can take a while on a busy laptop
            prefs.token?.let { conn.setRequestProperty("Authorization", "Bearer $it") }
            if (body != null) {
                conn.doOutput = true
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
                conn.outputStream.use { it.write(body.toString().toByteArray()) }
            }
            val ok = conn.responseCode in 200..299
            val text = (if (ok) conn.inputStream else conn.errorStream)?.bufferedReader()?.use { it.readText() } ?: "{}"
            val json = JSONObject(text)
            if (!ok) throw ApiError(json.optString("detail").takeIf { it.isNotEmpty() && !it.startsWith("[") } ?: "generic")
            json
        } catch (e: IOException) {
            throw ApiError("network")
        }
    }
}

// ---------- models, parsed from the server's JSON ----------

fun JSONObject.str(key: String): String? = if (isNull(key)) null else getString(key)
fun JSONObject.dbl(key: String): Double? = if (isNull(key)) null else getDouble(key)
fun <T> JSONArray.map(transform: (JSONObject) -> T): List<T> = (0 until length()).map { transform(getJSONObject(it)) }

data class User(val id: Int, val name: String, val phone: String, val role: String, val status: String, val lang: String, val researchConsent: Boolean) {
    val isTeacher get() = role == "teacher"
    val isApproved get() = status == "approved"

    companion object {
        fun from(o: JSONObject) = User(
            o.getInt("id"), o.getString("name"), o.getString("phone"), o.getString("role"), o.getString("status"),
            o.getString("lang"), o.getBoolean("research_consent"),
        )
    }
}

data class ClassInfo(val key: String, val name: String, val level: String, val about: String) {
    companion object {
        fun from(o: JSONObject) = ClassInfo(o.getString("key"), o.getString("name"), o.getString("level"), o.getString("about"))
    }
}

data class ClassSession(
    val id: Int,
    val startsAt: Instant,
    val minutes: Int,
    val info: ClassInfo,
    val meetLink: String?,
    val hasLink: Boolean,
    val checkedIn: Boolean,
    val ownLink: Boolean,
    val joined: Int,
) {
    val endsAt: Instant get() = startsAt.plusSeconds(minutes * 60L)

    companion object {
        fun from(o: JSONObject) = ClassSession(
            o.getInt("id"), Instant.parse(o.getString("starts_at")), o.getInt("duration_min"), ClassInfo.from(o.getJSONObject("class")),
            o.str("meet_link"), o.getBoolean("has_link"), o.optBoolean("checked_in"), o.optBoolean("own_link"), o.optInt("joined"),
        )
    }
}

data class Studio(val name: String, val tagline: String, val since: Int, val teacherName: String, val teacherTitle: String, val teacherBio: String, val weekly: List<Pair<String, ClassInfo>>) {
    companion object {
        fun from(o: JSONObject): Studio {
            val t = o.getJSONObject("teacher")
            val weekly = o.getJSONArray("weekly").map { it.getString("day") to ClassInfo.from(it.getJSONObject("class")) }
            return Studio(o.getString("name"), o.getString("tagline"), o.getInt("since"), t.getString("name"), t.getString("title"), t.getString("bio"), weekly)
        }
    }
}

data class Home(val user: User, val studio: Studio, val sessions: List<ClassSession>, val afterCheckin: ClassSession?, val groupLink: String?) {
    companion object {
        fun from(o: JSONObject) = Home(
            User.from(o.getJSONObject("user")), Studio.from(o.getJSONObject("studio")), o.getJSONArray("sessions").map(ClassSession::from),
            if (o.isNull("after_checkin")) null else ClassSession.from(o.getJSONObject("after_checkin")), o.str("group_link"),
        )
    }
}

data class Stats(val classesJoined: Int, val streakDays: Int, val moodChange: Double?, val moodPairs: Int) {
    companion object {
        fun from(o: JSONObject) = Stats(o.getInt("classes_joined"), o.getInt("streak_days"), o.dbl("mood_change"), o.getInt("mood_pairs"))
    }
}

data class TeacherSettings(val groupLink: String?, val groupCode: String, val defaultMeetLink: String?)

data class TeacherHome(val sessions: List<ClassSession>, val settings: TeacherSettings, val pendingStudents: Int) {
    companion object {
        fun from(o: JSONObject): TeacherHome {
            val s = o.getJSONObject("settings")
            return TeacherHome(
                o.getJSONArray("sessions").map(ClassSession::from),
                TeacherSettings(s.str("group_link"), s.getString("group_code"), s.str("default_meet_link")),
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

data class SessionInsight(val startsAt: Instant, val className: String, val joined: Int, val moodBefore: Double?, val moodAfter: Double?)
data class Feedback(val name: String, val screen: String, val text: String)

data class Insights(
    val approved: Int,
    val pending: Int,
    val moodChange: Double?,
    val moodPairs: Int,
    val questions: Int,
    val sessions: List<SessionInsight>,
    val feedback: List<Feedback>,
) {
    companion object {
        fun from(o: JSONObject): Insights {
            val students = o.getJSONObject("students")
            return Insights(
                students.getInt("approved"), students.getInt("pending"), o.dbl("mood_change"), o.getInt("mood_pairs"),
                o.getJSONObject("questions").getInt("count"),
                o.getJSONArray("sessions").map {
                    SessionInsight(Instant.parse(it.getString("starts_at")), it.getString("class"), it.getInt("joined"), it.dbl("mood_before"), it.dbl("mood_after"))
                },
                o.getJSONArray("feedback").map { Feedback(it.getString("name"), it.getString("screen"), it.getString("text")) },
            )
        }
    }
}

/** One line in the Ask conversation. `mode` is "gemma", "notes" or "urgent" for answers, null for the student's own. */
data class ChatLine(val text: String, val fromStudent: Boolean, val mode: String? = null, val sources: List<String> = emptyList())
