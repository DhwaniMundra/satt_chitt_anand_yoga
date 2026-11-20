package com.sattchittanand.yoga

import com.sun.net.httpserver.HttpServer
import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Which calls are tried again, how often and with which request id, and how each failure is named. */
class ApiTest {

    /** A backend that gives each call the next of [script]: a reply's text, or an error to throw. Keeps every envelope. */
    private class Scripted(vararg script: Any) : Exchange {
        val left = script.toMutableList()
        val sent = mutableListOf<JSONObject>()
        override fun send(envelope: String): JSONObject {
            sent += JSONObject(envelope)
            return when (val next = left.removeAt(0)) {
                is ApiError -> throw next
                else -> JSONObject(next as String)
            }
        }
    }

    private val waits = mutableListOf<Long>()
    private fun api(backend: Exchange) = Api({ "token-a" }, backend) { waits += it }

    private fun failing(block: suspend () -> Unit): ApiError = try {
        runBlocking { block() }
        fail("no error")
        throw IllegalStateException()
    } catch (e: ApiError) {
        e
    }

    private val ok = """{"status": 200, "body": {"ok": true, "id": 7}}"""
    private val home = """{"status": 200, "body": {"sessions": []}}"""
    private val busy = """{"status": 503, "body": {"detail": "busy"}}"""
    private fun lost() = ApiError("network")
    private fun neverSent() = ApiError("network", unsent = true)
    private fun googleError() = ApiError("server", http = 503)

    @Test fun aReadIsTriedThreeTimesInAllWhenNoReplyComes() {
        val backend = Scripted(lost(), lost(), lost(), home)
        val e = failing { api(backend).get("/home?lang=en") }
        assertEquals("network", e.code)
        assertEquals(3, backend.sent.size)
        assertEquals(2, waits.size)
        assertTrue("about a second, then about two, at random", waits[0] in 1_000L until 1_500L && waits[1] in 2_000L until 3_000L)
    }

    @Test fun aReadIsTriedAgainWhenTheServerFailsOrIsBusy() {
        val backend = Scripted(googleError(), busy, home)
        assertEquals(JSONObject(home).getJSONObject("body").toString(), runBlocking { api(backend).get("/home") }.toString())
        assertEquals(3, backend.sent.size)
    }

    @Test fun aWriteWithoutARequestIdIsNotSentAgainOnceItHasGone() {
        for (failure in listOf<Any>(lost(), googleError(), busy)) {
            val backend = Scripted(failure, ok)
            failing { api(backend).post("/me/shared", JSONObject().put("text", "knee")) }
            assertEquals(failure.toString(), 1, backend.sent.size)
        }
    }

    @Test fun anyCallThatNeverLeftThePhoneIsTriedAgain() {
        val write = Scripted(neverSent(), ok)
        runBlocking { api(write).post("/teacher/students/3/password", JSONObject(), "r9", retry = false) }
        assertEquals(2, write.sent.size)
        val read = Scripted(neverSent(), neverSent(), neverSent(), home)
        assertTrue(failing { api(read).get("/home") }.unsent)
        assertEquals("three tries at most", 3, read.sent.size)
    }

    @Test fun aWriteWithARequestIdIsTriedAgainWithTheSameId() {
        val backend = Scripted(lost(), googleError(), ok)
        runBlocking { api(backend).post("/me/solo", JSONObject().put("minutes", 5), "solo-1") }
        assertEquals(listOf("solo-1", "solo-1", "solo-1"), backend.sent.map { it.getString("request_id") })
        assertEquals(listOf("token-a"), backend.sent.map { it.getString("token") }.distinct())
    }

    @Test fun aWriteNotToBeRepeatedKeepsItsIdButGoesOnce() {
        val backend = Scripted(lost(), ok)
        failing { api(backend).post("/me/password", JSONObject(), "pw-1", retry = false) }
        assertEquals(1, backend.sent.size)
        assertEquals("pw-1", backend.sent.single().getString("request_id"))
    }

    @Test fun everyPutCarriesARequestIdAndIsTriedAgainWithIt() {
        val backend = Scripted(busy, """{"status": 200, "body": {"intake": {}}}""")
        runBlocking { api(backend).put("/me/intake", JSONObject().put("age", 30)) }
        val ids = backend.sent.map { it.getString("request_id") }
        assertEquals(2, ids.size)
        assertEquals(1, ids.distinct().size)
        assertTrue(ids.first().isNotEmpty())
    }

    @Test fun aRefusalIsNeverTriedAgainAndKeepsItsStatus() {
        val backend = Scripted("""{"status": 401, "body": {"detail": "signed_out"}}""", home)
        val e = failing { api(backend).get("/home") }
        assertEquals(listOf("signed_out", "401"), listOf(e.code, e.status.toString()))
        assertEquals(1, backend.sent.size)
        assertTrue(e.nothingDone)
    }

    /** {"ok": true} alone is what the redirect's target gives when fetched a second time: the health check's answer. */
    @Test fun aLoneOkIsTheHealthChecksAnswerUnlessItIsTheCallsOwn() {
        val lone = """{"status": 200, "body": {"ok": true}}"""
        val read = Scripted(lone, home)
        runBlocking { api(read).get("/home") }
        assertEquals("a read is asked again", 2, read.sent.size)
        val write = Scripted(lone, ok)
        assertEquals(7, runBlocking { api(write).post("/me/solo", JSONObject(), "solo-2") }.getInt("id"))
        assertEquals("and a write with its request id, the same one", listOf("solo-2", "solo-2"), write.sent.map { it.getString("request_id") })
        val noId = Scripted(lone, ok)
        assertEquals("unknown", failing { api(noId).post("/me/shared", JSONObject()) }.code)
        assertEquals(1, noId.sent.size)
        for ((method, path) in listOf("POST" to "/feedback", "POST" to "/auth/logout", "POST" to "/me/password", "POST" to "/teacher/students/12/status",
            "GET" to "/health")) {
            val own = Scripted(lone)
            val reply = runBlocking { if (method == "GET") api(own).get(path) else api(own).post(path, JSONObject(), "f-1") }
            assertEquals(path, true, reply.getBoolean("ok"))
        }
    }

