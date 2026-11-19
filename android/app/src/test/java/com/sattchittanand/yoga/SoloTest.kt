package com.sattchittanand.yoga

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/** Practice on one's own: the stopwatch per item, what is sent at Finish, and the library's search. */
class SoloTest {
    private val start = 1_000_000L

    @Test fun theStopwatchAddsUpPerItemAndStopsWhenMovingOn() {
        var run = SoloRun.start(listOf("vajrasana", "tadasana"), "beginner", start)
        run = run.toggled(start + 1_000) // started
        assertEquals(30_000L, run.held(start + 31_000))
        run = run.toggled(start + 31_000).toggled(start + 40_000) // stopped at 30 s, started again
        run = run.moved(1, start + 55_500) // moving on stops it: 30 + 15.5 s
        assertEquals(null, run.runningSince)
        assertEquals(45_500L, run.heldMs[0])
        assertEquals("the next item's own stopwatch", 0L, run.held(start + 60_000))
        run = run.moved(0, start + 61_000)
        assertEquals("back to the first: its time is kept, the watch not running", 45_500L, run.held(start + 70_000))
    }

    @Test fun finishSendsWhatWasTimedOrSaid() {
        var run = SoloRun.start(listOf("vajrasana", "tadasana", "shavasana"), null, start)
        run = run.toggled(start).stopped(start + 90_900)
        run = run.moved(1, start + 91_000).changed(ItemFeedback("tadasana", 3, false, ""))
        val sent = run.entries()
        assertEquals(listOf("vajrasana", "tadasana"), sent.map { it.item }) // shavasana: nothing timed or said
        assertEquals(listOf(90, 0), sent.map { it.heldSeconds }) // whole seconds; none for an item not timed
    }

    @Test fun theLibrarySearchFindsAnyNameAccentsAndCaseAside() {
        val item = LibraryItem("shashankasana", "asana", "शशांकासन", "Śaśāṅkāsana", "Hare pose", listOf("child's pose", "balasana"))
        assertTrue(item.matches("sasank"))
        assertTrue(item.matches("CHILD"))
        assertTrue(item.matches("शशांक"))
        assertTrue(item.matches(" hare "))
        assertFalse(item.matches(""))
        assertFalse(item.matches("cobra"))
        assertFalse("not inside a word", item.matches("ank"))
    }
}
