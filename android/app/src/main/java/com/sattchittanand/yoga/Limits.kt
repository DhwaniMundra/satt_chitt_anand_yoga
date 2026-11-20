package com.sattchittanand.yoga

/** The server's limits on what people type (appsscript/src/Validate.gs), so a field stops where the server would. Text
 *  is counted in code points, as the server counts it: a Devanagari vowel sign or virama is one. */
object Limits {
    const val NAME = 80
    const val MEALS = 600
    const val PAIN_NOTE = 600
    /** A note on an item, after class or on one's own. */
    const val NOTE = 1000
    /** A health note, kept on the phone and maybe shared with the teacher. */
    const val HEALTH_NOTE = 1000
    const val BATCH_NOTE = 600
    const val ITEM_FEEDBACK = 1000
    const val FEEDBACK = 2000
    const val PASSWORD_MIN = 6
    val AGE = 5..100
    val HEIGHT_CM = 80..230
    val WEIGHT_KG = 15..250
}

/** The length the server counts. */
fun String.codePointLength(): Int = codePointCount(0, length)

/** At most [max] code points, never splitting one. */
fun String.limitedTo(max: Int): String = if (codePointLength() <= max) this else substring(0, offsetByCodePoints(0, max))
