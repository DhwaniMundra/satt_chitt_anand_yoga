package com.sattchittanand.yoga.companion

import com.sattchittanand.yoga.JoinedClass
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant
import java.time.LocalDate

/** The companion's conversation without the model: what Gemma is handed up front, its tools and the "Remember that…"
 *  rule. */
class CompanionTest {
    private val companion = PracticeCompanion(NOTES, "Satt Chitt Anand Yoga", "Ramit ji")
    private val now = Instant.parse("2026-11-19T02:00:00Z") // Thursday 19 November, 7:30 in India

    /** The server, as the tools see it, with a fixed week of classes. */
    private class Server(val classes: List<UpcomingClass>, val reachable: Boolean = true) : StudentData {
        val saved = mutableListOf<String>()
        var practiceAsked: Pair<Int, String>? = null
        override fun practice(days: Int, lang: String): Map<String, Any?> {
            if (!reachable) error("no network")
            practiceAsked = days to lang
            return linkedMapOf("period_days" to days, "classes_joined" to 3)
        }
        override fun upcoming(lang: String): List<UpcomingClass> = if (reachable) classes else error("no network")
        override fun saveNote(text: String) { saved += text }
        override fun notes() = saved.map { KeptNote(it, Instant.parse("2026-11-18T08:00:00Z")) }
    }

    private val week = listOf(
        UpcomingClass(Instant.parse("2026-11-19T02:30:00Z"), "Dhyana · Meditation", "All levels", "Seated stillness."),
        UpcomingClass(Instant.parse("2026-11-20T02:30:00Z"), "Hatha Yoga", "All levels", "Classical postures."),
        UpcomingClass(Instant.parse("2026-11-21T02:30:00Z"), "Yoga Nidra", "All levels", "Deep relaxation."),
        UpcomingClass(Instant.parse("2026-11-22T02:30:00Z"), "Satsang · Open Practice", "All levels", "Sunday gathering."),
        UpcomingClass(Instant.parse("2026-11-23T02:30:00Z"), "Hatha Yoga", "All levels", "Classical postures."),
        UpcomingClass(Instant.parse("2026-11-24T02:30:00Z"), "Pranayama", "All levels", "Breathwork."),
    )

    private fun tools(server: StudentData = Server(week), lang: String = "en") = Tools(server, NOTES, lang) { now }

    @Test fun matchingNotesAreHandedOverUpFront() {
        val used = mutableListOf<String>()
        assertTrue("पाठीवर" in companion.preloadedNotes("पाठदुखीसाठी योग?", "mr", used))
        assertEquals(listOf("search_studio_notes"), used)
        assertEquals("", companion.preloadedNotes("How was my practice this week?", "en", mutableListOf()))
        assertTrue("### Pregnancy" in companion.preloadedNotes("I am pregnant, can I join?", "en", mutableListOf()))
        assertTrue("### Diabetes" in companion.preloadedNotes("Can I lower my metformin dose?", "en", mutableListOf()))
        // With the schedule handed over, "class" names no topic of its own; "back" still does.
        assertEquals("", companion.preloadedNotes("कल कौन सी कक्षा है?", "hi", mutableListOf(), schedule = true))
        assertTrue("### Back pain" in companion.preloadedNotes("My lower back is stiff. Which class tomorrow?", "en", mutableListOf(), schedule = true))
        // Matches on words of a section's text only, not its topic: no notes, and no "Read the studio notes".
        for (message in listOf("How many classes did I join in the last 30 days?", "Do I usually feel better after class than before?",
            "What did I tell you about my knee?")) assertEquals(message, "", companion.preloadedNotes(message, "en", mutableListOf()))
    }

    @Test fun theNotesSectionReadsAsOnTheServer() {
        assertTrue(companion.preloadedNotes("Yoga for back pain?", "en", mutableListOf()).startsWith(
            "\n\nThe studio's notes on what the student asks about. Answer from them:\n### Back pain\n- Gentle movement often helps every"))
    }

