package com.sattchittanand.yoga

import android.app.Application
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.sattchittanand.yoga.companion.labels
import kotlinx.coroutines.launch
import org.json.JSONObject

/** All screen state, and every call to the server. Errors land in [error] as the server's code. */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private val api = Api(prefs)
    /** The companion on this phone; [gemma] is where its model stands (downloading, loading, ready…). */
    private val companion = PhoneCompanion(app, api)
    val gemma = companion.gemma
    /** The signed-in account's chat and notes, kept on this phone. */
    private var store: LocalStore? = null
    private var storeUser: Int? = null

    var starting by mutableStateOf(true); private set
    var user by mutableStateOf<User?>(null); private set
    var home by mutableStateOf<Home?>(null); private set
    var stats by mutableStateOf<Stats?>(null); private set
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
        openStore(user!!)
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
        students = emptyList(); notes = emptyList(); sharedNotes = emptyList()
        chat.clear()
        store = null // the chat and notes stay on the phone, under this account, for its next sign-in
        storeUser = null
    }

    /** This account's chat and notes on the phone. */
    private fun openStore(account: User) {
        if (storeUser == account.id) return
        storeUser = account.id
        store = LocalStore(getApplication<Application>().filesDir, account.id).also {
            chat.clear()
            chat.addAll(it.chat())
            notes = it.notes()
        }
    }

    /** Saves the language on the phone (and on the server once signed in). The activity then restarts in it. */
    fun setLanguage(lang: String) {
        prefs.lang = lang
        if (user != null) viewModelScope.launch { try { api.post("/me", JSONObject().put("lang", lang)) } catch (_: ApiError) { } }
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
            val reply = companion.answer(account, kept, line.text, prefs.lang, history)
            val answer = ChatLine(reply.text, fromStudent = false, tools = labels(reply.tools), mode = reply.mode)
            kept.add(answer)
            chat.add(answer)
            notes = kept.notes() // a tool, or the "Remember that…" rule, may have saved one
            asking = false
        }
    }

    /** The Ask tab opened: Gemma picks up where it was (a download, a check, a load). */
    fun openAsk() = gemma.refresh()

    fun downloadGemma() = gemma.download()
    fun cancelDownload() = gemma.cancel()
    fun useMobileData() = gemma.useMobileData()

    fun clearChat() {
        if (asking) return
        store?.clearChat()
        chat.clear()
    }

    fun loadNotes() {
        notes = store?.notes() ?: emptyList()
    }

    /** Forgets a note on this phone. One already shared stays with the teacher, as the share dialog says. */
    fun forgetNote(note: Note) {
        store?.forget(note.id)
        loadNotes()
    }

    /** Sends this one note to the teacher: the only thing from the companion that leaves the phone. */
    fun shareNote(note: Note, done: String) = launchCall {
        val reply = api.post("/me/shared", JSONObject().put("text", note.text))
        store?.markShared(note.id, reply.getInt("id"))
        loadNotes()
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

    fun saveServer(address: String) {
        prefs.server = address
        if (user != null || prefs.token != null) launchCall { refreshAll() }
    }

    /** Coming back to the app (from Meet, say) reloads, so the after-class question appears when it is due. */
    fun onResume() {
        if (user != null && !busy) refresh()
        gemma.refresh(loadModel = false) // a download that went on, or finished, while the app was away
    }
}
