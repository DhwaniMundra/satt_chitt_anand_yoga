package com.sattchittanand.yoga

import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import org.json.JSONArray
import org.json.JSONException
import org.json.JSONObject
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.util.UUID
import kotlin.random.Random

/**
 * Why a call failed. [code] is an error the server named ("bad_login", "pending", …; for a check its validation
 * refused, a [problemCode] naming the field), "network" when no reply came, "server" when what answered is not the
 * studio's server (an HTTP error, or a page that is no reply of its own), or "unknown" when the reply
 * cannot be the call's own (see [Api]). [status] is the reply's own status, 0 with none. [unsent]: the call failed
 * before it left the phone, so the server never saw it.
 */
class ApiError(val code: String, val status: Int = 0, val unsent: Boolean = false) : Exception(code) {
    /** Whether the server surely wrote nothing for the call: it never arrived, was refused, or found the server busy. */
    val nothingDone get() = unsent || status in 400..499 || code == "busy"
}

/** A 422's first problem as a code the app words: "too_long:pain_note:600", "range:height_cm" or "invalid:name", the
 *  field being the last name in its location (["body", "entries", 0, "note"] is "note"). */
fun problemCode(detail: JSONArray): String {
    val first = detail.optJSONObject(0) ?: return "generic"
    val loc = first.optJSONArray("loc") ?: JSONArray()
    val field = (loc.length() - 1 downTo 0).map { loc.opt(it) }.firstOrNull { it is String } as String? ?: "body"
    return when (first.text("type")) {
        "string_too_long" -> "too_long:$field:${first.optJSONObject("ctx")?.intOrNull("max_length") ?: 0}"
        "greater_than_equal", "less_than_equal" -> "range:$field"
        else -> "invalid:$field"
    }
}

fun newRequestId(): String = UUID.randomUUID().toString()

/** How one envelope goes to the backend and its reply comes back, as JSON. Fails with an [ApiError], "network" or
 *  "server". */
fun interface Exchange {
    fun send(envelope: String): JSONObject
}

/** Told of each try of a call: as it goes, and how it ended (null: answered). */
interface Tries {
    fun sending()
    fun ended(error: ApiError?)
}

/**
 * The envelope POSTed to [server], then the redirect followed with GET, as Apps Script answers. The redirect's target
 * answers once (fetched again, it gives the web app's health check), so it is never fetched again on its own: a failure
 * on the way fails the whole call. What went wrong goes to the log as the exception's class, the HTTP status and the
 * host, never the address's path, the envelope or the reply.
 */
class HttpExchange(private val server: () -> String) : Exchange {

    override fun send(envelope: String): JSONObject {
        val bytes = envelope.toByteArray()
        var url = URL(server())
        var conn = open(url)
        conn.requestMethod = "POST"
        conn.doOutput = true
        conn.setFixedLengthStreamingMode(bytes.size) // a body streamed, not buffered, is never sent twice by the platform
        conn.setRequestProperty("Content-Type", "application/json; charset=utf-8")
        try {
            conn.connect()
        } catch (e: IOException) { // the address, the connection or TLS: nothing has left the phone
            throw failed(url, e, unsent = true)
        }
        try {
            conn.outputStream.use { it.write(bytes) }
            repeat(MAX_REDIRECTS + 1) {
                val code = conn.responseCode
                if (code !in 300..399) {
                    if (code != HttpURLConnection.HTTP_OK) throw notTheServer(url, code)
                    val text = conn.inputStream.bufferedReader().use { it.readText() }
                    return try {
                        JSONObject(text)
                    } catch (e: JSONException) { // a sign-in page, an error page, a wrong address
                        throw notTheServer(url, code)
                    }
                }
                val location = conn.getHeaderField("Location") ?: throw notTheServer(url, code)
                conn.inputStream.use { it.readBytes() } // read to its end, so the connection can be used again
                url = URL(conn.url, location)
                conn = open(url)
            }
            throw notTheServer(url, conn.responseCode)
        } catch (e: IOException) {
            throw failed(url, e, unsent = false)
        }
    }

    private fun failed(url: URL, e: IOException, unsent: Boolean): ApiError {
        Log.w(TAG, "no reply from ${url.host}${if (unsent) ", nothing sent" else ""}: ${e.javaClass.simpleName}")
        return ApiError("network", unsent = unsent)
    }

    private fun notTheServer(url: URL, code: Int): ApiError {
        Log.w(TAG, "HTTP $code from ${url.host}, not the studio server's reply")
        return ApiError("server")
    }

