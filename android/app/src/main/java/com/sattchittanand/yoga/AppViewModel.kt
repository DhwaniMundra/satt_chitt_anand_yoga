package com.sattchittanand.yoga

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.launch
import org.json.JSONException
import org.json.JSONObject
import java.time.LocalDate
import java.time.ZoneId

/** All screen state, and every call to the server. Errors land in [error] as the server's code. */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private val api = Api(prefs)
    private val studioFile = JSONObject(app.assets.open("studio/studio.json").bufferedReader().use { it.readText() })
    private val companion = PhoneCompanion(app, api, studioFile)
    /** Where Gemma on this phone stands (too little memory, downloading, loading, ready…). */
    val gemma = companion.gemma
    /** The signed-in student's chat and health notes, kept on this phone. */
    private var store: LocalStore? = null

    var starting by mutableStateOf(true); private set
    /** For the first screen, before signing in. */
    var studio by mutableStateOf<Studio?>(null); private set
    var user by mutableStateOf<User?>(null); private set
    var home by mutableStateOf<Home?>(null); private set
    var stats by mutableStateOf<Stats?>(null); private set
    /** The classes the student joined in the last two weeks, newest first. */
    var practice by mutableStateOf<List<JoinedClass>>(emptyList()); private set
    var teacherHome by mutableStateOf<TeacherHome?>(null); private set
    var students by mutableStateOf<List<Student>>(emptyList()); private set
    var insights by mutableStateOf<Insights?>(null); private set
    /** The conversation with the practice companion, as kept on this phone. */
    val chat = mutableStateListOf<ChatLine>()
    var asking by mutableStateOf(false); private set
    var notes by mutableStateOf<List<Note>>(emptyList()); private set
    /** For the teacher: the notes students chose to share. */
    var sharedNotes by mutableStateOf<List<SharedNote>>(emptyList()); private set
    var busy by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null)
    /** A one-off message for a snackbar; the screen clears it once shown. */
    var notice by mutableStateOf<String?>(null)

    init {
        if (prefs.token == null) loadStudio() else launchCall { refreshAll() }
    }

    private fun launchCall(block: suspend () -> Unit) {
        viewModelScope.launch {
            busy = true
            error = null
            try {
                block()
            } catch (e: ApiError) {
                if (e.code == "signed_out") signOutLocally() else error = e.code
            } catch (e: JSONException) { // a reply missing a field the app expects
                error = "generic"
            } finally {
                busy = false
                starting = false
            }
        }
    }

    private fun loadStudio() = launchCall { studio = Studio.from(api.get("/studio?lang=${prefs.lang}")) }

    /** The studio's own words (its blessing, the meaning of its name, its headings), in the chosen language. */
    fun words() = StudioWords.from(studioFile, prefs.lang)

    private suspend fun refreshAll() {
        val me = api.get("/me")
        val account = User.from(me.getJSONObject("user"))
        if (user?.id != account.id) openStore(account)
        user = account
        stats = Stats.from(me.getJSONObject("stats"))
        if (account.isTeacher) {
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

    fun signup(name: String, phone: String, password: String, teacher: Boolean, code: String) {
        if (password.length < 6) {
            error = "short_password"
            return
        }
        launchCall {
            val body = JSONObject().put("name", name).put("phone", phone).put("password", password)
                .put("role", if (teacher) "teacher" else "student").put("code", code).put("lang", prefs.lang)
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
        practice = emptyList(); students = emptyList(); notes = emptyList(); sharedNotes = emptyList()
        chat.clear()
        store = null // the chat and notes stay on the phone, under this account, for its next sign-in
        loadStudio()
    }

    private fun openStore(account: User) {
        store = LocalStore(getApplication<Application>().filesDir, account.id).also {
            chat.clear()
            chat.addAll(it.chat())
            notes = it.notes()
        }
    }

    /** Saves the language on the phone (and on the server once signed in) and reloads what the server words in it.
     *  The activity then restarts in it. */
    fun setLanguage(lang: String) {
        prefs.lang = lang
        if (user == null) {
            loadStudio()
        } else {
            viewModelScope.launch { try { api.post("/me", JSONObject().put("lang", lang)) } catch (_: ApiError) { } }
            refresh()
        }
    }

    /** A debug build's server address, from the first screen. */
    fun saveServer(address: String) {
        prefs.server = address
        loadStudio()
    }

    fun enterGroupCode(code: String) = launchCall {
        api.post("/me/group_code", JSONObject().put("code", code))
        refreshAll()
    }

    fun sendFeedback(text: String, thanks: String) = launchCall {
        api.post("/feedback", JSONObject().put("screen", "me").put("text", text))
        notice = thanks
    }

    // ---------- student ----------

    fun checkin(sessionId: Int, phase: String, mood: Int, then: () -> Unit = {}) = launchCall {
        stats = Stats.from(api.post("/sessions/$sessionId/checkin", JSONObject().put("phase", phase).put("mood", mood)).getJSONObject("stats"))
        home = Home.from(api.get("/home?lang=${prefs.lang}"))
        then()
    }

    fun loadPractice() = launchCall {
        val today = LocalDate.now(ZoneId.of("Asia/Kolkata"))
        practice = api.get("/me/practice?days=14&lang=${prefs.lang}").getJSONArray("classes").map { JoinedClass.from(it, today) }.reversed()
    }

    /** Sends [question] to the companion on this phone: the student's line shows at once, the reply when it comes.
     *  Both are kept on the phone, never sent to the server. */
    fun ask(question: String) {
        val account = user ?: return
        val kept = store ?: return
        if (question.isBlank() || asking) return
        val history = chat.toList()
        val line = ChatLine(question.trim(), fromStudent = true)
        chat.add(line)
        kept.add(line)
        asking = true
        viewModelScope.launch {
            val answer = companion.answer(account, kept, line.text, prefs.lang, history)
            kept.add(answer)
            chat.add(answer)
            notes = kept.notes() // a tool, or the "Remember that…" rule, may have saved one
            asking = false
        }
    }

    fun clearChat() {
        if (asking) return
        store?.clearChat()
        chat.clear()
    }

    fun addNote(text: String) {
        val kept = store ?: return
        kept.addNote(text)
        notes = kept.notes()
    }

    /** Forgets a note on this phone. One already shared stays with the teacher, as the share dialog says. */
    fun forgetNote(note: Note) {
        val kept = store ?: return
        kept.forget(note.id)
        notes = kept.notes()
    }

    /** Sends this one note to the teacher: the only thing from the chat and the notes that leaves the phone. */
    fun shareNote(note: Note, done: String) = launchCall {
        val reply = api.post("/me/shared", JSONObject().put("text", note.text))
        store?.let {
            it.markShared(note.id, reply.getInt("id"))
            notes = it.notes()
        }
        notice = done
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

    fun saveSettings(groupLink: String, defaultMeetLink: String, saved: String) = launchCall {
        val body = JSONObject()
        if (groupLink.isNotBlank()) body.put("group_link", groupLink)
        if (defaultMeetLink.isNotBlank()) body.put("default_meet_link", defaultMeetLink)
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
        loadSharedNotes()
    }

    private suspend fun loadSharedNotes() {
        sharedNotes = api.get("/teacher/shared").getJSONArray("shared").map(SharedNote::from)
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
        loadSharedNotes() // the "Notes shared" tile
    }

    /** Coming back to the app (from Meet, say) reloads, so the after-class question appears when it is due. */
    fun onResume() {
        if (user != null && !busy) refresh()
        gemma.refresh(loadModel = false) // a download that went on, or finished, while the app was away
    }
}
