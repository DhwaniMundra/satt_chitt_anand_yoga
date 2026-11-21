package com.sattchittanand.yoga

import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.time.Instant

/** The first screens kept on the phone: for one sign-in and one language, gone at sign-out, shown as they stand now. */
class SavedScreensTest {
    private val dir: File = Files.createTempDirectory("saved").toFile()
    private val file = File(dir, "saved_screens.json")
    private fun json(text: String) = JSONObject(text)

    @Test fun whatWasKeptOpensForTheSameSignInAndLanguageOnly() {
        val saved = SavedScreens(file)
        saved.keep("token-a", "en", SavedScreens.ME, json("""{"user": {"id": 2}}"""), at = 1_000)
        saved.keep("token-a", "en", SavedScreens.DAY, json("""{"sessions": []}"""), at = 2_000)
        val kept = SavedScreens(file).read("token-a", "en")!! // as the next start reads it
        assertEquals(2, kept.me!!.getJSONObject("user").getInt("id"))
        assertEquals(0, kept.day!!.getJSONArray("sessions").length())
        assertNull(kept.curricula)
        assertEquals("when the day was read", 2_000L, kept.at)
        assertNull("another sign-in", saved.read("token-b", "en"))
        assertNull("another language", saved.read("token-a", "hi"))
        assertFalse("the token itself is not kept", file.readText().contains("token-a"))
    }

    @Test fun anotherSignInReplacesItAndSignOutClearsIt() {
        val saved = SavedScreens(file)
        saved.keep("token-a", "en", SavedScreens.DAY, json("""{"who": "a"}"""), at = 1)
        saved.keep("token-b", "en", SavedScreens.ME, json("""{"who": "b"}"""), at = 2)
        assertNull("the first sign-in's day is gone", saved.read("token-a", "en"))
        assertNull(saved.read("token-b", "en")!!.day)
        saved.clear()
        assertNull(saved.read("token-b", "en"))
        assertFalse(file.exists())
    }

    @Test fun aDamagedFileOpensOnNothing() {
        file.writeText("{not json")
        assertNull(SavedScreens(file).read("token-a", "en"))
    }

    private val studio = """{"tagline": "Truth", "teacher": {"name": "Ramit", "title": "Teacher", "bio": ""}}"""
    private val user = """{"id": 2, "name": "Asha", "phone": "+919000000002", "role": "student", "status": "approved", "batch": "beginner", "batch_since": null}"""
    private fun session(id: Int, startsAt: String) =
        """{"id": $id, "starts_at": "$startsAt", "duration_min": 55, "batch": {"key": "beginner", "name": "Beginner", "about": null, "time": "07:00"},
            "meet_link": "https://meet.google.com/abc-defg-hij", "has_link": true}"""

    /** A day kept yesterday shows at today's open without the classes that have ended, nor a class to say how it went
     *  whose time for that has passed. */
    @Test fun aKeptDayShowsAsItStandsNow() {
        val home = Home.from(json("""{"user": $user, "batch": null, "studio": $studio,
            "sessions": [${session(5, "2026-11-19T01:30:00Z")}, ${session(6, "2026-11-20T01:30:00Z")}],
            "after_class": ${session(4, "2026-11-18T01:30:00Z").dropLast(1)}, "checked_in": true, "said": {"mood": 4, "items": []}}, "group_link": null}"""))
        val thursdayNoon = Instant.parse("2026-11-19T06:30:00Z") // noon in India: class 5 ended, class 6 is tomorrow
        val now = home.at(thursdayNoon)
        assertEquals(listOf(6), now.sessions.map { it.id })
        assertNull("Wednesday's class closed 12 hours after it", now.afterClass)
        assertNull(now.afterSaid)
        val wednesdayEvening = Instant.parse("2026-11-18T12:00:00Z")
        assertEquals(4, home.at(wednesdayEvening).afterClass!!.id)
        assertTrue(home.at(wednesdayEvening).afterSaid != null)
    }
}
