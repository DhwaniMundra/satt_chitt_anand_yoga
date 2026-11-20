package com.sattchittanand.yoga

import android.app.Application
import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.time.Instant
import java.util.UUID

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
    var soloSessions by mutableStateOf<List<SoloSession>>(emptyList()); private set
    private var soloRun by mutableStateOf(restoredSolo())
    /** Practice on one's own in progress; the screen changes it as the student goes, and [finishSolo] sends it. Kept on
     *  the phone at each change, so it outlasts Android closing the app. */
    var solo: SoloRun?
        get() = soloRun
        set(value) {
            soloRun = value
            prefs.solo = value?.let { JSONObject().put("boot", bootedAt()).put("run", it.saved()).toString() }
        }
    var teacherHome by mutableStateOf<TeacherHome?>(null); private set
    var students by mutableStateOf<List<Student>>(emptyList()); private set
    var insights by mutableStateOf<Insights?>(null); private set
    /** The studio's library and curricula, in the chosen language. */
    var curricula by mutableStateOf<Curricula?>(null); private set
    /** For the teacher: how one class went, item by item. */
    var review by mutableStateOf<ClassReview?>(null); private set
    /** A student's practice per item (the student's own, or the one the teacher opened), and one item's history. */
    var items by mutableStateOf<List<ItemSummary>>(emptyList()); private set
    var itemHistory by mutableStateOf<ItemHistory?>(null); private set
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
    /** Signed in on this phone (a saved token), whether or not the studio could be reached yet. */
    var signedIn by mutableStateOf(prefs.token != null); private set
    /** A new student: the intake opens before anything else. */
    var askIntake by mutableStateOf(false)
    /** How many notes students have shared in all; the list holds the newest. */
    var sharedCount by mutableStateOf(0); private set
    /** When everything was last read from the server (elapsedRealtime), so coming back to the app soon after reads
     *  nothing again. */
    private var refreshedAt = 0L
    /** Check-ins sent in the background that the server has not confirmed: kept on the phone, shown as done on the
     *  Today tab, and sent again at each start and return to the app until they land. */
    private var pending = PendingCheckin.restore(prefs.checkins).filter { it.token == prefs.token }
        set(value) {
            field = value
            prefs.checkins = PendingCheckin.saved(value)
        }
    private val sending = mutableSetOf<Int>()
    /** Check-ins the server has confirmed, by class, kept shown as done until the class ends (its end, as a moment). */
    private val confirmed = mutableMapOf<Int, Instant>()
    /** Why the server refused a check-in sent in the background, until the student has read it: apart from [error],
     *  which every call clears. */
    var checkInError by mutableStateOf<String?>(null)

    /** The calls of this sign-in, cancelled when signing out, so no reply for the account left lands on the next. */
    private var signedInScope = newSignedInScope()

    private fun newSignedInScope() = CoroutineScope(viewModelScope.coroutineContext + SupervisorJob(viewModelScope.coroutineContext[Job]))

    init {
        if (prefs.token == null) loadStudio() else launchCall { refreshAll() }
    }

    private fun launchCall(block: suspend () -> Unit) {
        signedInScope.launch {
            busy = true
            error = null
            try {
                block()
            } catch (e: ApiError) {
                failed(e)
            } catch (e: JSONException) { // a reply missing a field the app expects
                error = "generic"
            } finally {
                busy = false
                starting = false
            }
        }
    }

    private fun failed(e: ApiError) {
        when (e.code) {
            "signed_out" -> signOutLocally()
            "other_batch" -> { error = e.code; refreshHome() } // moved to another batch since the Today tab was read
            else -> error = e.code
        }
    }

    // A write that creates something carries one request id per action on its target (a student's batch, an item's
    // feedback), kept until the action goes through, so a retry of it (after a timeout, say) is written once. When any
    // action on the target goes through, every id kept for it goes, so a later action, even the same one, is new.
    private val requestIds = mutableMapOf<String, String>()

    private suspend fun <T> once(target: String, action: String, send: suspend (String) -> T): T {
        val reply = send(requestIds.getOrPut("$target|$action") { UUID.randomUUID().toString() })
        requestIds.keys.removeAll { it.startsWith("$target|") }
        return reply
    }

    private fun loadStudio() = launchCall { studio = Studio.from(api.get("/studio?lang=${prefs.lang}")) }

    /** The studio's own words (its blessing, the meaning of its name, its headings), in the chosen language. */
    fun words() = StudioWords.from(studioFile, prefs.lang)

    /** The intake's assessment asanas and how to try each safely, in the chosen language, from the studio content. */
    fun assessment(): List<Pair<String, String>> = studioFile.getJSONObject("intake").getJSONArray("assessment")
        .map { a -> a.getString("item") to a.getJSONObject("how").let { it.optString(prefs.lang).ifEmpty { it.getString("en") } } }

    /** Who is signed in, then their day, then the curricula: the day comes before the curricula, so it shows even if
     *  the curricula cannot be read. */
    private suspend fun refreshAll() {
        val me = api.get("/me")
        val account = User.from(me.getJSONObject("user"))
        if (user?.id != account.id) openStore(account)
        user = account
        stats = Stats.from(me.getJSONObject("stats"))
        if (account.isTeacher) readTeacherHome() else readHome()
        if (curricula == null) curricula = Curricula.from(api.get("/curricula?lang=${prefs.lang}"))
        refreshedAt = SystemClock.elapsedRealtime()
    }

    fun refresh() = launchCall { refreshAll() }

    /** The student's Today tab from the server, with the check-ins made on this phone shown as done: those it has not
     *  confirmed yet, and those it has, until their class ends, in case the reply was read before the check-in. */
    private suspend fun readHome() {
        val now = Instant.now()
        confirmed.values.removeAll { it < now }
        val done = pending.map { it.sessionId } + confirmed.keys
        home = done.fold(Home.from(api.get("/home?lang=${prefs.lang}"))) { h, id -> h.checkedIn(id, true) }
    }

    /** The student's Today tab read again in one call, quietly (no spinner, no error shown): while a class is near, or
     *  after the server said the student is now in another batch. */
    fun refreshHome() {
        if (user?.isTeacher != false) return
        signedInScope.launch {
            try {
                readHome()
            } catch (_: ApiError) {
            } catch (_: JSONException) {
            }
        }
    }

    // ---------- account ----------

    fun login(phone: String, password: String) = launchCall {
        val reply = api.post("/auth/login", JSONObject().put("phone", phone).put("password", password))
        prefs.token = reply.getString("token")
        signedIn = true
        refreshAll()
    }

    fun signup(name: String, phone: String, password: String, teacher: Boolean, code: String) {
        if (password.length < Limits.PASSWORD_MIN) {
            error = "short_password"
            return
        }
        launchCall {
            val body = JSONObject().put("name", name).put("phone", phone).put("password", password)
                .put("role", if (teacher) "teacher" else "student").put("code", code).put("lang", prefs.lang)
            prefs.token = api.post("/auth/signup", body).getString("token")
            signedIn = true
            askIntake = !teacher
            refreshAll()
        }
    }

    /** A student's own new password, after the current one; this phone stays signed in. [done] runs once it is through. */
    fun changePassword(current: String, new: String, changed: String, done: () -> Unit) = launchCall {
        val body = JSONObject().put("current_password", current).put("new_password", new)
        try {
            // Not tried again by itself: a second try overlapping the first would find the current password changed.
            once("password", (current + "\n" + new).hashCode().toString()) { api.post("/me/password", body, it, retry = false) }
        } catch (e: ApiError) {
            throw if (e.code == "Not Found") ApiError("old_server") else e // no /me/password on this server
        }
        notice = changed
        done()
    }

    fun logout() {
        viewModelScope.launch {
            try { api.post("/auth/logout") } catch (_: ApiError) { }
            signOutLocally()
        }
    }

    private fun signOutLocally() {
        signedInScope.cancel()
        signedInScope = newSignedInScope()
        confirmed.clear()
        prefs.token = null
        signedIn = false
        askIntake = false
        user = null; home = null; stats = null; teacherHome = null; insights = null; review = null
        practice = emptyList(); soloSessions = emptyList(); solo = null; students = emptyList(); notes = emptyList(); sharedNotes = emptyList()
        items = emptyList(); itemHistory = null; intake = null; intakeRead = false; pending = emptyList(); checkInError = null
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
        curricula = null // its names and cues are in the language
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

    /** Sends feedback to the studio; [sent] runs only once it is through, so a failed send keeps the text. */
    fun sendFeedback(text: String, thanks: String, sent: () -> Unit) = launchCall {
        once("feedback", text) { api.post("/feedback", JSONObject().put("screen", "me").put("text", text), it) }
        notice = thanks
        sent()
    }

    // ---------- student ----------

    /** The mood before class. The Today tab shows the check-in at once and the student goes into class: it is kept on
     *  the phone, with this sign-in's token, and sent in the background ([sendCheckins]) until the server has it. */
    fun checkIn(sessionId: Int, mood: Int) {
        val token = prefs.token ?: return
        pending = pending.filter { it.sessionId != sessionId } + PendingCheckin(sessionId, mood, UUID.randomUUID().toString(), token)
        home = home?.checkedIn(sessionId, true)
        checkInError = null
        sendCheckins()
    }

    /** Sends each check-in the server has not confirmed, with its request id and the token it was made with: at once,
     *  at each start and return to the app, and every two minutes while the Today tab is open, until it lands. A clear
     *  refusal (a 4xx) drops it and undoes it on the Today tab; [checkInError] says why, except for one that came after
     *  its class (the class can still be said after it). Anything else (no connection, busy, a 5xx, a page that is no
     *  reply) keeps it for the next try. A reply that comes after signing out is ignored. */
    fun sendCheckins() {
        pending.filter { it.sessionId !in sending }.forEach { p ->
            sending += p.sessionId
            signedInScope.launch {
                try {
                    val reply = api.post("/sessions/${p.sessionId}/checkin", JSONObject().put("phase", "before").put("mood", p.mood), p.requestId,
                        token = p.token)
                    if (prefs.token != p.token) return@launch
                    pending = pending - p
                    confirmed[p.sessionId] = classOf(p.sessionId)?.endsAt ?: Instant.now()
                    stats = Stats.from(reply.getJSONObject("stats"))
                } catch (e: ApiError) {
                    if (prefs.token != p.token || e.status !in 400..499) return@launch
                    pending = pending - p
                    if (pending.none { it.sessionId == p.sessionId }) home = home?.checkedIn(p.sessionId, false)
                    when (e.code) {
                        "signed_out" -> signOutLocally()
                        "checkin_closed" -> if (classOf(p.sessionId)?.let { Instant.now() < it.endsAt } == true) checkInError = e.code
                        "no_session" -> refreshHome()
                        "other_batch" -> { checkInError = e.code; refreshHome() }
                        else -> checkInError = e.code
                    }
                } catch (_: JSONException) {
                    pending = pending - p
                } finally {
                    sending -= p.sessionId
                }
                if (pending.any { it.sessionId == p.sessionId && it != p }) sendCheckins() // a new mood picked meanwhile
            }
        }
    }

    /** A class on the Today tab, coming or to say how it went. */
    private fun classOf(sessionId: Int) = home?.let { h -> h.sessions.firstOrNull { it.id == sessionId } ?: h.afterClass?.takeIf { it.id == sessionId } }

    fun loadPractice() = launchCall { readPractice() }

    /** The last two weeks: the classes joined and the practice on one's own, newest first. */
    private suspend fun readPractice() {
        val summary = api.get("/me/practice?days=14&lang=${prefs.lang}")
        practice = summary.getJSONArray("classes").map(JoinedClass::from).reversed()
        soloSessions = summary.getJSONArray("solo").map(SoloSession::from).reversed()
    }

    /** Sends the practice on one's own, if anything was timed or said, and closes it, with one request id per run. If
     *  the server refuses it, it stays open to change and send again. If the outcome is unknown (no connection, busy,
     *  a 5xx), the run is [SoloRun.unsure]: it can only be sent again as it is, or left, so the same id stays right. */
    fun finishSolo(saved: String) = launchCall {
        val now = SystemClock.elapsedRealtime()
        val run = solo?.let { if (it.unsure) it else it.stopped(now) } ?: return@launchCall
        solo = run
        val entries = run.entries()
        if (entries.isNotEmpty()) {
            // Whole minutes, rounded up; for a run sent again as it is, the length sent the first time.
            val minutes = run.sentMinutes ?: ((now - run.startedAt + 59_999) / 60000).toInt().coerceIn(1, 240)
            val body = JSONObject().put("minutes", minutes).put("entries", JSONArray(entries.map { it.json() }))
            try {
                once("solo:${run.startedAt}", "") { api.post("/me/solo", body, it) }
            } catch (e: ApiError) {
                if (e.status !in 400..499) solo = run.copy(unsure = true, sentMinutes = minutes)
                throw e
            }
            notice = saved
        }
        solo = null
        readPractice()
        readItems(null)
    }

    /** The run kept on the phone, if any. Its times count from the phone's start: after a restart they are moved by the
     *  difference between the two starts. */
    private fun restoredSolo(): SoloRun? {
        val kept = prefs.solo?.takeIf { prefs.token != null } ?: return null
        return try {
            val o = JSONObject(kept)
            SoloRun.restore(o.getString("run"))?.let { run ->
                val moved = o.getLong("boot") - bootedAt()
                if (kotlin.math.abs(moved) > 60_000) run.shifted(moved) else run
            }
        } catch (e: JSONException) {
            null
        }
    }

    /** When the phone started, on the wall clock. */
    private fun bootedAt() = System.currentTimeMillis() - SystemClock.elapsedRealtime()

    /** After class: the mood, if picked, and how each item went, if anything was said; [changing] what was said before. */
    fun sendAfterClass(sessionId: Int, mood: Int?, items: List<ItemFeedback>, changing: Boolean, done: () -> Unit) = launchCall {
        try {
            if (mood != null) {
                stats = Stats.from(api.post("/sessions/$sessionId/checkin", JSONObject().put("phase", "after").put("mood", mood)).getJSONObject("stats"))
            }
            val said = items.filter { it.said }
            // Changing what was said replaces all of it, even with nothing, so an item cleared is cleared on the server too.
            if (said.isNotEmpty() || changing) api.post("/sessions/$sessionId/practice", JSONObject().put("entries", JSONArray(said.map { it.json() })))
        } catch (e: ApiError) {
            throw if (e.code == "checkin_closed") ApiError("after_closed") else e
        }
        readHome()
        done()
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
            val answer = companion.answer(account, kept, line.text, prefs.lang, history, home?.batch?.name)
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

    private suspend fun readTeacherHome() {
        teacherHome = TeacherHome.from(api.get("/teacher/home?lang=${prefs.lang}"))
    }

    /** Saves one class's own link; [done] runs once it is saved and the classes read again. Then [share], if given,
     *  gets the class's message for the share sheet; if not, the snackbar says [saved]. */
    fun saveLink(sessionId: Int, link: String, saved: String, done: () -> Unit, share: ((String) -> Unit)?) = launchCall {
        val reply = api.put("/teacher/sessions/$sessionId?lang=${prefs.lang}", JSONObject().put("meet_link", link))
        readTeacherHome()
        done()
        if (share != null) share(reply.getString("text")) else notice = saved
    }

    fun shareSession(sessionId: Int, share: (String) -> Unit) = launchCall {
        share(api.get("/teacher/sessions/$sessionId/share?lang=${prefs.lang}").getString("text"))
    }

    /** Saves the links the teacher changed, each on its own, so one refused leaves the others saved: the class group's
     *  ([group], null when unchanged; empty removes it) and each batch's everyday Meet link ([links], by batch key;
     *  empty removes it). [done] gets the fields saved (the group's as [GROUP_FIELD]) and those refused, each with the
     *  reason, to show beside it. */
    fun saveLinks(group: String?, links: Map<String, String>, saved: String, done: (Set<String>, Map<String, String>) -> Unit) = launchCall {
        val sends = listOfNotNull(group?.let { g -> GROUP_FIELD to suspend { api.put("/teacher/settings", JSONObject().put("group_link", g)) } }) +
            links.map { (key, link) -> key to suspend { api.put("/teacher/batches/$key", JSONObject().put("meet_link", link)) } }
        val ok = mutableSetOf<String>()
        val refused = mutableMapOf<String, String>()
        var failure: ApiError? = null
        for ((field, send) in sends) {
            try {
                send()
                ok += field
            } catch (e: ApiError) {
                if (e.code in FIELD_ERRORS || e.code.startsWith("too_long:")) refused[field] = e.code else failure = e
            }
            if (failure != null) break
        }
        if (ok.isNotEmpty()) readTeacherHome()
        done(ok, refused)
        failure?.let { throw it }
        if (refused.isEmpty() && ok.isNotEmpty()) notice = saved
    }

    fun newGroupCode() = launchCall {
        api.post("/teacher/group_code")
        readTeacherHome()
    }

    fun shareInvite(share: (String) -> Unit) = launchCall {
        share(api.get("/teacher/invite?lang=${prefs.lang}").getString("text"))
    }

    fun loadStudents() = launchCall {
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
        loadSharedNotes()
    }

    private suspend fun loadSharedNotes() {
        val shared = api.get("/teacher/shared")
        sharedNotes = shared.getJSONArray("shared").map(SharedNote::from)
        sharedCount = shared.getInt("count")
    }

    /** The student's own intake, read when its screen opens ([intakeRead] then true; [intake] null if never filled). */
    var intake by mutableStateOf<Intake?>(null); private set
    var intakeRead by mutableStateOf(false); private set

    fun loadIntake() = launchCall {
        val o = api.get("/me/intake")
        intake = if (o.isNull("intake")) null else Intake.from(o.getJSONObject("intake"))
        intakeRead = true
    }

    fun saveIntake(answers: Intake, thanks: String, done: () -> Unit) = launchCall {
        intake = Intake.from(api.put("/me/intake", answers.json()).getJSONObject("intake"))
        notice = thanks
        done()
    }

    /** Places a student in a batch: approving a new one, or moving one after a review, with the teacher's note. [done]
     *  runs once it is saved, so a move that fails keeps the picker and the note. */
    fun placeStudent(userId: Int, batch: String, note: String, done: () -> Unit) = launchCall {
        val body = JSONObject().put("batch", batch).put("note", note.trim().ifEmpty { null } ?: JSONObject.NULL)
        once("move:$userId", "$batch:${note.trim()}") { api.put("/teacher/students/$userId/batch", body, it) }
        done()
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
        readTeacherHome()
    }

    fun setStudentStatus(userId: Int, status: String) = launchCall {
        api.post("/teacher/students/$userId/status", JSONObject().put("status", status))
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
        readTeacherHome()
    }

    /** A new password for a student. Not tried again by itself, so two can never overlap; the teacher's own retry after
     *  a lost reply sends the same request id and gets the same password back. */
    fun resetPassword(userId: Int, show: (String) -> Unit) = launchCall {
        show(once("reset:$userId", "") { api.post("/teacher/students/$userId/password", JSONObject(), it, retry = false) }.getString("password"))
    }

    fun setCurriculum(sessionId: Int, curriculum: String) = launchCall {
        api.put("/teacher/sessions/$sessionId/curriculum", JSONObject().put("curriculum", curriculum))
        readTeacherHome()
    }

    /** Where a student's practice per item is read: the student's own, or [studentId]'s for the teacher. */
    private fun itemsPath(studentId: Int?) = if (studentId == null) "/me/asanas" else "/teacher/students/$studentId/asanas"

    fun loadItems(studentId: Int? = null) = launchCall {
        items = emptyList() // not the last student's list while this one loads
        readItems(studentId)
    }

    private suspend fun readItems(studentId: Int?) {
        items = api.get(itemsPath(studentId)).getJSONArray("items").map(ItemSummary::from)
    }

    fun loadItem(item: String, studentId: Int? = null) = launchCall {
        itemHistory = null
        itemHistory = ItemHistory.from(api.get(itemsPath(studentId) + "/$item"))
    }

    /** The teacher's feedback on one student's item; [done] runs only once it is through, so a failed send keeps the text. */
    fun sendItemFeedback(studentId: Int, item: String, text: String, sent: String, done: () -> Unit) = launchCall {
        val body = JSONObject().put("item", item).put("text", text)
        once("item-feedback:$studentId:$item", text) { api.post("/teacher/students/$studentId/feedback", body, it) }
        itemHistory = ItemHistory.from(api.get(itemsPath(studentId) + "/$item"))
        notice = sent
        done()
    }

    fun loadReview(sessionId: Int) = launchCall {
        review = null
        review = ClassReview.from(api.get("/teacher/sessions/$sessionId/practice?lang=${prefs.lang}"))
    }

    fun loadInsights() = launchCall {
        insights = Insights.from(api.get("/teacher/insights?lang=${prefs.lang}"))
        loadSharedNotes() // the "Notes shared" tile
    }

    /** Coming back to the app (from Meet, say) sends the check-ins still waiting, and reloads, so the after-class
     *  question appears when it is due; it reloads not again within half a minute (a rotation, a glance at another
     *  app). */
    fun onResume() {
        val stale = SystemClock.elapsedRealtime() - refreshedAt > RESUME_REFRESH_MS
        if (signedIn) sendCheckins()
        if (signedIn && !busy && stale) refresh() // signed in, or signed in but the studio was out of reach: try again
        gemma.refresh(loadModel = false) // a download that went on, or finished, while the app was away
    }

    companion object {
        /** The class group's link, among the fields [saveLinks] saves. */
        const val GROUP_FIELD = "group_link"
        /** Errors that belong to one field and are shown beside it. */
        val FIELD_ERRORS = setOf("bad_meet_link", "bad_group_link")
        private const val RESUME_REFRESH_MS = 30_000L
    }
}
