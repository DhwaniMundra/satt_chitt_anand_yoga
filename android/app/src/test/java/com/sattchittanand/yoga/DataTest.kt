package com.sattchittanand.yoga

import org.json.JSONArray
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** The server's JSON as the app reads it: a cell the owner left empty or wrote words in never stops a screen. */
class DataTest {
    private fun json(text: String) = JSONObject(text)

    @Test fun aCurriculumWithAnEmptyOrWordedDoseShowsTheRest() {
        val c = Curricula.from(json("""{
            "library": [{"key": "tadasana", "type": "asana", "level": null, "sanskrit": "ताड़ासन", "name": "Tadasana", "english": null},
                        {"key": "omkar", "type": null, "sanskrit": "ओंकार", "name": "Omkar", "english": "Om", "aliases": ["om"]}],
            "curricula": [{"key": "beginner", "name": "Beginner", "about": null, "items": [
                {"item": "tadasana", "dose": null, "unit": "breaths", "cue": "Stand tall."},
                {"item": "omkar", "dose": 3, "unit": null, "cue": null},
                {"item": "omkar", "dose": "5"},
                {"item": "tadasana", "dose": 0, "unit": "breaths", "cue": "Slowly."},
                {"item": "omkar", "dose": 2, "dose_label": "2.5", "unit": "minutes", "cue": "Easy."}]},
              {"key": "empty", "name": null}]
        }"""))
        val items = c.find("beginner")!!.items
        assertEquals("0 is no count, as null is", listOf(null, 3, 5, null, 2), items.map { it.dose })
        assertEquals("a count that is not whole, as written", listOf(null, null, null, null, "2.5"), items.map { it.doseLabel })
        assertEquals(listOf("breaths", "", "", "breaths", "minutes"), items.map { it.unit })
        assertEquals(listOf("Stand tall.", "", "", "Slowly.", "Easy."), items.map { it.cue })
        assertEquals("", c.find("beginner")!!.about)
        assertEquals(emptyList<PlanItem>(), c.find("empty")!!.items)
        assertEquals("", c.library.getValue("tadasana").english)
        assertEquals(emptyList<String>(), c.library.getValue("tadasana").aliases)
        assertEquals(listOf("om"), c.library.getValue("omkar").aliases)
    }

    private val studio = """{"tagline": "Truth", "teacher": {"name": "Ramit", "title": null, "bio": "Teaches"}}"""
    private val user = """{"id": 2, "name": "Asha", "phone": "+919000000002", "role": "student", "status": "approved", "batch": "beginner", "batch_since": null}"""
    private fun session(id: Int, extra: String = "") =
        """{"id": $id, "starts_at": "2026-11-18T01:30:00Z", "duration_min": 55, "batch": {"key": "beginner", "name": "Beginner", "about": null, "time": "07:00"},
            "meet_link": null, "has_link": false$extra}"""

    @Test fun theTodayTabOffersTheClassToSayHowItWentEvenWithoutACheckIn() {
        val home = Home.from(json("""{"user": $user, "batch": null, "studio": $studio, "sessions": [${session(5, ", \"checked_in\": false")}],
            "after_checkin": null, "after_class": ${session(4, ", \"checked_in\": false, \"curriculum\": \"beginner\", \"said\": null")}, "group_link": null}"""))
        assertEquals(4, home.afterClass!!.id)
        assertFalse(home.afterClass.checkedIn)
        assertNull(home.afterSaid)
        assertEquals("", home.studio.teacherTitle)
        assertEquals(true, home.checkedIn(5, true).sessions.single().checkedIn)
        assertEquals("the class to say how it went too", true, home.checkedIn(4, true).afterClass!!.checkedIn)
    }

    @Test fun aCheckInNotYetConfirmedIsKeptWithItsRequestId() {
        val pending = listOf(PendingCheckin(5, 3, "a1", "token-a"), PendingCheckin(9, 5, "b2", "token-b"))
        assertEquals(pending, PendingCheckin.restore(PendingCheckin.saved(pending)))
        assertEquals(emptyList<PendingCheckin>(), PendingCheckin.restore(null))
        assertEquals(emptyList<PendingCheckin>(), PendingCheckin.restore("not json"))
    }

    @Test fun aServerWithoutAfterClassGivesTheClassCheckedInTo() {
        val home = Home.from(json("""{"user": $user, "batch": null, "studio": $studio, "sessions": [],
            "after_checkin": ${session(4, ", \"said\": {\"mood\": 4, \"items\": [{\"item\": \"tadasana\", \"reaction\": null, \"pain\": 1, \"note\": null}]}")},
            "group_link": "https://t.me/x"}"""))
        assertTrue(home.afterClass!!.checkedIn)
        assertEquals(Said(4, listOf(ItemFeedback("tadasana", null, true, ""))), home.afterSaid)
        assertEquals("https://t.me/x", home.groupLink)
    }

    @Test fun aClassSaidWithoutACheckInHasNoMoodBefore() {
        val c = JoinedClass.from(json("""{"date": "2026-11-18", "at": "2026-11-18T01:30:00Z", "class": "Beginner", "curriculum": null, "mood_before": null, "mood_after": 4}"""))
        assertNull(c.moodBefore)
        assertEquals(4, c.moodAfter)
    }

