package com.sattchittanand.yoga

import kotlinx.coroutines.runBlocking
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Signing up when the answer is lost: the same request id for each try, and with a server that does not answer a
 *  repeat as the first time, a login with the same number and password. */
class AccountsTest {

    /**
     * A studio's accounts. Each call does what [next] says, in turn ("run" when none is left): "run"; "lose", run but its
     * answer lost on the way back; "down", never arrives. With [replays], the server answers a sign-up or login repeated
     * with the same number and request id as it did the first time.
     */
    private class Studio(private val replays: Boolean = false) : Exchange {
        val passwords = mutableMapOf<String, String>()
        val roles = mutableMapOf<String, String>()
        val next = mutableListOf<String>()
        val sent = mutableListOf<JSONObject>()
        private val kept = mutableMapOf<String, JSONObject>()

        override fun send(envelope: String): JSONObject {
            val e = JSONObject(envelope)
            sent += e
            val how = if (next.isEmpty()) "run" else next.removeAt(0)
            if (how == "down") throw ApiError("network", unsent = true)
            val reply = run(e)
            if (how == "lose") throw ApiError("network")
            return reply
        }

        private fun run(e: JSONObject): JSONObject {
            val body = e.getJSONObject("body")
            val phone = phoneKey(body.getString("phone"))
            val key = "$phone ${e.optString("request_id")}"
            if (replays) kept[key]?.let { return it }
            val reply = when (e.getString("path")) {
                "/auth/signup" -> when {
                    body.getString("role") == "teacher" && "teacher" in roles.values -> answer(409, "teacher_exists")
                    phone in passwords -> answer(409, "phone_taken")
                    else -> {
                        passwords[phone] = body.getString("password")
                        roles[phone] = body.getString("role")
                        signedIn(phone)
                    }
                }
                "/auth/login" -> if (passwords[phone] == body.getString("password")) signedIn(phone) else answer(401, "bad_login")
                else -> answer(404, "Not Found")
            }
            if (replays && reply.getInt("status") == 200) kept[key] = reply
            return reply
        }

        private fun answer(status: Int, detail: String) = JSONObject().put("status", status).put("body", JSONObject().put("detail", detail))

        private fun signedIn(phone: String): JSONObject {
            val teacher = roles[phone] == "teacher"
            val user = JSONObject().put("id", passwords.keys.indexOf(phone) + 1).put("name", "Test").put("phone", phone).put("role", roles[phone])
                .put("status", if (teacher) "approved" else "pending")
            return JSONObject().put("status", 200).put("body", JSONObject().put("token", "token-$phone-${sent.size}").put("user", user))
        }

        fun paths() = sent.map { it.getString("path") }
    }

    private class Memory : SignupMemory {
        override var lostSignup: String? = null
    }

    private var clock = 1_000_000L
    private val memory = Memory()
    private fun accounts(studio: Studio) = Accounts(Api({ null }, studio) { }, memory) { clock }

    private fun form(phone: String = "98000 00104", password: String = "pilot123", role: String = "student") =
        JSONObject().put("name", "Kavya").put("phone", phone).put("password", password).put("role", role).put("code", "GRP1").put("lang", "en")

    private fun signup(studio: Studio, body: JSONObject = form(), id: String = "tap-1") = runBlocking { accounts(studio).signup(body, id) }

    private fun refused(block: () -> Unit): String = try {
        block()
        "none"
    } catch (e: ApiError) {
        e.code
    }

    @Test fun aSignUpWhoseAnswerIsLostLogsInWithTheSameNumberAndPassword() {
        val studio = Studio().apply { next += "lose" }
        val account = signup(studio)
        assertEquals(listOf("/auth/signup", "/auth/signup", "/auth/login"), studio.paths())
        assertEquals("each try of the tap carries its request id", listOf("tap-1", "tap-1"), studio.sent.take(2).map { it.getString("request_id") })
        assertEquals("98000 00104", studio.sent.last().getJSONObject("body").getString("phone"))
        assertEquals("pilot123", studio.sent.last().getJSONObject("body").getString("password"))
        assertTrue("so the intake opens", account.newStudent)
        assertEquals(1, studio.passwords.size)
        assertNull(memory.lostSignup)
    }

