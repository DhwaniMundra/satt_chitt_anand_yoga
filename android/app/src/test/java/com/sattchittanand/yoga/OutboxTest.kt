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

    /** A server that answers every envelope with [answer]'s next. */
    private class Always(val answer: (Int) -> Any) : Exchange {
        var calls = 0
        override fun send(envelope: String): JSONObject = when (val next = answer(calls++)) {
            is ApiError -> throw next
            else -> JSONObject(next as String)
        }
    }

    private val memory = Memory()
    private fun outbox(server: Exchange) = Outbox(Api({ "token-now" }, server) { }, memory)

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
        assertEquals("landed, it is kept to show, and sent no more", listOf(true to false), outbox(Server()).writes.map { it.landed to it.waiting })
    }

    @Test fun theServerFailingOverAndOverGivesItUpButBusyAndNoAnswerDoNot() {
        val passing = outbox(Always { if (it % 3 == 0) ApiError("busy", 503) else if (it % 3 == 1) lost else ApiError("server") })
        passing.add(items("after-1"))
        repeat(20) { assertNull(runBlocking { passing.send(passing.writes.single()) }) }
        assertEquals("busy, no answer or a page that is no reply count for nothing", 0, passing.writes.single().failures)
        val failing = outbox(Always { """{"status": 500, "body": {"detail": "Internal Server Error"}}""" })
        repeat(Outbox.GIVE_UP_AFTER - 1) { assertNull(runBlocking { failing.send(failing.writes.single()) }) }
        assertEquals("counted, and kept on the phone", Outbox.GIVE_UP_AFTER - 1, outbox(Server()).writes.single().failures)
        val given = try {
            runBlocking { failing.send(failing.writes.single()) }
            null
        } catch (e: ApiError) {
            e.code
        }
        assertEquals("gave_up", given)
        assertTrue(failing.writes.isEmpty())
    }

    @Test fun aRefusedPracticeIsKeptAsideWithItsReasonAndNotSent() {
        val box = outbox(Server())
        val solo = items("solo-1").copy(kind = PendingWrite.SOLO, key = "123", path = "/me/solo")
        box.add(solo.copy(refused = "unknown_item"))
        val kept = outbox(Server()).writes.single()
        assertEquals("unknown_item" to false, kept.refused to kept.waiting)
        box.change(kept) { it.copy(shown = """{"x": 1}""") }
        assertEquals("""{"x": 1}""", outbox(Server()).writes.single().shown)
        box.drop { it.refused != null }
        assertTrue(outbox(Server()).writes.isEmpty())
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
        assertEquals(listOf("after-2" to true), box.writes.map { it.requestId to it.waiting })
    }
}
