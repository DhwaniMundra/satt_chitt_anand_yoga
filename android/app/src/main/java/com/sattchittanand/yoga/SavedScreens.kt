package com.sattchittanand.yoga

import org.json.JSONException
import org.json.JSONObject
import java.io.File
import java.security.MessageDigest

/**
 * What the first screens showed, kept on the phone for one sign-in, so the app opens on it at once and reads it afresh
 * behind it: the account and its stats (/me), the day (/home or /teacher/home) and the curricula, each as the server
 * sent it, in one language. Kept under a hash of the login token, so another sign-in never opens on it; [clear] at
 * sign-out. One small JSON file in the app's private storage.
 */
class SavedScreens(private val file: File) {

    /** What was kept: when the day was read (epoch ms), and each part as the server sent it, or null. */
    class Saved(val at: Long, val me: JSONObject?, val day: JSONObject?, val curricula: JSONObject?)

    /** What was kept for this login token and language, or null. */
    @Synchronized
    fun read(token: String, lang: String): Saved? {
        val o = load() ?: return null
        if (o.optString("login") != hash(token) || o.optString("lang") != lang) return null
        return Saved(o.optLong("at"), o.optJSONObject(ME), o.optJSONObject(DAY), o.optJSONObject(CURRICULA))
    }

    /** Keeps one part ([ME], [DAY] or [CURRICULA]) for this login and language, read at [at]; what was kept for another
     *  login or language goes. */
    @Synchronized
    fun keep(token: String, lang: String, part: String, json: JSONObject, at: Long) {
        val login = hash(token)
        val o = load()?.takeIf { it.optString("login") == login && it.optString("lang") == lang } ?: JSONObject().put("login", login).put("lang", lang)
        o.put(part, json)
        if (part == DAY) o.put("at", at)
        file.parentFile?.mkdirs()
        val next = File(file.path + ".tmp")
        next.writeText(o.toString())
        next.renameTo(file)
    }

    @Synchronized
    fun clear() {
        file.delete()
    }

    private fun load(): JSONObject? = try {
        if (file.isFile) JSONObject(file.readText()) else null
    } catch (e: JSONException) {
        null
    }

    private fun hash(token: String) = MessageDigest.getInstance("SHA-256").digest(token.toByteArray()).joinToString("") { "%02x".format(it) }

    companion object {
        const val ME = "me"
        const val DAY = "day"
        const val CURRICULA = "curricula"
    }
}