    @Test fun aServerThatReplaysAnswersTheRepeatItself() {
        val studio = Studio(replays = true).apply { next += "lose" }
        val account = signup(studio)
        assertEquals(listOf("/auth/signup", "/auth/signup"), studio.paths())
        assertEquals("token-+919800000104-1", account.token)
        assertTrue(account.newStudent)
    }

    @Test fun aNumberThatHasAnAccountIsRefusedAsBeforeWhenNoSignUpWasLost() {
        val studio = Studio().apply { passwords["+919800000104"] = "pilot123"; roles["+919800000104"] = "student" }
        assertEquals("phone_taken", refused { signup(studio) })
        assertEquals(listOf("/auth/signup"), studio.paths())
    }

    @Test fun aLostSignUpOfANumberWhoseAccountIsSomeoneElsesStaysRefused() {
        val studio = Studio().apply { passwords["+919800000104"] = "theirs"; roles["+919800000104"] = "student" }
        memory.lostSignup = "+919800000104 ${clock - 60_000}"
        assertEquals("phone_taken", refused { signup(studio) })
        assertEquals(listOf("/auth/signup", "/auth/login"), studio.paths())
        assertNull(memory.lostSignup)
    }

    @Test fun aLostSignUpIsKeptOnThePhoneForTheNextStartAndForTenMinutes() {
        val studio = Studio().apply { next += listOf("lose", "down", "down") }
        assertEquals("network", refused { signup(studio) })
        assertEquals(1, studio.passwords.size) // made, though the phone never heard
        clock += 9 * 60_000L
        val account = signup(studio, id = "tap-2") // the app started again: a new Accounts, the same memory
        assertEquals(listOf("/auth/signup", "/auth/login"), studio.paths().drop(3))
        assertTrue(account.newStudent)

        val later = Studio().apply { next += listOf("lose", "down", "down") }
        memory.lostSignup = null
        assertEquals("network", refused { signup(later, id = "tap-3") })
        clock += 11 * 60_000L
        assertEquals("too long ago", "phone_taken", refused { signup(later, id = "tap-4") })
    }

    @Test fun anotherNumberIsNotTheLostOne() {
        val studio = Studio().apply { passwords["+919800000105"] = "pilot123"; roles["+919800000105"] = "student" }
        memory.lostSignup = "+919800000104 $clock"
        assertEquals("phone_taken", refused { signup(studio, form(phone = "9800000105")) })
        assertEquals(listOf("/auth/signup"), studio.paths())
    }

    @Test fun theTeachersLostSignUpLogsInToo() {
        val studio = Studio().apply { next += "lose" }
        val account = signup(studio, form(phone = "9800000101", role = "teacher"))
        assertEquals(listOf("/auth/signup", "/auth/signup", "/auth/login"), studio.paths())
        assertTrue(account.user.isTeacher)
        assertFalse(account.newStudent)
    }

    @Test fun aLoginIsTriedAgainWithItsRequestId() {
        val studio = Studio().apply { passwords["+919800000102"] = "pilot123"; roles["+919800000102"] = "student"; next += "lose" }
        val account = runBlocking { accounts(studio).login("9800000102", "pilot123", "login-1") }
        assertEquals(listOf("login-1", "login-1"), studio.sent.map { it.getString("request_id") })
        assertFalse(account.newStudent)
    }

    @Test fun numbersAreReadAsTheServerReadsThem() {
        for (typed in listOf("98765 43210", "098765 43210", "+91 98765 43210", "+91 098765 43210", "0091 98765 43210", "९८७६५ ४३२१०")) {
            assertEquals(typed, "+919876543210", phoneKey(typed))
        }
        assertEquals("+16505550123", phoneKey("+1 (650) 555-0123"))
    }

    @Test fun numbersShowGroupedForTheTeacher() {
        assertEquals("+91 98000 00001", formatPhone("+919800000001"))
        assertEquals("+1 650 555 0123", formatPhone("+16505550123"))
        assertEquals("+447700900123", formatPhone("+447700900123"))
        assertEquals("98000 00001", formatPhone("98000 00001"))
    }
}
