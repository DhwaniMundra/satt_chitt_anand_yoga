package com.sattchittanand.yoga

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * A write the server has not confirmed: kept on the phone and sent again, with the same request id and the login it
 * was made with, until it lands. [kind] says what it is ([AFTER_MOOD], [AFTER_ITEMS], [SOLO]), [key] what a newer write
 * of the same kind replaces (the class, the practice run), and [shown] what the screens need of it meanwhile, and to
 * undo it.
 */
data class PendingWrite(val kind: String, val key: String, val path: String, val body: String, val requestId: String, val token: String,
    val shown: String = "{}") {

    companion object {
        /** The mood after a class. */
        const val AFTER_MOOD = "after_mood"
        /** How each item of a class went. */
        const val AFTER_ITEMS = "after_items"
        /** A practice on one's own. */
        const val SOLO = "solo"

        fun saved(list: List<PendingWrite>): String = JSONArray(list.map {
            JSONObject().put("kind", it.kind).put("key", it.key).put("path", it.path).put("body", it.body).put("id", it.requestId)
                .put("token", it.token).put("shown", it.shown)
        }).toString()

        /** The writes [saved] wrote; none if the text is missing or not theirs. */
        fun restore(text: String?): List<PendingWrite> = try {
            if (text == null) emptyList() else JSONArray(text).map {
                PendingWrite(it.getString("kind"), it.getString("key"), it.getString("path"), it.getString("body"), it.getString("id"),
                    it.getString("token"), it.optString("shown", "{}"))
            }
        } catch (e: JSONException) {
            emptyList()
        }
    }
}

/** Where [Outbox] keeps its writes: on the phone, so they outlast the app being closed. */
interface OutboxMemory {
    var outbox: String?
}

/** The writes waiting for the server, kept in [memory], each sent with its own request id and login until it lands. */
class Outbox(private val api: Api, private val memory: OutboxMemory) {

    var writes: List<PendingWrite> = PendingWrite.restore(memory.outbox)
        private set(value) {
            field = value
            memory.outbox = PendingWrite.saved(value)
        }

    /** Adds a write, in place of one of the same kind and key still waiting. */
    fun add(write: PendingWrite) {
        writes = writes.filter { it.kind != write.kind || it.key != write.key } + write
    }

    /** Keeps only the writes made with this login: none, signed out. */
    fun keepOnly(token: String?) {
        if (writes.any { it.token != token }) writes = writes.filter { it.token == token }
    }

    /**
     * Sends a write (with the api's own few tries): the server's answer once it has it, the write then gone; null when
     * it is to be sent again later (no answer, the server busy or failing). A refusal (a 4xx) drops it too, and is
     * thrown for the screens to undo it and say why.
     */
    suspend fun send(write: PendingWrite): JSONObject? {
        val reply = try {
            api.post(write.path, JSONObject(write.body), write.requestId, token = write.token)
        } catch (e: ApiError) {
            if (e.status !in 400..499) return null
            writes = writes - write
            throw e
        }
        writes = writes - write
        return reply
    }
}
