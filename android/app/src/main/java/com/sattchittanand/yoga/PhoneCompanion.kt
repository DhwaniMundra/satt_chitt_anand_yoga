package com.sattchittanand.yoga

import android.content.Context
import android.util.Log
import com.sattchittanand.yoga.companion.PracticeCompanion
import com.sattchittanand.yoga.companion.GemmaOnPhone
import com.sattchittanand.yoga.companion.GemmaState
import com.sattchittanand.yoga.companion.KeptNote
import com.sattchittanand.yoga.companion.NotesReason
import com.sattchittanand.yoga.companion.Problem
import com.sattchittanand.yoga.companion.Reply
import com.sattchittanand.yoga.companion.StudentData
import com.sattchittanand.yoga.companion.StudioNotes
import com.sattchittanand.yoga.companion.Tools
import com.sattchittanand.yoga.companion.UpcomingClass
import com.sattchittanand.yoga.companion.URGENT_REPLY
import com.sattchittanand.yoga.companion.isUrgent
import com.sattchittanand.yoga.companion.noteToSave
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject
import java.util.Locale

/**
 * The practice companion, answering on this phone: Gemma 4 E2B when it is downloaded and loaded, otherwise the studio's
 * notes bundled in the app (saying why). The words of a question never leave the phone; the tools ask the server only
 * for the student's own practice summary and the coming classes.
 */
class PhoneCompanion(context: Context, private val api: Api) {
    val gemma = GemmaOnPhone.get(context)
    private val companion: PracticeCompanion

    init {
        fun asset(name: String) = context.assets.open("studio/$name").bufferedReader().use { it.readText() }
        val studio = JSONObject(asset("studio.json"))
        companion = PracticeCompanion(
            StudioNotes(asset("yoga_health.md"), asset("yoga_health.mr.md")),
            studio.getJSONObject("name").getString("en"), studio.getJSONObject("teacher").getString("short"),
        )
    }

    /** One reply to [message]; [history] holds the earlier messages, oldest first. Never throws: if Gemma fails, the
     *  notes answer. */
    suspend fun answer(user: User, store: LocalStore, message: String, lang: String, history: List<ChatLine>): Reply {
        val started = System.nanoTime()
        val reply = reply(user, store, message, lang, history)
        Log.i("SCA-Companion", "reply in %.1f s, mode %s, tools %s".format(Locale.US, (System.nanoTime() - started) / 1e9, reply.mode, reply.tools))
        return reply
    }

    private suspend fun reply(user: User, store: LocalStore, message: String, lang: String, history: List<ChatLine>): Reply {
        if (isUrgent(message)) return Reply(URGENT_REPLY.getValue(lang), emptyList(), "urgent") // first, with no model
        val save = { note: String -> store.addNote(note); Unit }
        val reason = when (val state = gemma.settled()) {
            is GemmaState.Ready -> try {
                val tools = Tools(Data(api, store), companion.notes, lang)
                val system = withContext(Dispatchers.IO) { companion.system(user.name.trim().split(Regex("\\s+")).first(), message, lang, tools) }
                val preface = companion.preface(history.map { it.fromStudent to it.text })
                val text = gemma.reply(system, preface, message, tools.toolSets(), banForeign = lang == "mr")
                if (text.isNotBlank()) {
                    noteToSave(message, tools.used)?.let { save(it); tools.used += "save_my_note" }
                    return Reply(text, tools.used.toList(), "companion")
                }
                NotesReason.NOT_STARTED
            } catch (e: Exception) {
                Log.w("SCA-Companion", "Gemma failed; answering from the notes", e)
                NotesReason.NOT_STARTED
            }
            is GemmaState.TooLittleMemory -> NotesReason.TOO_LITTLE_MEMORY
            is GemmaState.Failed -> if (state.problem == Problem.START) NotesReason.NOT_STARTED else NotesReason.NOT_DOWNLOADED
            else -> NotesReason.NOT_DOWNLOADED
        }
        return companion.notesOnly(message, lang, reason, save)
    }
}

/** What the tools read: the server for the student's practice and the classes, this phone for the notes. */
private class Data(private val api: Api, private val store: LocalStore) : StudentData {
    override fun practice(days: Int, lang: String): Map<String, Any?> = api.getNow("/me/practice?days=$days&lang=$lang").toMap()

    override fun upcoming(lang: String): List<UpcomingClass> =
        Home.from(api.getNow("/home?lang=$lang")).sessions.map { UpcomingClass(it.startsAt, it.info.name, it.info.level, it.info.about) }

    override fun saveNote(text: String) {
        store.addNote(text)
    }

    override fun notes(): List<KeptNote> = store.notes().map { KeptNote(it.text, it.savedAt) }
}

/** The server's JSON as maps and lists, in the server's key order, as the tool hands it to Gemma. */
fun JSONObject.toMap(): Map<String, Any?> = keys().asSequence().associateWithTo(LinkedHashMap()) { plain(get(it)) }

private fun plain(value: Any?): Any? = when (value) {
    JSONObject.NULL -> null
    is JSONObject -> value.toMap()
    is JSONArray -> (0 until value.length()).map { plain(value.get(it)) }
    else -> value
}
