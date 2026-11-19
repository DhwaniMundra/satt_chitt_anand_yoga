package com.sattchittanand.yoga.companion

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.time.Instant

/** The companion's conversation without the model: what Gemma is handed up front, its tools and the "Remember that…"
 *  rule. */
class CompanionTest {
    private val companion = PracticeCompanion(NOTES, "Lotus Yoga", "Teacher One")
    private val now = Instant.parse("2026-11-19T02:00:00Z") // Thursday 19 November, 7:30 in India

    /** The server, as the tools see it, with a fixed week of classes. */
    private companion object {
        val LIBRARY = listOf(
            ItemName("vajrasana", "वज्रासन", "Vajrasana", "Thunderbolt pose", listOf("vajrasan", "vajra", "kneeling pose")),
            ItemName("ardha_matsyendrasana", "अर्धमत्स्येन्द्रासन", "Ardha Matsyendrasana", "Half spinal twist", emptyList()),
            ItemName("matsyasana", "मत्स्यासन", "Matsyasana", "Fish pose", emptyList()),
            ItemName("setu_bandhasana", "सेतुबन्धासन", "Setu Bandhasana", "Bridge pose", listOf("bridge")),
            ItemName("shashankasana", "शशांकासन", "Shashankasana", "Hare pose", listOf("child's pose", "balasana")),
            ItemName("dhyana", "ध्यान", "Dhyana", "Meditation", emptyList()),
        )
        val VAJRASANA: Map<String, Any?> = linkedMapOf(
            "item" to "vajrasana", "in_class" to 9, "solo" to 5, "first" to "2026-10-30", "last" to "2026-11-17",
            "reaction_trend" to linkedMapOf("early_average" to 2.0, "recent_average" to 3.7, "each" to 3),
            "holds" to linkedMapOf("recent_seconds" to 120, "longest_seconds" to 120),
            "strain_or_pain" to linkedMapOf("times" to 6, "last" to "2026-11-10"),
            "teacher_said" to linkedMapOf("date" to "2026-11-16", "text" to "Much steadier this week."),
            "your_notes" to listOf(linkedMapOf("date" to "2026-11-14", "text" to "Cushion helped")),
            "entries" to emptyList<Any>(), "feedback" to emptyList<Any>(),
        )
    }

    private class Server(val classes: List<UpcomingClass>, val reachable: Boolean = true) : StudentData {
        val saved = mutableListOf<String>()
        var practiceAsked: Pair<Int, String>? = null
        override fun practice(days: Int, lang: String): Map<String, Any?> {
            if (!reachable) error("no network")
            practiceAsked = days to lang
            return linkedMapOf("period_days" to days, "classes_joined" to 3, "average_mood_before" to 3.0, "average_mood_after" to 4.0,
                "classes" to listOf(linkedMapOf("date" to "2026-11-16", "class" to "Intermediate", "mood_before" to 3, "mood_after" to 4)),
                "solo" to listOf(linkedMapOf("date" to "2026-11-17", "minutes" to 20, "items" to listOf("Vajrasana"))),
                "top_items" to listOf(linkedMapOf("asana" to "Vajrasana", "times" to 4, "average_reaction" to 2.5, "pain_times" to 1)))
        }
        override fun upcoming(lang: String): List<UpcomingClass> = if (reachable) classes else error("no network")
        override fun saveNote(text: String) { saved += text }
        override fun notes() = saved.map { KeptNote(it, Instant.parse("2026-11-18T08:00:00Z")) }
        override fun library() = LIBRARY
        override fun itemProgress(key: String): Map<String, Any?> = if (!reachable) error("no network") else VAJRASANA
    }

    private val week = listOf(
        UpcomingClass(Instant.parse("2026-11-19T02:30:00Z"), "Intermediate", "For a steady practice."),
        UpcomingClass(Instant.parse("2026-11-20T02:30:00Z"), "Intermediate", "For a steady practice."),
        UpcomingClass(Instant.parse("2026-11-21T02:30:00Z"), "Intermediate", "For a steady practice."),
        UpcomingClass(Instant.parse("2026-11-23T02:30:00Z"), "Intermediate", "For a steady practice."),
        UpcomingClass(Instant.parse("2026-11-24T02:30:00Z"), "Intermediate", "For a steady practice."),
        UpcomingClass(Instant.parse("2026-11-25T02:30:00Z"), "Intermediate", "For a steady practice."),
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
        assertTrue(system, "Today is Thursday 19 November. This student's coming classes, in their batch. Answer from them:\n" +
            "- today, Thursday 19 November: Intermediate at 8:00 AM India time\n" +
            "- tomorrow, Friday 20 November: Intermediate at 8:00 AM India time\n" +
            "- Saturday 21 November: Intermediate at 8:00 AM India time\n" +
            "- Monday 23 November: Intermediate at 8:00 AM India time" in system)
        assertFalse("Wednesday 25 November" in system) // the next five classes only
        assertFalse("### About the studio and classes" in system)
        assertEquals(listOf("get_upcoming_classes"), t.used)
        assertTrue(system.startsWith("You are the practice companion in the Lotus Yoga app, talking with one student, Asha."))
        assertTrue(system.contains("tell\n   Teacher One before class") && system.contains("6. Reply only in English."))
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
        val week = t.getMyPractice(7)
        assertEquals(3, week["classes_joined"])
        assertEquals(listOf(3.0, 4.0, null), listOf(week["average_class_mood_before"], week["average_class_mood_after"], week["average_mood_after"]))
        assertEquals(listOf("Monday 16 November"), (week["classes"] as List<*>).map { (it as Map<*, *>)["date"] }) // the weekday written out
        assertEquals(listOf("Tuesday 17 November"), (week["solo"] as List<*>).map { (it as Map<*, *>)["date"] })
        assertEquals(listOf("2.5, between with effort and steady"), (week["top_items"] as List<*>).map { (it as Map<*, *>)["average_reaction"] })
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
        val names = tools().toolSets().map { set -> set.javaClass.declaredMethods.single { it.name.matches(Regex("(get|search|save|asana)_.*")) }.name }
        assertEquals(listOf("get_my_practice", "asana_progress", "get_upcoming_classes", "search_studio_notes", "save_my_note", "get_my_notes"), names)
    }

