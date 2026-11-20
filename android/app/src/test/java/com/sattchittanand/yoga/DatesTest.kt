package com.sattchittanand.yoga

import com.sattchittanand.yoga.ui.daysFromToday
import com.sattchittanand.yoga.ui.timeParts
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Test
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Days and times on the student's own calendar: a student in California is 13 and a half hours behind India. */
class DatesTest {
    private val california = ZoneId.of("America/Los_Angeles")
    private val india = ZoneId.of("Asia/Kolkata")
    private val clock = DateTimeFormatter.ofPattern("h:mm a", Locale.ENGLISH)

    @Test fun aClassTimeAbroadHasItsIndiaTimeApartForItsOwnLine() {
        val sevenInIndia = Instant.parse("2026-11-23T01:30:00Z") // Monday 7:00 AM in India
        assertEquals("5:30 PM" to "7:00 AM IST", timeParts(sevenInIndia, california, clock))
        assertEquals("7:00 AM" to null, timeParts(sevenInIndia, india, clock))
    }

    /** "You can change it until …": twelve hours after a class that ended at 7:55 AM in India. */
    @Test fun theLastMomentToChangeIsTomorrowInIndiaButTodayInCalifornia() {
        val closes = Instant.parse("2026-11-20T14:25:00Z") // Friday 7:55 PM in India, 6:25 AM in California
        val now = Instant.parse("2026-11-20T03:00:00Z") // Friday 8:30 AM in India, Thursday 7:00 PM in California
        assertEquals(0L, daysFromToday(closes, now, india))
        assertEquals(1L, daysFromToday(closes, now, california))
    }

    /** The first time an item was practised: an evening class in California is the next morning's date in India. */
    @Test fun anItemsFirstTimeIsTheDayOfItsOldestEntryWhereTheStudentIs() {
        val history = ItemHistory.from(JSONObject("""{"item": "vajrasana", "in_class": 2, "solo": 0, "first": "2026-11-23", "reaction_trend": null,
            "holds": null, "strain_or_pain": {"times": 0, "last": null}, "feedback": [], "entries": [
              {"date": "2026-11-24", "at": "2026-11-24T01:30:00Z", "kind": "class", "hold_s": null, "reaction": 3, "pain": 0, "note": null},
              {"date": "2026-11-23", "at": "2026-11-23T01:30:00Z", "kind": "class", "hold_s": null, "reaction": 2, "pain": 0, "note": null}]}"""))
        val oldest = history.entries.last().at
        assertEquals(LocalDate.parse("2026-11-22"), oldest.atZone(california).toLocalDate()) // Sunday evening there
        assertEquals(LocalDate.parse("2026-11-23"), oldest.atZone(india).toLocalDate())
        val mondayInCalifornia = Instant.parse("2026-11-23T17:00:00Z") // Monday 9 AM there, Monday 10:30 PM in India
        assertEquals("yesterday in California, not today as India's date would say", -1L, daysFromToday(oldest, mondayInCalifornia, california))
    }
}
