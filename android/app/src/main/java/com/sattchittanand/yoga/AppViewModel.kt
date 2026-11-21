package com.sattchittanand.yoga

import android.app.Application
import android.os.SystemClock
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.time.Instant

/** All screen state, and every call to the server. Errors land in [error] as the server's code. */
class AppViewModel(app: Application) : AndroidViewModel(app) {
    val prefs = Prefs(app)
    private val api = Api({ prefs.token }, HttpExchange { prefs.server })
    private val accounts = Accounts(api, prefs)
    private val studioFile = JSONObject(app.assets.open("studio/studio.json").bufferedReader().use { it.readText() })
    private val companion = PhoneCompanion(app, api, studioFile)
    /** Where Gemma on this phone stands (too little memory, downloading, loading, ready…). */
    val gemma = companion.gemma
    /** The signed-in student's chat and health notes, kept on this phone. */
    private var store: LocalStore? = null
    /** What the first screens showed, kept on this phone for this sign-in, to open on at once. */
    private val saved = SavedScreens(File(app.filesDir, "saved_screens.json"))

    /** For the first screen, before signing in. */
    var studio by mutableStateOf<Studio?>(null); private set
    var user by mutableStateOf<User?>(null); private set
    var home by mutableStateOf<Home?>(null); private set
    var stats by mutableStateOf<Stats?>(null); private set
    /** The classes the student joined in the last two weeks, newest first. */
    var practice by mutableStateOf<List<JoinedClass>>(emptyList()); private set
    /** The practice on one's own of the last two weeks, newest first: those still waiting for the server, then the
     *  server's ([soloRead]). */
    var soloSessions by mutableStateOf<List<SoloSession>>(emptyList()); private set
    private var soloRead = emptyList<SoloSession>()
    private var soloRun by mutableStateOf(restoredRun(prefs.solo?.takeIf { prefs.token != null }))
    /** Practice on one's own in progress; the screen changes it as the student goes, and [finishSolo] sends it. Kept on
     *  the phone at each change, so it outlasts Android closing the app. */
    var solo: SoloRun?
        get() = soloRun
        set(value) {
            soloRun = value
            prefs.solo = value?.let(::keptRun)
        }
    var teacherHome by mutableStateOf<TeacherHome?>(null); private set
    var students by mutableStateOf<List<Student>>(emptyList()); private set
    var insights by mutableStateOf<Insights?>(null); private set
    /** The studio's library and curricula, in the chosen language: read once a start (shown till then as kept). */
    var curricula by mutableStateOf<Curricula?>(null); private set
    private var curriculaRead = false
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
    private var calls by mutableIntStateOf(0)
    /** A call to the server under way, for the screens' spinners. */
    val busy get() = calls > 0
    /** Logging in or signing up, until the first screen's data has come or the call has failed. */
    var signingIn by mutableStateOf(false); private set
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
    /** When the day the screens show was read from the server (epoch ms): this start's read, or the one kept. */
    private var readAt = 0L
    /** Reading the screens again behind what they show: a thin line at the top says so, and nothing moves. */
    var refreshing by mutableStateOf(false); private set
    /** The same, asked for by pulling the Today tab down, whose own spinner then shows it. */
    var pulling by mutableStateOf(false); private set
    /** The screens show what was read at this moment (epoch ms), as the studio could not be reached since: a calm line
     *  says so, with a way to try again. */
    var shownFrom by mutableStateOf<Long?>(null); private set
    /** Check-ins sent in the background that the server has not confirmed: kept on the phone, shown as done on the
     *  Today tab, and sent again at each start and return to the app until they land. */
    private var pending = PendingCheckin.restore(prefs.checkins).filter { it.token == prefs.token }
        set(value) {
            field = value
            prefs.checkins = PendingCheckin.saved(value)
        }
    private val sending = mutableSetOf<Int>()
    /** What was said after class and the practice on one's own, saved on the phone at once and sent in the background
     *  ([sendPending]) until the server has them; the screens show them as saved meanwhile. */
    private val outbox = Outbox(api, prefs).also { it.keepOnly(prefs.token) }
    private val sendingWrites = mutableSetOf<String>()
    /** The student's day as the server last gave it, before what this phone has sent or is sending is laid over it. */
    private var dayRead: Home? = null
    /** Check-ins the server has confirmed, by class, kept shown as done until the class ends (its end, as a moment). */
    private val confirmed = mutableMapOf<Int, Instant>()
    /** Why the server refused a check-in, what was said after class or a practice on one's own, sent in the
     *  background, until the student has read it: apart from [error], which every call clears. */
    var sendError by mutableStateOf<String?>(null)