    private fun open(url: URL) = (url.openConnection() as HttpURLConnection).apply {
        instanceFollowRedirects = false
        connectTimeout = 10_000
        readTimeout = 45_000 // a write waits up to 20 s for the script's lock, after the script's own start
    }

    private companion object {
        const val TAG = "SCA-Api"
        const val MAX_REDIRECTS = 3
    }
}

/**
 * The backend's API. The backend is a Google Apps Script web app, which cannot read request headers or set a status,
 * so every call is one POST of an envelope {"method", "path", "token", "body"} (the path carries the query string),
 * and every answer is HTTP 200 with {"status", "body"}: `status` is the call's real status. A write may carry a request
 * id: the server answers a repeat of it as it did the first time.
 *
 * A failed call is tried again as [tryAgain] says, up to [TRIES] times in all, waiting a little longer each time. The
 * health check's answer, the one with "assistant" (no other answer has it), is what the redirect's target gives when
 * fetched a second time: for any other call, the outcome is "unknown".
 */
class Api(private val token: () -> String?, private val exchange: Exchange, private val pause: suspend (Long) -> Unit = { delay(it) }) {

    suspend fun get(path: String) = call("GET", path, null, null, replays = false)

    /** [requestId] for a write the server keeps by it: the same id for each try of the same action, which the server
     *  writes once, so it may be tried again ([retry]). [token]: the login to send it as, when not the current one.
     *  [tries] hears of each try. */
    suspend fun post(path: String, body: JSONObject = JSONObject(), requestId: String? = null, retry: Boolean = requestId != null,
        token: String? = null, tries: Tries? = null) = call("POST", path, body, requestId, requestId != null && retry, token, tries)

    /** Each PUT replaces what it names, so each carries a request id and may be tried again. */
    suspend fun put(path: String, body: JSONObject, requestId: String = newRequestId()) = call("PUT", path, body, requestId, replays = true)

    /** A GET on the calling thread, for the companion's tools, which run on Gemma's own thread. */
    fun getNow(path: String): JSONObject = runBlocking { send("GET", path, null, null, false, null, null) }

    private suspend fun call(method: String, path: String, body: JSONObject?, requestId: String?, replays: Boolean, token: String? = null,
        tries: Tries? = null): JSONObject = withContext(Dispatchers.IO) { send(method, path, body, requestId, replays, token, tries) }

    private suspend fun send(method: String, path: String, body: JSONObject?, requestId: String?, replays: Boolean, token: String?,
        tries: Tries?): JSONObject {
        var tried = 0
        while (true) {
            tried++
            tries?.sending()
            try {
                return request(method, path, body, requestId, token).also { tries?.ended(null) }
            } catch (e: ApiError) {
                tries?.ended(e)
                if (tried >= TRIES || !tryAgain(e, read = method == "GET", replays = replays)) throw e
            }
            val wait = FIRST_WAIT_MS shl (tried - 1)
            pause(wait + Random.nextLong(wait / 2))
        }
    }

    private fun request(method: String, path: String, body: JSONObject?, requestId: String?, token: String?): JSONObject {
        val login = token ?: this.token() ?: ""
        val envelope = JSONObject().put("method", method).put("path", path).put("token", login).put("body", body ?: JSONObject.NULL)
        if (requestId != null) envelope.put("request_id", requestId)
        val reply = exchange.send(envelope.toString())
        if (!reply.has("status")) throw ApiError("server") // JSON, but no reply of the studio's
        val status = reply.optInt("status")
        val answer = reply.optJSONObject("body") ?: JSONObject()
        if (status !in 200..299) {
            val code = when (val detail = answer.opt("detail")) {
                is JSONArray -> problemCode(detail)
                is String -> detail.ifEmpty { "generic" }
                else -> "generic"
            }
            throw ApiError(code, status)
        }
        if (answer.has("assistant") && "$method ${path.substringBefore('?')}" != "GET /health") throw ApiError("unknown")
        return answer
    }

    companion object {
        const val TRIES = 3
        private const val FIRST_WAIT_MS = 1_000L // then 2 s, each with up to half again at random


        private val AGAIN = setOf("network", "server", "busy", "unknown")

        /** Whether a call that failed with [e] is tried again, with the same request id if it has one: one that never
         *  left the phone, always; a [read], or a write the server answers again by its request id ([replays]), when no
         *  reply came, the server failed or was busy, or the reply was not its own. A refusal, never. */
        fun tryAgain(e: ApiError, read: Boolean, replays: Boolean) = e.unsent || (read || replays) && e.code in AGAIN
    }
}