    @Test fun aClassReviewKeepsAStudentNoLongerInTheSheet() {
        val r = ClassReview.from(json("""{"curriculum": "beginner", "joined": 2, "answered": 2, "items": [{"item": "tadasana", "reactions": [0, 1, 0, 0],
            "pain": [{"note": "knee"}, {"name": "Meera", "note": null}], "notes": [{"name": null, "text": "Steady"}]}]}"""))
        assertEquals(listOf(null to "knee", "Meera" to null), r.items.single().pain)
        assertEquals(listOf(null to "Steady"), r.items.single().notes)
    }

    @Test fun theTeacherHomeWithTheGroupCodeClearedInTheSheet() {
        val t = TeacherHome.from(json("""{"sessions": [${session(1, ", \"own_link\": false, \"joined\": 0, \"curriculum\": \"beginner\"")}],
            "batches": [{"key": "beginner", "name": "Beginner", "about": "x", "days": [], "time": null, "meet_link": null}],
            "settings": {"group_link": null, "group_code": null}, "pending_students": 0}"""))
        assertNull(t.settings.groupCode)
        assertEquals("beginner", t.sessions.single().curriculum)
    }

    @Test fun theTeacherHomeWithTodaysClassesOverAndAClassTimeOfItsOwn() {
        val t = TeacherHome.from(json("""{"sessions": [${session(2, ", \"time_set\": true")}], "earlier": [${session(1, "")}],
            "batches": [], "settings": {}, "pending_students": 0}"""))
        assertEquals(listOf(2 to true), t.sessions.map { it.id to it.timeSet })
        assertEquals(listOf(1 to false), t.earlier.map { it.id to it.timeSet })
        val before = TeacherHome.from(json("""{"sessions": [], "batches": [], "settings": {}}"""))
        assertEquals("a server without them: none", emptyList<ClassSession>(), before.earlier)
    }

    @Test fun aRefusedInputIsNamedByItsField() {
        fun problem(text: String) = problemCode(JSONArray(text))
        assertEquals("too_long:pain_note:600", problem("""[{"type": "string_too_long", "loc": ["body", "pain_note"], "msg": "", "ctx": {"max_length": 600}}]"""))
        assertEquals("too_long:note:1000", problem("""[{"type": "string_too_long", "loc": ["body", "entries", 0, "note"], "ctx": {"max_length": 1000}}]"""))
        assertEquals("range:height_cm", problem("""[{"type": "less_than_equal", "loc": ["body", "height_cm"]}, {"type": "missing", "loc": ["body", "age"]}]"""))
        assertEquals("invalid:lang", problem("""[{"type": "literal_error", "loc": ["query", "lang"]}]"""))
        assertEquals("generic", problem("[]"))
    }

    @Test fun lengthsAreCountedInCodePointsAsTheServerCountsThem() {
        val hindi = "घुटने में दर्द" // Devanagari is all in the BMP: as many code points as chars
        assertEquals(14, hindi.codePointLength())
        assertEquals(14, hindi.length)
        assertEquals("घुटने", hindi.limitedTo(5))
        val faces = "🙂🙂🙂" // outside the BMP: two chars each, one code point each
        assertEquals(3, faces.codePointLength())
        assertEquals("🙂🙂", faces.limitedTo(2))
        assertEquals(hindi, hindi.limitedTo(600))
    }

    @Test fun aPracticeOnOnesOwnCarriesItsIdWhenTheServerGivesOne() {
        val o = json("""{"id": 7, "date": "2026-11-20", "at": "2026-11-20T03:00:00Z", "minutes": 20, "items": ["Vajrasana"]}""")
        assertEquals(7, SoloSession.from(o).id)
        o.remove("id")
        assertNull(SoloSession.from(o).id)
    }

    @Test fun theStopwatchStopsAtAnHour() {
        val start = 1_000_000L
        var run = SoloRun.start(listOf("vajrasana"), null, start).toggled(start)
        assertEquals(SoloRun.MAX_HOLD_MS, run.held(start + 2 * SoloRun.MAX_HOLD_MS))
        run = run.stopped(start + 2 * SoloRun.MAX_HOLD_MS)
        assertEquals(listOf(3600), run.entries().map { it.heldSeconds })
    }

    @Test fun aRunInProgressIsKeptAndRestoredAsTyped() {
        val start = 5_000L
        val run = SoloRun.start(listOf("vajrasana", "tadasana"), "beginner", start).toggled(start + 1_000)
            .changed(ItemFeedback("vajrasana", 3, true, "  knee ")).moved(1, start + 31_000).toggled(start + 40_000)
        val back = SoloRun.restore(run.saved())!!
        assertEquals(run, back)
        assertEquals(run.copy(startedAt = start - 12_000, runningSince = start + 28_000), back.shifted(-12_000))
        assertNull(SoloRun.restore("not json"))
        assertNull(SoloRun.restore("""{"started_at": 1, "at": 3, "held_ms": [0], "said": [{"item": "x"}]}"""))
    }
}
