package com.sattchittanand.yoga

import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject

/**
 * A write the app keeps on the phone: sent again, with the same request id and the login it was made with, until it
 * lands; then kept a while as [landed], so the screens show it over a reply read before it landed. [kind] says what it
 * is ([AFTER_MOOD], [AFTER_ITEMS], [SOLO]), [key] what a newer write of the same kind replaces (the class, the practice
 * run), and [shown] what the screens need of it meanwhile, and to undo it. [failures] counts the server's errors so
 * far; a practice on one's own the server refused, or gave up on, stays as [refused] (the reason), to open again.
 */
data class PendingWrite(val kind: String, val key: String, val path: String, val body: String, val requestId: String, val token: String,
    val shown: String = "{}", val failures: Int = 0, val landed: Boolean = false, val refused: String? = null) {

    /** Waiting to be sent: neither landed nor refused. */
    val waiting get() = !landed && refused == null

    /** What a newer write replaces, and what is sent one at a time, in order. */
    val slot get() = "$kind:$key"

    companion object {
        /** The mood after a class. */
        const val AFTER_MOOD = "after_mood"
        /** How each item of a class went. */
        const val AFTER_ITEMS = "after_items"
        /** A practice on one's own. */
        const val SOLO = "solo"

        fun saved(list: List<PendingWrite>): String = JSONArray(list.map {
            JSONObject().put("kind", it.kind).put("key", it.key).put("path", it.path).put("body", it.body).put("id", it.requestId)
                .put("token", it.token).put("shown", it.shown).put("failures", it.failures).put("landed", it.landed)
                .put("refused", it.refused ?: JSONObject.NULL)
        }).toString()

        /** The writes [saved] wrote; none if the text is missing or not theirs. */
        fun restore(text: String?): List<PendingWrite> = try {
            if (text == null) emptyList() else JSONArray(text).map {
                PendingWrite(it.getString("kind"), it.getString("key"), it.getString("path"), it.getString("body"), it.getString("id"),
                    it.getString("token"), it.optString("shown", "{}"), it.optInt("failures"), it.optBoolean("landed"), it.str("refused"))
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

    /** Adds a write, in place of one of the same kind and key, waiting, landed or refused. */
    fun add(write: PendingWrite) {
        writes = writes.filter { it.slot != write.slot } + write
    }

    fun remove(write: PendingWrite) {
        writes = writes - write
    }

    /** Changes a write still kept; nothing if a newer one has taken its place. */
    fun change(write: PendingWrite, changed: (PendingWrite) -> PendingWrite) {
        if (write in writes) writes = writes.map { if (it == write) changed(it) else it }
    }

    /** Drops the writes [gone] picks: landed ones no longer needed on screen. */
    fun drop(gone: (PendingWrite) -> Boolean) {
        if (writes.any(gone)) writes = writes.filterNot(gone)
    }

    /** Keeps only the writes made with this login: none, signed out. */
    fun keepOnly(token: String?) {
        if (writes.any { it.token != token }) writes = writes.filter { it.token == token }
    }

    /**
     * Sends a write (with the api's own few tries): the server's answer once it has it, the write then kept as landed;
     * null when it is to be sent again later (no answer, the server busy or failing). A refusal (a 4xx) drops it, and is
     * thrown for the screens to undo it and say why; so is the server failing [GIVE_UP_AFTER] times ("gave_up"), as a
     * write it fails on every time would otherwise be sent for ever.
     */
    suspend fun send(write: PendingWrite): JSONObject? {
        val reply = try {
            api.post(write.path, JSONObject(write.body), write.requestId, token = write.token)
        } catch (e: ApiError) {
            when {
                e.status in 400..499 -> {
                    remove(write)
                    throw e
                }
                e.status >= 500 && e.code != "busy" -> {
                    if (write.failures + 1 >= GIVE_UP_AFTER) {
                        remove(write)
                        throw ApiError("gave_up", e.status)
                    }
                    change(write) { it.copy(failures = it.failures + 1) }
                }
            }
            return null
        }
        change(write) { it.copy(landed = true) }
        return reply
    }

    companion object {
        /** The server's errors (a 5xx, but busy, which passes) after which a write is given up: each send is the api's
         *  own few tries, and a write is sent again at each start, return to the app and two minutes, so this is a
         *  couple of dozen failures over a quarter of an hour or more. */
        const val GIVE_UP_AFTER = 8
    }
}