    @Test fun theServersOwnErrorsAreNamedAsItNamesThem() {
        val invalid = """{"status": 422, "body": {"detail": [{"loc": ["body", "pain_note"], "type": "string_too_long", "ctx": {"max_length": 600}}]}}"""
        assertEquals("too_long:pain_note:600", failing { api(Scripted(invalid)).put("/me/intake", JSONObject()) }.code)
        assertEquals("server", failing { api(Scripted("""{"message": "hello"}""", """{"message": "hello"}""", """{"message": "hello"}""")).get("/home") }.code)
        val crash = failing { api(Scripted("""{"status": 500, "body": {"detail": "Internal Server Error"}}""")).get("/home") }
        assertEquals(listOf("Internal Server Error", "500"), listOf(crash.code, crash.status.toString()))
    }

    @Test fun whichFailuresAreTriedAgain() {
        val cases = listOf(
            Triple(ApiError("network"), true to false, true), Triple(ApiError("network"), false to false, false),
            Triple(ApiError("network"), false to true, true), Triple(ApiError("network", unsent = true), false to false, true),
            Triple(ApiError("server", http = 502), true to false, true), Triple(ApiError("server", http = 502), false to false, false),
            Triple(ApiError("busy", 503), false to true, true), Triple(ApiError("unknown"), false to true, true),
            Triple(ApiError("bad_login", 401), false to true, false), Triple(ApiError("phone_taken", 409), true to true, false),
        )
        for ((e, kind, again) in cases) assertEquals("${e.code} read=${kind.first} replays=${kind.second}", again, Api.tryAgain(e, kind.first, kind.second))
    }

    // ---------- over HTTP ----------

    private fun serve(handle: (com.sun.net.httpserver.HttpExchange) -> Unit): HttpServer =
        HttpServer.create(InetSocketAddress("127.0.0.1", 0), 0).apply {
            createContext("/") { x -> x.requestBody.readBytes(); handle(x); x.close() }
            start()
        }

    private fun HttpServer.address() = "http://127.0.0.1:${address.port}/exec"

    private fun com.sun.net.httpserver.HttpExchange.answer(code: Int, text: String, type: String = "application/json") {
        responseHeaders.add("Content-Type", type)
        val bytes = text.toByteArray()
        sendResponseHeaders(code, if (bytes.isEmpty()) -1 else bytes.size.toLong())
        if (bytes.isNotEmpty()) responseBody.write(bytes)
    }

    @Test fun anEnvelopeIsPostedAndItsRedirectFollowed() {
        val server = serve { x ->
            if (x.requestMethod == "POST") {
                x.responseHeaders.add("Location", "/echo?key=1")
                x.answer(302, "")
            } else {
                x.answer(200, home)
            }
        }
        try {
            assertEquals(200, HttpExchange { server.address() }.send("{}").getInt("status"))
        } finally {
            server.stop(0)
        }
    }

    @Test fun anHttpErrorOrAPageIsTheServersFailureNotTheNetworks() {
        for ((code, page) in listOf(503 to "<html>Service Unavailable</html>", 200 to "<html>Sign in</html>")) {
            val server = serve { x -> x.answer(code, page, "text/html") }
            try {
                val e = try {
                    HttpExchange { server.address() }.send("{}")
                    fail("no error")
                    throw IllegalStateException()
                } catch (e: ApiError) {
                    e
                }
                assertEquals(listOf("server", "$code"), listOf(e.code, e.http.toString()))
                assertFalse(e.unsent)
            } finally {
                server.stop(0)
            }
        }
    }

    @Test fun noConnectionIsANetworkFailureBeforeAnythingWasSent() {
        val port = ServerSocket(0).use { it.localPort } // free, and nothing listens on it
        val e = try {
            HttpExchange { "http://127.0.0.1:$port/exec" }.send("{}")
            throw IllegalStateException()
        } catch (e: ApiError) {
            e
        }
        assertEquals("network", e.code)
        assertTrue(e.unsent)
    }

    @Test fun aReplyLostAfterTheCallWentIsANetworkFailureAfterItWasSent() {
        val socket = ServerSocket(0)
        val calls = AtomicInteger()
        val server = thread {
            while (!socket.isClosed) {
                val client = try { socket.accept() } catch (e: Exception) { break }
                calls.incrementAndGet()
                val input = client.getInputStream().bufferedReader()
                var length = 0
                while (true) {
                    val line = input.readLine() ?: break
                    if (line.isEmpty()) break
                    if (line.lowercase().startsWith("content-length:")) length = line.substringAfter(':').trim().toInt()
                }
                repeat(length) { input.read() }
                client.close() // the call has arrived; its answer never comes
            }
        }
        try {
            val e = try {
                HttpExchange { "http://127.0.0.1:${socket.localPort}/exec" }.send("""{"method": "POST"}""")
                throw IllegalStateException()
            } catch (e: ApiError) {
                e
            }
            assertEquals("network", e.code)
            assertFalse(e.unsent)
            assertEquals("posted once, never again by itself", 1, calls.get())
        } finally {
            socket.close()
            server.join(2_000)
        }
    }
}
