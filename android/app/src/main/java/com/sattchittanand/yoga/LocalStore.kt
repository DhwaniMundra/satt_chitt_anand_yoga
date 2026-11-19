package com.sattchittanand.yoga

import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.time.Instant

/**
 * The companion's chat and the notes it keeps, on this phone only: one small JSON file per account in the app's
 * private storage (not in device backups: allowBackup is off). The server never sees them; a note reaches the teacher
 * only when the student shares it ([Note.sharedId] is then the server's id for it).
 */
class LocalStore(dir: File, userId: Int) {
    private val file = File(dir, "companion/$userId.json")
    private var chat = mutableListOf<ChatLine>()
    private var notes = mutableListOf<Note>()
    private var nextId = 1

    init {
        if (file.isFile) {
            try {
                val o = JSONObject(file.readText())
                o.getJSONArray("chat").map { chat += fromJson(it) }
                o.getJSONArray("notes").map { n ->
                    notes += Note(n.getInt("id"), n.getString("text"), Instant.parse(n.getString("saved_at")),
                        if (n.isNull("shared_id")) null else n.getInt("shared_id"))
                }
                nextId = o.optInt("next_id", (notes.maxOfOrNull { it.id } ?: 0) + 1)
            } catch (e: org.json.JSONException) { // a damaged file: start again rather than crash at every launch
                file.renameTo(File(file.path + ".damaged"))
            }
        }
    }

    @Synchronized fun chat(): List<ChatLine> = chat.toList()
    @Synchronized fun notes(): List<Note> = notes.toList()

    @Synchronized fun add(line: ChatLine) { chat += line; save() }
    @Synchronized fun clearChat() { chat.clear(); save() }

    @Synchronized fun addNote(text: String): Note =
        Note(nextId++, text.trim().take(500), Instant.now()).also { notes += it; save() }

    @Synchronized fun forget(id: Int) { notes.removeAll { it.id == id }; save() }

    @Synchronized fun markShared(id: Int, sharedId: Int) {
        notes = notes.map { if (it.id == id) it.copy(sharedId = sharedId) else it }.toMutableList()
        save()
    }

    private fun save() {
        val o = JSONObject()
            .put("chat", JSONArray(chat.map(::toJson)))
            .put("notes", JSONArray(notes.map { JSONObject().put("id", it.id).put("text", it.text).put("saved_at", it.savedAt.toString()).put("shared_id", it.sharedId ?: JSONObject.NULL) }))
            .put("next_id", nextId)
        file.parentFile?.mkdirs()
        val temp = File(file.path + ".tmp")
        temp.writeText(o.toString())
        temp.renameTo(file) // whole or not at all
    }

    private fun toJson(line: ChatLine) = JSONObject().put("text", line.text).put("student", line.fromStudent)
        .put("tools", JSONArray(line.tools)).put("mode", line.mode ?: JSONObject.NULL)

    private fun fromJson(o: JSONObject) = ChatLine(o.getString("text"), o.getBoolean("student"), o.getJSONArray("tools").strings(), o.str("mode"))
}