    /** The calls of this sign-in, cancelled when signing out, so no reply for the account left lands on the next. */
    private var signedInScope = newSignedInScope()

    private fun newSignedInScope() = CoroutineScope(viewModelScope.coroutineContext + SupervisorJob(viewModelScope.coroutineContext[Job]))

    init {
        when {
            prefs.token == null -> loadStudio()
            restoreSaved() -> refreshBehind()
            else -> launchCall { refreshAll() }
        }
    }

    /** Opens on what this sign-in's first screens showed last, kept on the phone, as it stands now (classes that have
     *  ended dropped): true if there was some. */
    private fun restoreSaved(): Boolean {
        val kept = prefs.token?.let { saved.read(it, prefs.lang) } ?: return false
        val me = kept.me ?: return false
        val day = kept.day ?: return false
        return try {
            val account = User.from(me.getJSONObject("user"))
            val now = Instant.now()
            if (account.isTeacher) teacherHome = TeacherHome.from(day).at(now) else showDay(Home.from(day).at(now))
            stats = Stats.from(me.getJSONObject("stats"))
            kept.curricula?.let { curricula = Curricula.from(it) }
            openStore(account)
            user = account
            readAt = kept.at
            true
        } catch (e: JSONException) {
            saved.clear()
            false
        }
    }

    /** Keeps a part of the first screens on the phone, under this sign-in and language. */
    private fun keep(part: String, json: JSONObject) {
        prefs.token?.let { saved.keep(it, prefs.lang, part, json, System.currentTimeMillis()) }
    }

