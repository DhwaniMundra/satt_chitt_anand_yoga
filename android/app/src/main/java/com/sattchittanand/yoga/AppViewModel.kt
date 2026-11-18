package com.sattchittanand.yoga

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import org.json.JSONObject

/** All screen state, and every call to the server. Errors land in [error] as the server's code. */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private val api = Api(prefs)

    var starting by mutableStateOf(true); private set
    var user by mutableStateOf<User?>(null); private set
    var home by mutableStateOf<Home?>(null); private set
    var stats by mutableStateOf<Stats?>(null); private set
    var teacherHome by mutableStateOf<TeacherHome?>(null); private set
    var students by mutableStateOf<List<Student>>(emptyList()); private set
    var insights by mutableStateOf<Insights?>(null); private set
    val chat = mutableStateListOf<ChatLine>()
    var asking by mutableStateOf(false); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null)
    /** A one-off message for a snackbar; the screen clears it once shown. */
    var notice by mutableStateOf<String?>(null)

    init {
        if (prefs.token == null) starting = false else launchCall(onDone = { starting = false }) { refreshAll() }
    }

    private fun launchCall(onDone: () -> Unit = {}, block: suspend () -> Unit) {
        viewModelScope.launch {
            busy = true
            error = null
            try {
                block()
            } catch (e: ApiError) {
                if (e.code == "signed_out") signOutLocally() else error = e.code
            } catch (e: org.json.JSONException) { // a reply missing a field the app expects
                error = "generic"
            } finally {
                busy = false
                onDone()
            }
        }
    }

    private suspend fun refreshAll() {
        val me = api.get("/me")
        user = User.from(me.getJSONObject("user"))
        stats = Stats.from(me.getJSONObject("stats"))
        if (user!!.isTeacher) {
            teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
        } else {
            home = Home.from(api.get("/home?lang=${prefs.lang}"))
        }
    }

    fun refresh() = launchCall { refreshAll() }

    // ---------- account ----------

    fun login(phone: String, password: String) = launchCall {
        val reply = api.post("/auth/login", JSONObject().put("phone", phone).put("password", password))
        prefs.token = reply.getString("token")
        refreshAll()
    }

    fun signup(name: String, phone: String, password: String, teacher: Boolean, code: String, consent: Boolean) {
        if (password.length < 6) {
            error = "short_password"
            return
        }
        launchCall {
            val body = JSONObject().put("name", name).put("phone", phone).put("password", password)
                .put("role", if (teacher) "teacher" else "student").put("code", code).put("lang", prefs.lang)
                .put("research_consent", consent)
            prefs.token = api.post("/auth/signup", body).getString("token")
            refreshAll()
        }
    }

    fun logout() {
        viewModelScope.launch {
            try { api.post("/auth/logout") } catch (_: ApiError) { }
            signOutLocally()
        }
    }

    private fun signOutLocally() {
        prefs.token = null
        user = null; home = null; stats = null; teacherHome = null; insights = null
        students = emptyList()
        chat.clear()
    }

    /** Saves the language on the phone (and on the server once signed in). The activity then restarts in it. */
    fun setLanguage(lang: String) {
        prefs.lang = lang
        if (user != null) viewModelScope.launch { try { api.post("/me", JSONObject().put("lang", lang)) } catch (_: ApiError) { } }
    }

    fun setConsent(consent: Boolean) = launchCall {
        user = User.from(api.post("/me", JSONObject().put("research_consent", consent)).getJSONObject("user"))
    }

    fun enterGroupCode(code: String) = launchCall {
        api.post("/me/group_code", JSONObject().put("code", code))
        refreshAll()
    }

    fun sendFeedback(screen: String, text: String, thanks: String) = launchCall {
        api.post("/feedback", JSONObject().put("screen", screen).put("text", text))
        notice = thanks
    }

    // ---------- student ----------

    fun checkin(sessionId: Int, phase: String, mood: Int, then: () -> Unit = {}) = launchCall(onDone = then) {
        stats = Stats.from(api.post("/sessions/$sessionId/checkin", JSONObject().put("phase", phase).put("mood", mood)).getJSONObject("stats"))
        home = Home.from(api.get("/home?lang=${prefs.lang}"))
    }

    fun ask(question: String) {
        if (question.isBlank() || asking) return
        chat.add(ChatLine(question.trim(), fromStudent = true))
        asking = true
        viewModelScope.launch {
            try {
                val reply = api.post("/ask", JSONObject().put("question", question.trim()).put("lang", prefs.lang))
                val sources = reply.getJSONArray("sources").let { a -> (0 until a.length()).map { a.getString(it) } }
                chat.add(ChatLine(reply.getString("answer"), fromStudent = false, mode = reply.getString("mode"), sources = sources))
            } catch (e: ApiError) {
                error = e.code
            } catch (e: org.json.JSONException) {
                error = "generic"
            } finally {
                asking = false
            }
        }
    }

    // ---------- teacher ----------

    /** Saves the session's link and hands the WhatsApp message to [share]. */
    fun saveLinkAndShare(sessionId: Int, link: String, share: (String) -> Unit) = launchCall {
        val reply = api.put("/teacher/sessions/$sessionId?lang=${prefs.lang}", JSONObject().put("meet_link", link))
        teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
        share(reply.getString("text"))
    }

    fun shareSession(sessionId: Int, share: (String) -> Unit) = launchCall {
        share(api.get("/teacher/sessions/$sessionId/share?lang=${prefs.lang}").getString("text"))
    }

    fun saveSettings(groupLink: String?, defaultMeetLink: String?, saved: String) = launchCall {
        val body = JSONObject()
        if (!groupLink.isNullOrBlank()) body.put("group_link", groupLink)
        if (!defaultMeetLink.isNullOrBlank()) body.put("default_meet_link", defaultMeetLink)
        api.put("/teacher/settings", body)
        teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
        notice = saved
    }

    fun newGroupCode() = launchCall {
        api.post("/teacher/group_code")
        teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
    }

    fun shareInvite(share: (String) -> Unit) = launchCall {
        share(api.get("/teacher/invite?lang=${prefs.lang}").getString("text"))
    }

    fun loadStudents() = launchCall {
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
    }

    fun setStudentStatus(userId: Int, status: String) = launchCall {
        api.post("/teacher/students/$userId/status", JSONObject().put("status", status))
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
        teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
    }

    fun resetPassword(userId: Int, show: (String) -> Unit) = launchCall {
        show(api.post("/teacher/students/$userId/password").getString("password"))
    }

    fun loadInsights() = launchCall {
        insights = Insights.from(api.get("/teacher/insights"))
    }

    fun saveServer(address: String) {
        prefs.server = address
        if (user != null || prefs.token != null) launchCall { refreshAll() }
    }

    /** Coming back to the app (from Meet, say) reloads, so the after-class question appears when it is due. */
    fun onResume() {
        if (user != null && !busy) refresh()
    }
}
