package com.sattchittanand.yoga

import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** What was said after class and practice on one's own, kept on the phone until the server has it. */
class OutboxTest {

    private class Memory : OutboxMemory {
        override var outbox: String? = null
    }

    /** A server that answers each envelope with the next of [answers] (a reply's text, or an error), keeping them. */
    private class Server(vararg answers: Any) : Exchange {
        val left = answers.toMutableList()
        val sent = mutableListOf<JSONObject>()
        override fun send(envelope: String): JSONObject {
            sent += JSONObject(envelope)
            return when (val next = left.removeAt(0)) {
                is ApiError -> throw next
                else -> JSONObject(next as String)
            }
        }
    }

    private val memory = Memory()
    private fun outbox(server: Server) = Outbox(Api({ "token-now" }, server) { }, memory)

    private fun items(id: String, session: Int = 7, token: String = "token-a") = PendingWrite(PendingWrite.AFTER_ITEMS, "$session",
        "/sessions/$session/practice", """{"entries": [{"item": "vajrasana", "reaction": 3, "pain": 0, "note": null}]}""", id, token)

    private val lost = ApiError("network")
    private val ok = """{"status": 200, "body": {"ok": true, "saved": 1}}"""

    @Test fun aWriteIsKeptOnThePhoneUntilItLandsAndSentAgainWithItsRequestId() {
        val down = Server(lost, lost, lost)
        outbox(down).add(items("after-1"))
        assertNull("no answer: kept for later", runBlocking { outbox(down).send(outbox(down).writes.single()) })
        val later = Server(ok)
        val again = outbox(later) // the app started again: the same memory
        assertEquals(listOf("after-1"), again.writes.map { it.requestId })
        assertEquals(1, runBlocking { again.send(again.writes.single()) }!!.getInt("saved"))
        assertEquals(listOf("after-1", "after-1", "after-1", "after-1"), (down.sent + later.sent).map { it.getString("request_id") })
        assertEquals("the login it was made with", listOf("token-a"), later.sent.map { it.getString("token") })
        assertEquals(emptyList<PendingWrite>(), outbox(Server()).writes)
    }

    @Test fun aRefusalDropsItAndSaysWhy() {
        val server = Server("""{"status": 400, "body": {"detail": "checkin_closed"}}""")
        val box = outbox(server)
        box.add(items("after-1"))
        val refused = try {
            runBlocking { box.send(box.writes.single()) }
            null
        } catch (e: ApiError) {
            e.code
        }
        assertEquals("checkin_closed", refused)
        assertTrue(box.writes.isEmpty())
        assertTrue(outbox(Server()).writes.isEmpty())
    }

    @Test fun aNewerWriteOfTheSameClassReplacesTheOneWaiting() {
        val box = outbox(Server())
        box.add(items("after-1"))
        box.add(items("solo-1").copy(kind = PendingWrite.SOLO, key = "123"))
        box.add(items("after-2"))
        box.add(items("after-3", session = 8))
        assertEquals(listOf("solo-1", "after-2", "after-3"), box.writes.map { it.requestId })
    }

    @Test fun anotherSignInKeepsNoneOfThem() {
        val box = outbox(Server())
        box.add(items("after-1"))
        box.add(items("after-2", session = 8, token = "token-b"))
        box.keepOnly("token-b")
        assertEquals(listOf("after-2"), box.writes.map { it.requestId })
        box.keepOnly(null)
        assertTrue(outbox(Server()).writes.isEmpty())
    }

    @Test fun aWriteLandingWhileANewerOneWaitsLeavesTheNewer() {
        val server = Server(ok)
        val box = outbox(server)
        box.add(items("after-1"))
        val first = box.writes.single()
        box.add(items("after-2")) // changed on the phone while the first was on its way
        runBlocking { box.send(first) }
        assertEquals(listOf("after-2"), box.writes.map { it.requestId })
    }
}
