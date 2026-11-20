package com.sattchittanand.yoga

import org.json.JSONObject

/** Where [Accounts] keeps a sign-up whose answer never came: on the phone, so it outlasts the app being closed. */
interface SignupMemory {
    var lostSignup: String?
}

/**
 * Logging in and signing up. Each tap sends one request id with all its tries, so a server that keeps the answer to a
 * sign-up or a login by its number and request id gives a repeat the first answer. For a server that does not: a
 * sign-up whose answer never came may have made the account, and the next try then hears that the number has one. So
 * such a sign-up is kept for [LOST_MS], and "this number already has an account" for the same number within that time
 * logs in with the same number and password instead, as the sign-up did go through. If that password does not fit, the
 * account is someone else's, and the refusal stands.
 */
class Accounts(private val api: Api, private val memory: SignupMemory, private val now: () -> Long = System::currentTimeMillis) {

    /** An account signed in to; [newStudent] for a student who has just signed up, to be asked about themselves. */
    class SignedIn(val token: String, val user: User, val newStudent: Boolean)

    suspend fun login(phone: String, password: String, requestId: String = newRequestId()): SignedIn =
        signedIn(api.post("/auth/login", credentials(phone, password), requestId), newStudent = false)

    /** Signs up with [body]: name, phone, password, role, code and language. */
    suspend fun signup(body: JSONObject, requestId: String): SignedIn {
        val number = phoneKey(body.getString("phone"))
        var mayExist = false
        val tries = object : Tries {
            override fun sending() {
                mayExist = mayExist || lostBefore(number)
                memory.lostSignup = "$number ${now()}"
            }

            // Kept unless this try was answered, or did nothing and no earlier one was lost.
            override fun ended(error: ApiError?) {
                if (error == null || error.nothingDone && !mayExist) memory.lostSignup = null
            }
        }
        try {
            return signedIn(api.post("/auth/signup", body, requestId, tries = tries), newStudent = true)
        } catch (e: ApiError) {
            if (e.code !in TAKEN || !mayExist) throw e
            val found = try {
                api.post("/auth/login", credentials(body.getString("phone"), body.getString("password")), newRequestId())
            } catch (refused: ApiError) {
                if (refused.code != "bad_login") throw refused // kept, for the next tap to log in again
                memory.lostSignup = null
                throw e
            }
            memory.lostSignup = null
            val user = User.from(found.getJSONObject("user"))
            return SignedIn(found.getString("token"), user, newStudent = !user.isTeacher && !user.isApproved)
        }
    }

    private fun credentials(phone: String, password: String) = JSONObject().put("phone", phone).put("password", password)

    private fun signedIn(reply: JSONObject, newStudent: Boolean): SignedIn {
        val user = User.from(reply.getJSONObject("user"))
        return SignedIn(reply.getString("token"), user, newStudent && !user.isTeacher)
    }

    /** Whether a sign-up of [number] went out within [LOST_MS] and no answer to it came. */
    private fun lostBefore(number: String): Boolean {
        val (kept, at) = memory.lostSignup?.split(' ')?.takeIf { it.size == 2 } ?: return false
        val since = now() - (at.toLongOrNull() ?: return false)
        return kept == number && since in 0..LOST_MS
    }

    companion object {
        const val LOST_MS = 10 * 60_000L
        /** What a repeated sign-up hears: the number has an account, or (the teacher's) the studio has its teacher. */
        private val TAKEN = setOf("phone_taken", "teacher_exists")
    }
}

/** A phone number as the server reads it, "+<country><number>": a bare 10-digit number, or one with the trunk 0 (or
 *  "0" after +91), is Indian; "00" starts an international number. Devanagari digits count. For telling whether two
 *  numbers typed are the same. */
fun phoneKey(typed: String): String {
    var digits = typed.filter { it.isDigit() }.map { Character.digit(it, 10) }.joinToString("")
    if (digits.startsWith("00")) digits = digits.drop(2)
    else if (digits.length == 11 && digits.startsWith("0")) digits = digits.drop(1)
    if (digits.length == 13 && digits.startsWith("910")) digits = "91" + digits.drop(3)
    if (digits.length == 10) digits = "91$digits"
    return "+$digits"
}

/** A stored number as people read it: "+91 98000 00001", "+1 650 555 0123"; any other as it is stored. */
fun formatPhone(stored: String): String {
    val digits = stored.removePrefix("+")
    if (digits == stored || digits.any { it !in '0'..'9' }) return stored
    return when {
        digits.length == 12 && digits.startsWith("91") -> "+91 ${digits.substring(2, 7)} ${digits.substring(7)}"
        digits.length == 11 && digits.startsWith("1") -> "+1 ${digits.substring(1, 4)} ${digits.substring(4, 7)} ${digits.substring(7)}"
        else -> stored
    }
}