    @Test fun theWordsTheAppTeachesForSaving() {
        assertEquals("मेरे घुटने में दर्द है", noteToSave("याद रखना कि मेरे घुटने में दर्द है", emptyList()))
        assertEquals("माझा गुडघा दुखतो", noteToSave("कृपया लक्षात ठेवा की माझा गुडघा दुखतो", emptyList()))
        assertEquals("My left knee hurts in Vajrasana.", noteToSave("Please remember that my left knee hurts in Vajrasana.", emptyList()))
        assertNull(noteToSave("Do you remember that my knee hurts?", emptyList())) // asking, not telling
        assertNull(noteToSave("What did I tell you about my knee?", emptyList()))
        assertNull(noteToSave("Remember that my knee hurts", listOf("save_my_note"))) // Gemma saved it: not twice
    }

    @Test fun aNameIsFoundHoweverItIsWritten() {
        for (asked in listOf("Vajrasana", "vajrasan", "vajra", "Vajrāsana", "वज्रासन", "वज्र आसन", "thunderbolt pose", "Thunderbolt", "VAJRASANA POSE")) {
            assertEquals(asked, "vajrasana", resolveItem(asked, LIBRARY))
        }
        assertEquals("shashankasana", resolveItem("child's pose", LIBRARY))
        assertEquals("setu_bandhasana", resolveItem("setu bandha", LIBRARY))
        assertEquals("matsyasana", resolveItem("matsyasana", LIBRARY)) // not the half spinal twist, whose name contains it
        assertEquals("matsyasana", resolveItem("matsy", LIBRARY)) // its name without "asana"
        assertEquals(null, resolveItem("s", LIBRARY)) // the start of several names: not one item
        assertEquals(null, resolveItem("lotus", LIBRARY))
        assertEquals("Shashankasana", closestItems("shash", LIBRARY).first())
    }

    @Test fun asanaProgressGivesTheSumsWithWeekdaysAndTheTeachersWord() {
        val t = tools()
        val p = t.asanaProgress("वज्रासन")
        assertEquals("Vajrasana (वज्रासन, Thunderbolt pose)", p["asana"])
        assertEquals(listOf(9, 5), listOf(p["times_in_class"], p["times_on_own"]))
        assertEquals("Friday 30 October", p["first"])
        assertEquals(mapOf("first 3 times" to "2.0, with effort", "last 3 times" to "3.7, between steady and at ease"), p["how_it_felt"])
        assertEquals(listOf("1.0, not yet", "2.5, between with effort and steady", "4.0, at ease"), listOf(1, 2.5, 4.0).map(::reactionWords))
        assertEquals(mapOf("date" to "Monday 16 November", "text" to "Much steadier this week."), p["teacher_said"])
        assertEquals(mapOf("times" to 6, "last" to "Tuesday 10 November"), p["strain_or_pain"])
        assertEquals(listOf("asana_progress"), t.used)
        assertTrue(t.asanaProgress("lotus")["error"].toString().startsWith("Nothing called \"lotus\" is in the studio's list."))
        assertEquals(mapOf("error" to "The studio server could not be reached just now, so this is not available."),
            tools(Server(week, reachable = false)).asanaProgress("vajrasana"))
    }

    @Test fun aMessageAboutOnesOwnAsanaGetsItsProgressUpFront() {
        for ((message, lang) in listOf("How has my Vajrasana been?" to "en", "मेरा वज्रासन कैसा चल रहा है?" to "hi", "माझे वज्रासन कसे चालले आहे?" to "mr")) {
            val t = tools(lang = lang)
            val system = companion.system("Asha", message, lang, t)
            assertTrue(message, "How Vajrasana (वज्रासन, Thunderbolt pose) has gone for this student (asana_progress)" in system)
            assertTrue("- teacher_said: {date=Monday 16 November, text=Much steadier this week.}" in system)
            assertEquals(listOf("asana_progress"), t.used)
        }
        val general = tools()
        assertFalse("not about their own practice", "(asana_progress). Answer from it" in companion.system("Asha", "Is meditation good for sleep?", "en", general))
        assertFalse("asana_progress" in general.used)
        val keep = tools()
        companion.system("Asha", "Remember that my left knee hurts in Vajrasana", "en", keep)
        assertFalse("a note to keep, not a question", "asana_progress" in keep.used)
    }

    @Test fun theSystemMessageNamesTheStudentsBatch() {
        assertTrue("Asha practises in the Intermediate batch" in companion.system("Asha", "Hello", "en", tools(), "Intermediate"))
        assertFalse("batch;" in companion.system("Neha", "Hello", "en", tools()))
    }
}