    /** Runs a call to the server: [busy] meanwhile ([signingIn] too, for a login or a sign-up), its error in [error]. */
    private fun launchCall(signIn: Boolean = false, block: suspend () -> Unit) {
        signedInScope.launch {
            calls++
            error = null
            if (signIn) signingIn = true
            try {
                block()
            } catch (e: ApiError) {
                failed(e)
            } catch (e: JSONException) { // a reply missing a field the app expects
                error = "generic"
            } finally {
                calls--
                if (signIn) signingIn = false
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

    // A write carries one request id per action on its target (a student's batch, an item's feedback), kept until the
    // action goes through, so a retry of it (after a timeout, say, or a second tap) is written once. When any action on
    // the target goes through, every id kept for it goes, so a later action, even the same one, is new.
    private val requestIds = mutableMapOf<String, String>()

    private suspend fun <T> once(target: String, action: String, send: suspend (String) -> T): T {
        val reply = send(requestIds.getOrPut("$target|$action") { newRequestId() })
        requestIds.keys.removeAll { it.startsWith("$target|") }
        return reply
    }

    /** The studio's words for the first screen, read without holding it up: the form works without them. If they cannot
     *  be read, the first screen says why, as the first sign that the studio is out of reach. */
    private fun loadStudio() {
        viewModelScope.launch {
            try {
                studio = Studio.from(api.get("/studio?lang=${prefs.lang}"))
            } catch (e: ApiError) {
                if (!busy && !signedIn) error = e.code
            } catch (_: JSONException) {
            }
        }
    }

    /** The studio's own words (its blessing, the meaning of its name, its headings), in the chosen language. */
    fun words() = StudioWords.from(studioFile, prefs.lang)

    /** The intake's assessment asanas and how to try each safely, in the chosen language, from the studio content. */
    fun assessment(): List<Pair<String, String>> = studioFile.getJSONObject("intake").getJSONArray("assessment")
        .map { a -> a.getString("item") to a.getJSONObject("how").let { it.optString(prefs.lang).ifEmpty { it.getString("en") } } }

    /** Who is signed in, their day and the curricula, read together. The day is read alongside /me for the role kept on
     *  the phone from the last sign-in; with none kept (or another), after /me. The account shows once its day has
     *  come, and the day even if the curricula cannot be read. */
    private suspend fun refreshAll() = coroutineScope {
        val kept = prefs.role
        val lists = if (!curriculaRead) async { runCatching { api.get("/curricula?lang=${prefs.lang}") } } else null
        val day = kept?.let { role -> async { readDay(teacher = role == "teacher") } }
        val me = api.get("/me")
        val account = User.from(me.getJSONObject("user"))
        keep(SavedScreens.ME, me)
        prefs.role = account.role
        if (day == null || (kept == "teacher") != account.isTeacher) {
            day?.cancel()
            readDay(account.isTeacher)
        } else {
            day.await()
        }
        if (user?.id != account.id) openStore(account)
        stats = Stats.from(me.getJSONObject("stats"))
        user = account
        lists?.let {
            val read = it.await().getOrThrow()
            curricula = Curricula.from(read)
            curriculaRead = true
            keep(SavedScreens.CURRICULA, read)
        }
        refreshedAt = SystemClock.elapsedRealtime()
    }

    private suspend fun readDay(teacher: Boolean) = if (teacher) readTeacherHome() else readHome()

    /** Reads the first screens again: behind them when they show (the Today tab [pulled] down, or anything else), else
     *  with the wait for them. */
    fun refresh(pulled: Boolean = false) = if (user == null) launchCall { refreshAll() } else refreshBehind(pulled)

    /** Reads the first screens again behind those showing, which stay as they are until the new ones come: a thin line
     *  meanwhile. If the studio cannot be reached, [shownFrom] says since when the screens are what they are. */
    private fun refreshBehind(pulled: Boolean = false) {
        if (refreshing) return
        signedInScope.launch {
            refreshing = true
            pulling = pulled
            try {
                refreshAll()
            } catch (e: ApiError) {
                if (e.code == "signed_out") signOutLocally() else shownFrom = readAt
            } catch (e: JSONException) {
                shownFrom = readAt
            } finally {
                refreshing = false
                pulling = false
            }
        }
    }

    /** Shows a day from the server ([dayRead]) on the Today tab, with what this phone has sent laid over it: the
     *  check-ins shown as done, those not confirmed yet and those that are, until their class ends, in case the day was
     *  read before the check-in; and what was said after class, while it waits for the server. */
    private fun showDay(day: Home? = dayRead) {
        dayRead = day
        if (day == null) return
        val now = Instant.now()
        confirmed.values.removeAll { it < now }
        val checkedIn = (pending.map { it.sessionId } + confirmed.keys).fold(day) { h, id -> h.checkedIn(id, true) }
        val after = checkedIn.afterClass
        val waiting = outbox.writes.filter { it.key == after?.id?.toString() }
        val mood = waiting.lastOrNull { it.kind == PendingWrite.AFTER_MOOD }?.let { JSONObject(it.body).intOrNull("mood") }
        val items = waiting.lastOrNull { it.kind == PendingWrite.AFTER_ITEMS }?.let { JSONObject(it.body).getJSONArray("entries").map(ItemFeedback::from) }
        home = if (mood == null && items == null) checkedIn
        else checkedIn.copy(afterSaid = Said(mood ?: checkedIn.afterSaid?.mood, items ?: checkedIn.afterSaid?.items.orEmpty()))
    }

    /** The student's Today tab from the server, kept on the phone too. */
    private suspend fun readHome() {
        val read = api.get("/home?lang=${prefs.lang}")
        showDay(Home.from(read))
        keep(SavedScreens.DAY, read)
        readAt = System.currentTimeMillis()
        shownFrom = null
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

    fun login(phone: String, password: String) = launchCall(signIn = true) { signIn(accounts.login(phone, password)) }

    fun signup(name: String, phone: String, password: String, teacher: Boolean, code: String) {
        if (password.length < Limits.PASSWORD_MIN) {
            error = "short_password"
            return
        }
        launchCall(signIn = true) {
            val body = JSONObject().put("name", name).put("phone", phone).put("password", password)
                .put("role", if (teacher) "teacher" else "student").put("code", code).put("lang", prefs.lang)
            // The same form sent again (after no answer came) keeps its request id.
            signIn(once("signup", body.toString().hashCode().toString()) { accounts.signup(body, it) })
        }
    }

    /** Keeps the login, then reads what the first screen needs; a new student is asked about themselves first. */
    private suspend fun signIn(account: Accounts.SignedIn) {
        saved.clear() // another sign-in's screens
        prefs.token = account.token
        prefs.role = account.user.role
        signedIn = true
        askIntake = account.newStudent
        refreshAll()
    }

    /** A student's own new password, after the current one; this phone stays signed in. [done] runs once it is through. */
    fun changePassword(current: String, new: String, changed: String, done: () -> Unit) = launchCall {
        val body = JSONObject().put("current_password", current).put("new_password", new)
        // Sent once, not tried again by itself; a second tap after no answer came carries the same request id, which the
        // server answers as it did the first, even when the two arrive together.
        once("password", (current + "\n" + new).hashCode().toString()) { api.post("/me/password", body, it, retry = false) }
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
        outbox.keepOnly(null)
        dayRead = null
        saved.clear()
        shownFrom = null
        prefs.token = null
        prefs.role = null
        signedIn = false
        askIntake = false
        user = null; home = null; stats = null; teacherHome = null; insights = null; review = null
        practice = emptyList(); soloSessions = emptyList(); solo = null; students = emptyList(); notes = emptyList(); sharedNotes = emptyList()
        items = emptyList(); itemHistory = null; intake = null; intakeRead = false; pending = emptyList(); sendError = null; soloRead = emptyList()
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
        curriculaRead = false
        if (user == null) {
            loadStudio()
        } else {
            viewModelScope.launch { try { api.post("/me", JSONObject().put("lang", lang), newRequestId()) } catch (_: ApiError) { } }
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
        pending = pending.filter { it.sessionId != sessionId } + PendingCheckin(sessionId, mood, newRequestId(), token)
        showDay()
        sendError = null
        sendCheckins()
    }

    /** Sends each check-in the server has not confirmed, with its request id and the token it was made with: at once,
     *  at each start and return to the app, and every two minutes while the Today tab is open, until it lands. A clear
     *  refusal (a 4xx) drops it and undoes it on the Today tab; [sendError] says why, except for one that came after
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
                    showDay()
                    when (e.code) {
                        "signed_out" -> signOutLocally()
                        "checkin_closed" -> if (classOf(p.sessionId)?.let { Instant.now() < it.endsAt } == true) sendError = e.code
                        "no_session" -> refreshHome()
                        "other_batch" -> { sendError = e.code; refreshHome() }
                        else -> sendError = e.code
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
        soloRead = summary.getJSONArray("solo").map(SoloSession::from).reversed()
        showSolo()
    }

    /** The practice on one's own as the Practice tab lists it: those still waiting for the server first. */
    private fun showSolo() {
        val waiting = outbox.writes.filter { it.kind == PendingWrite.SOLO }.reversed().map {
            val o = JSONObject(it.shown)
            SoloSession(Instant.ofEpochMilli(o.getLong("at")), o.getInt("minutes"), o.getJSONArray("items").strings())
        }
        soloSessions = waiting + soloRead
    }

    /** Finishes the practice on one's own: if anything was timed or said, it is saved on the phone at once and sent in
     *  the background, with one request id ([sendPending]); the student goes on at once. A refusal opens the run again,
     *  to change and send. */
    fun finishSolo(saved: String) {
        val token = prefs.token ?: return
        val now = SystemClock.elapsedRealtime()
        val run = solo?.stopped(now) ?: return
        solo = null
        val entries = run.entries()
        if (entries.isEmpty()) return
        val minutes = ((now - run.startedAt + 59_999) / 60000).toInt().coerceIn(1, 240) // whole minutes, rounded up
        val body = JSONObject().put("minutes", minutes).put("entries", JSONArray(entries.map { it.json() }))
        val names = entries.map { curricula?.library?.get(it.item)?.short(prefs.lang) ?: it.item }
        val shown = JSONObject().put("at", System.currentTimeMillis() - minutes * 60_000L).put("minutes", minutes).put("items", JSONArray(names))
            .put("run", keptRun(run))
        outbox.add(PendingWrite(PendingWrite.SOLO, run.startedAt.toString(), "/me/solo", body.toString(), newRequestId(), token, shown.toString()))
        showSolo()
        notice = saved
        sendPending()
    }

    /** A run as the phone keeps it, with when the phone started, so its times can be moved after a restart. */
    private fun keptRun(run: SoloRun) = JSONObject().put("boot", bootedAt()).put("run", run.saved()).toString()

    /** A run [keptRun] wrote, or null. Its times count from the phone's start: after a restart they are moved by the
     *  difference between the two starts. */
    private fun restoredRun(kept: String?): SoloRun? {
        if (kept == null) return null
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

    /** After class: the mood, if picked, and how each item went, if anything was said; [changing] what was said before.
     *  Saved on the phone and shown on the Today tab at once, and sent in the background ([sendPending]); [done] runs at
     *  once, and the student goes on. */
    fun sendAfterClass(sessionId: Int, mood: Int?, items: List<ItemFeedback>, changing: Boolean, done: () -> Unit) {
        val token = prefs.token ?: return
        if (mood != null) {
            val body = JSONObject().put("phase", "after").put("mood", mood)
            outbox.add(PendingWrite(PendingWrite.AFTER_MOOD, sessionId.toString(), "/sessions/$sessionId/checkin", body.toString(), newRequestId(), token))
        }
        val said = items.filter { it.said }
        // Changing what was said replaces all of it, even with nothing, so an item cleared is cleared on the server too.
        if (said.isNotEmpty() || changing) {
            val body = JSONObject().put("entries", JSONArray(said.map { it.json() }))
            outbox.add(PendingWrite(PendingWrite.AFTER_ITEMS, sessionId.toString(), "/sessions/$sessionId/practice", body.toString(), newRequestId(), token))
        }
        sendError = null
        showDay()
        done()
        sendPending()
    }

    /** Sends each write waiting in the outbox, with its request id and the login it was made with: at once, at each start
     *  and return to the app, and every two minutes while the app is open, until it lands. A clear refusal (a 4xx)
     *  undoes it and [sendError] says why: the Today tab shows the class as not yet said, and a practice on one's own
     *  opens again. Anything else (no connection, busy, a 5xx) keeps it for the next try. */
    fun sendPending() {
        outbox.writes.filter { it.requestId !in sendingWrites }.forEach { w ->
            sendingWrites += w.requestId
            signedInScope.launch {
                try {
                    val reply = outbox.send(w) ?: return@launch
                    when (w.kind) {
                        PendingWrite.AFTER_MOOD -> stats = Stats.from(reply.getJSONObject("stats"))
                        PendingWrite.SOLO -> { showSolo(); quietly { readPractice(); readItems(null) } }
                    }
                } catch (e: ApiError) {
                    if (e.code == "signed_out") return@launch signOutLocally()
                    sendError = if (e.code == "checkin_closed") "after_closed" else e.code
                    if (w.kind == PendingWrite.SOLO) {
                        if (solo == null) solo = restoredRun(JSONObject(w.shown).optString("run").ifEmpty { null })
                        showSolo()
                    } else {
                        showDay()
                    }
                } catch (_: JSONException) {
                } finally {
                    sendingWrites -= w.requestId
                }
            }
        }
    }

    /** Everything this phone has yet to send: check-ins, what was said after class, practice on one's own. */
    fun sendWaiting() {
        sendCheckins()
        sendPending()
    }

    /** Reads something again in the background, quietly: nothing shown if it fails. */
    private fun quietly(read: suspend () -> Unit) {
        signedInScope.launch {
            try {
                read()
            } catch (_: ApiError) {
            } catch (_: JSONException) {
            }
        }
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
        val reply = once("share:${note.id}", "") { api.post("/me/shared", JSONObject().put("text", note.text), it) }
        store?.let {
            it.markShared(note.id, reply.getInt("id"))
            notes = it.notes()
        }
        notice = done
    }

    // ---------- teacher ----------

    /** The teacher's day from the server, kept on the phone too. */
    private suspend fun readTeacherHome() {
        val read = api.get("/teacher/home?lang=${prefs.lang}")
        teacherHome = TeacherHome.from(read)
        keep(SavedScreens.DAY, read)
        readAt = System.currentTimeMillis()
        shownFrom = null
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
        once("group-code", "") { api.post("/teacher/group_code", JSONObject(), it) }
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
        val body = answers.json()
        intake = Intake.from(once("intake", body.toString().hashCode().toString()) { api.put("/me/intake", body, it) }.getJSONObject("intake"))
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
        once("status:$userId", status) { api.post("/teacher/students/$userId/status", JSONObject().put("status", status), it) }
        students = api.get("/teacher/students").getJSONArray("students").map(Student::from)
        readTeacherHome()
    }

    /** A new password for a student, sent once, not tried again by itself. The teacher's retry after no answer came, or
     *  a second confirm, carries the same request id, and the server gives it the same password, even when the two
     *  arrive together; the confirm is off while a call is out. */
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
        if (signedIn) sendWaiting()
        if (signedIn && !busy && !refreshing && stale) refresh() // signed in, or signed in but the studio was out of reach: try again
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
