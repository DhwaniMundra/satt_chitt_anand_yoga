package com.sattchittanand.yoga

import android.content.Context
import android.util.Log
import com.sattchittanand.yoga.companion.GemmaOnPhone
import com.sattchittanand.yoga.companion.HISTORY_TURNS
import com.sattchittanand.yoga.companion.KeptNote
import com.sattchittanand.yoga.companion.PracticeCompanion
import com.sattchittanand.yoga.companion.ItemName
import com.sattchittanand.yoga.companion.StudentData
import com.sattchittanand.yoga.companion.StudioNotes
import com.sattchittanand.yoga.companion.Tools
import com.sattchittanand.yoga.companion.URGENT_REPLY
import com.sattchittanand.yoga.companion.UpcomingClass
import com.sattchittanand.yoga.companion.isUrgent
import com.sattchittanand.yoga.companion.noteToSave
import com.sattchittanand.yoga.companion.withoutGlosses
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONObject

/**
 * The practice companion, answering on this phone with Gemma 4 E2B. The words of a message never leave the phone; the
 * tools ask the server only for what is the student's own or the studio's: the practice summary (/me/practice), the
 * coming classes (/home), the library of items (/curricula) and one item's history (/me/asanas/{key}).
 */
class PhoneCompanion(context: Context, private val api: Api, studio: JSONObject) {
    val gemma = GemmaOnPhone.get(context)
    private val companion: PracticeCompanion

    init {
        fun asset(name: String) = context.assets.open("studio/$name").bufferedReader().use { it.readText() }
        companion = PracticeCompanion(
            StudioNotes(asset("yoga_health.md"), asset("yoga_health.mr.md")),
            studio.getJSONObject("name").getString("en"), studio.getJSONObject("teacher").getJSONObject("short").getString("en"),
        )
    }

    /** The reply to [message]; [history] holds the earlier messages, oldest first, and [batch] names the student's
     *  batch. Emergency signs get the fixed reply first, with no model. Never throws: if Gemma fails, the reply says so. */
    suspend fun answer(user: User, store: LocalStore, message: String, lang: String, history: List<ChatLine>, batch: String?): ChatLine {
        if (isUrgent(message)) return ChatLine(URGENT_REPLY.getValue(lang), fromStudent = false, urgent = true)
        return try {
            val tools = Tools(Data(api, store), companion.notes, lang)
            val firstName = user.name.trim().split(Regex("\\s+")).first()
            val system = withContext(Dispatchers.IO) { companion.system(firstName, message, lang, tools, batch) }
            val earlier = history.takeLast(HISTORY_TURNS).map { it.fromStudent to it.text }
            val reply = gemma.reply(system, earlier, message, tools.toolSets(), banForeign = lang == "mr")
            val text = if (lang == "en") reply else withoutGlosses(reply)
            check(text.isNotBlank()) { "empty reply" }
            noteToSave(message, tools.used)?.let { store.addNote(it); tools.used += "save_my_note" }
            ChatLine(text, fromStudent = false, tools = tools.used.distinct())
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            Log.w("SCA-Companion", "Gemma could not answer", e)
            ChatLine(NO_ANSWER.getValue(lang), fromStudent = false)
        }
    }
}

private val NO_ANSWER = mapOf(
    "en" to "Gemma could not answer just now. Please try again.",
    "hi" to "Gemma अभी जवाब नहीं दे पाया। कृपया फिर से कोशिश करें।",
    "mr" to "Gemma ला आत्ता उत्तर देता आले नाही. कृपया पुन्हा प्रयत्न करा.",
)

/** What the tools read: the server for the student's practice and the classes, this phone for the notes. */
private class Data(private val api: Api, private val store: LocalStore) : StudentData {
    override fun practice(days: Int, lang: String): Map<String, Any?> = api.getNow("/me/practice?days=$days&lang=$lang").toMap()

    override fun upcoming(lang: String): List<UpcomingClass> =
        Home.from(api.getNow("/home?lang=$lang")).sessions.map { UpcomingClass(it.startsAt, it.batch.name, it.batch.about) }

    override fun saveNote(text: String) = store.addNote(text)

    override fun notes(): List<KeptNote> = store.notes().map { KeptNote(it.text, it.savedAt) }

    private var read: List<ItemName>? = null // the library, read once per question

    override fun library(): List<ItemName> = read ?: Curricula.from(api.getNow("/curricula?lang=en")).library.values
        .map { ItemName(it.key, it.sanskrit, it.name, it.english, it.aliases) }.also { read = it }

    override fun itemProgress(key: String): Map<String, Any?> = api.getNow("/me/asanas/$key").toMap()
}

/** The server's JSON as maps and lists, in the server's key order, as the tool hands it to Gemma. */
private fun JSONObject.toMap(): Map<String, Any?> = keys().asSequence().associateWithTo(LinkedHashMap()) { plain(get(it)) }

private fun plain(value: Any?): Any? = when (value) {
    JSONObject.NULL -> null
    is JSONObject -> value.toMap()
    is JSONArray -> (0 until value.length()).map { plain(value.get(it)) }
    else -> value
}