    @Test fun aMessageAboutClassesGetsTheScheduleWithUnambiguousDays() {
        val t = tools()
        val system = companion.system("Asha", "Which class suits me tomorrow?", "en", t)
        assertTrue(system, "Today is Thursday 19 November. The studio's coming classes. Answer from them:\n" +
            "- today, Thursday 19 November: Dhyana · Meditation at 8:00 AM India time (All levels)\n" +
            "- tomorrow, Friday 20 November: Hatha Yoga at 8:00 AM India time (All levels)\n" +
            "- Saturday 21 November: Yoga Nidra at 8:00 AM India time (All levels)" in system)
        assertFalse("Pranayama" in system) // the next five classes only
        assertFalse("### About the studio and classes" in system)
        assertEquals(listOf("get_upcoming_classes"), t.used)
        assertTrue(system.startsWith("You are the practice companion in the Satt Chitt Anand Yoga app, talking with one student, Asha."))
        assertTrue(system.contains("tell\n   Ramit ji before class") && system.contains("6. Reply only in English."))
    }

    @Test fun otherMessagesGetNoSchedule() {
        val t = tools()
        val system = companion.system("Asha", "How was my practice this week?", "hi", t)
        assertFalse("Today is" in system)
        assertTrue(system.endsWith("6. Reply only in Hindi (हिन्दी, Devanagari script)."))
        assertEquals(emptyList<String>(), t.used)
    }

    /** Without the schedule, a class word names a notes topic again. */
    @Test fun noScheduleWhenTheServerCannotBeReached() {
        val t = tools(Server(week, reachable = false))
        val system = companion.system("Asha", "Which class tomorrow?", "en", t)
        assertFalse("Today is" in system)
        assertTrue("### Getting ready for an online class" in system)
        assertEquals(listOf("search_studio_notes"), t.used)
    }

    @Test fun toolsReturnTheServersSummaryAndTheNotesInTheStudentsLanguage() {
        val server = Server(week)
        val t = tools(server, "mr")
        assertEquals(3, t.getMyPractice(7)["classes_joined"])
        assertEquals(7 to "mr", server.practiceAsked)
        t.getMyPractice(400)
        assertEquals(90 to "mr", server.practiceAsked) // at most 90 days
        @Suppress("UNCHECKED_CAST")
        val notes = t.searchStudioNotes("back pain")["notes"] as List<Map<String, String>>
        assertEquals("Back pain", notes.first()["title"])
        assertTrue("पाठीवर" in notes.first().getValue("text")) // the Marathi notes for Marathi
        assertEquals(mapOf("saved" to true), t.saveMyNote("left knee hurts in Vajrasana"))
        assertEquals(mapOf("notes" to listOf(mapOf("note" to "left knee hurts in Vajrasana", "saved" to "2026-11-18"))), t.getMyNotes())
        assertEquals(listOf("get_my_practice", "get_my_practice", "search_studio_notes", "save_my_note", "get_my_notes"), t.used)
    }

    @Test fun aToolSaysSoWhenTheServerCannotBeReached() {
        val t = tools(Server(week, reachable = false))
        assertTrue(t.getMyPractice(7).containsKey("error"))
        assertTrue(t.getUpcomingClasses().containsKey("error"))
    }

    @Test fun theToolsKeepTheirNamesAndOrder() {
        val names = tools().toolSets().map { set -> set.javaClass.declaredMethods.single { it.name.startsWith("get_") || it.name.startsWith("s") }.name }
        assertEquals(listOf("get_my_practice", "get_upcoming_classes", "search_studio_notes", "save_my_note", "get_my_notes"), names)
    }

    @Test fun theWordsTheAppTeachesForSaving() {
        assertEquals("मेरे घुटने में दर्द है", noteToSave("याद रखना कि मेरे घुटने में दर्द है", emptyList()))
        assertEquals("माझा गुडघा दुखतो", noteToSave("कृपया लक्षात ठेवा की माझा गुडघा दुखतो", emptyList()))
        assertEquals("My left knee hurts in Vajrasana.", noteToSave("Please remember that my left knee hurts in Vajrasana.", emptyList()))
        assertNull(noteToSave("Do you remember that my knee hurts?", emptyList())) // asking, not telling
        assertNull(noteToSave("What did I tell you about my knee?", emptyList()))
        assertNull(noteToSave("Remember that my knee hurts", listOf("save_my_note"))) // Gemma saved it: not twice
    }

    @Test fun aPracticeDayIsTheLatestDateWithThatWeekday() {
        val today = LocalDate.of(2026, 1, 5) // a Monday
        assertEquals(LocalDate.of(2026, 1, 2), JoinedClass.pastDate("Fri 02 Jan", today))
        assertEquals(LocalDate.of(2025, 12, 29), JoinedClass.pastDate("Mon 29 Dec", today)) // 29 Dec 2026 is a Tuesday
        assertNull(JoinedClass.pastDate("Tue 06 Jan", today)) // tomorrow, not a class already joined
    }
}
