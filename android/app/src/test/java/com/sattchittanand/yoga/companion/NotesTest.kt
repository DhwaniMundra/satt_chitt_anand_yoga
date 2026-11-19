package com.sattchittanand.yoga.companion

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/** The studio's notes in the backend, read as the app reads them from its assets (Gradle copies these same files). */
val BACKEND = File("../../backend").let { if (it.isDirectory) it else File("../backend") }
val NOTES = StudioNotes(File(BACKEND, "knowledge/yoga_health.md").readText(), File(BACKEND, "knowledge/yoga_health.mr.md").readText())

/**
 * The retrieval port and the emergency check: the same questions and expected sections as backend/tests/test_assistant.py,
 * so the phone finds what the server finds.
 */
class NotesTest {
    @Test fun devanagariWordsStayWhole() {
        assertEquals(listOf("कमर", "दर्द", "पाठदुखी"), tokenize("कमर दर्द, पाठदुखी!"))
        assertEquals(listOf("कमर", "दर्द"), tokenize("मुझे कमर में दर्द है")) // function words dropped
    }

    @Test fun everySectionHasKeywordsAndNoKeywordsLeakIntoText() {
        val sections = NOTES.retriever.sections
        assertTrue(sections.size >= 20)
        for (s in sections) assertTrue(s.title, s.text.isNotEmpty() && "Keywords:" !in s.text)
    }

    @Test fun questionsFindTheRightSection() = check(
        "I have lower back pain, what can I do?" to "Back pain",
        "कमर दर्द के लिए योग?" to "Back pain",
        "मला पाठदुखी आहे" to "Back pain",
        "Is kapalbhati safe with high BP?" to "High blood pressure and the heart",
        "I am pregnant, can I join?" to "Pregnancy",
        "गरोदरपणात योग करू शकते का?" to "Pregnancy",
        "What time is the class?" to "About the studio and classes",
        "What does sat chit ananda mean?" to "Sat Chit Ananda",
        "नींद नहीं आती" to "Stress, anxiety and sleep",
    )

    @Test fun suggestedQuestionsFindTheirSection() = check(*SUGGESTIONS.toTypedArray())

    /** The Ask screen's suggestions 2 and 4 are answered from the notes and must be among the questions tested above
     *  (1 and 3 ask about the student's own practice), as backend/tests/test_assistant.py checks. */
    @Test fun noteSuggestionsInTheAppAreTested() {
        val res = File("src/main/res")
        val shown = listOf("values", "values-hi", "values-mr").flatMap { folder ->
            File(res, "$folder/strings.xml").readLines().filter { "name=\"sugg_2\"" in it || "name=\"sugg_4\"" in it }
                .map { it.substringAfter(">").substringBefore("<").replace("\\'", "'") }
        }.toSet()
        assertEquals(6, shown.size)
        assertTrue(shown.toString(), SUGGESTIONS.map { it.first }.containsAll(shown))
    }

    @Test fun marathiNotesHaveEverySection() {
        assertEquals(NOTES.retriever.sections.map { it.title }.toSet(), NOTES.translations.getValue("mr").keys)
    }

    @Test fun inflectedWordsFindTheirStem() {
        assertEquals("गरोदरपणा", NOTES.retriever.expand("गरोदरपणात"))
    }

    @Test fun unknownQuestionsMatchNothing() {
        assertEquals(emptyList<Section>(), NOTES.retriever.top("qwerty zxcv"))
    }

    @Test fun urgentSignsHoweverTheyAreWritten() {
        for (q in listOf(
            "I have chest pain during class", "मुझे सीने में दर्द है", "मला छातीत दुखत आहे", "I feel suicidal",
            "I can’t breathe after pranayama", "i cant breath", "my chest hurts badly", "I feel faint", "मुझे साँस नहीं आ रही",
            "सीने मे दर्द हो रहा है", "मला छातीत कळ येते", "मुझे ख़ुद को नुकसान पहुँचाने का मन करता है", "I have chest pain after surya namaskar",
        )) assertTrue(q, isUrgent(q))
    }

    @Test fun ordinaryBreathingQuestionsAreNotUrgent() {
        for (q in listOf("How do I breathe in cat-cow?", "Chest opening poses for posture?", "सांस कैसे लें?", "श्वास कसा घ्यावा?"))
            assertFalse(q, isUrgent(q))
    }

    private fun check(vararg cases: Pair<String, String>) {
        for ((question, section) in cases) assertEquals(question, section, NOTES.retriever.top(question).first().title)
    }

    companion object {
        /** The suggested questions on the Ask screen, exactly as in strings.xml, in all three languages. */
        val SUGGESTIONS = listOf(
            "I'm a beginner. How do I start?" to "Starting as a beginner",
            "मैं नया हूँ। शुरुआत कैसे करूँ?" to "Starting as a beginner",
            "मी नवशिका आहे. सुरुवात कशी करू?" to "Starting as a beginner",
            "Yoga for back pain?" to "Back pain",
            "कमर दर्द के लिए योग?" to "Back pain",
            "पाठदुखीसाठी योग?" to "Back pain",
            "What should I eat before class?" to "Food and water around practice",
            "कक्षा से पहले क्या खाएँ?" to "Food and water around practice",
            "वर्गापूर्वी काय खावे?" to "Food and water around practice",
            "What does Sat Chit Ananda mean?" to "Sat Chit Ananda",
            "सत् चित् आनंद का अर्थ क्या है?" to "Sat Chit Ananda",
            "सत् चित् आनंद म्हणजे काय?" to "Sat Chit Ananda",
        )
    }
}
