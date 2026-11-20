package com.sattchittanand.yoga.ui

import android.content.ActivityNotFoundException
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.BasicText
import androidx.compose.foundation.text.TextAutoSize
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LocalContentColor
import androidx.compose.material3.LocalTextStyle
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.isSpecified
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.codePointLength
import com.sattchittanand.yoga.limitedTo
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.DecimalStyle
import java.time.temporal.ChronoUnit
import java.util.Locale

/** The studio's name in Devanagari over its Latin spelling. */
@Composable
fun BrandHeader(modifier: Modifier = Modifier, large: Boolean = false) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            stringResource(R.string.brand_devanagari),
            color = Palette.saffron,
            style = MaterialTheme.typography.titleMedium.copy(fontSize = if (large) 22.sp else 15.sp, letterSpacing = 1.sp),
        )
        Text(
            stringResource(R.string.brand_latin),
            style = if (large) MaterialTheme.typography.displaySmall else MaterialTheme.typography.titleLarge,
            color = Palette.moss,
        )
    }
}

@Composable
fun SectionCard(modifier: Modifier = Modifier, tint: Color = Palette.paper, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = tint),
        border = BorderStroke(1.dp, Palette.line),
        shape = MaterialTheme.shapes.medium,
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp), content = content)
    }
}

@Composable
fun Label(text: String, color: Color = Palette.muted) {
    Text(text.uppercase(LocalConfiguration.current.locales[0]), style = MaterialTheme.typography.labelMedium, color = color)
}

@Composable
fun Pill(text: String, background: Color = Palette.mossLight, color: Color = Palette.moss) {
    Surface(color = background, shape = CircleShape) {
        Text(text, Modifier.padding(horizontal = 12.dp, vertical = 4.dp), style = MaterialTheme.typography.labelMedium, color = color)
    }
}

/** Errors a form shows beside its own field; any other error shows in a snackbar, on any tab. */
val FORM_ERRORS = setOf("bad_meet_link", "bad_group_link", "bad_group_code")

/** What a screen shows until its data has come: a spinner while it loads; if it failed (the snackbar says why),
 *  "Try again". */
@Composable
fun Waiting(vm: AppViewModel, retry: () -> Unit, modifier: Modifier = Modifier.fillMaxSize()) {
    Column(modifier.padding(24.dp), verticalArrangement = Arrangement.spacedBy(12.dp, Alignment.CenterVertically),
        horizontalAlignment = Alignment.CenterHorizontally) {
        if (vm.busy || vm.error == null) {
            CircularProgressIndicator(color = Palette.moss)
            Text(stringResource(R.string.loading), color = Palette.muted)
        } else {
            Text(stringResource(R.string.not_loaded), textAlign = TextAlign.Center)
            Button(onClick = retry) { Text(stringResource(R.string.try_again)) }
        }
    }
}

/** A stopwatch's time: "1:05". */
fun stopwatch(seconds: Int): String = "%d:%02d".format(seconds / 60, seconds % 60)

/** Whether the phone's font is large (1.5 times or more): a row of fixed slots then gives each slot more room. */
@Composable
fun largeFont() = LocalDensity.current.fontScale >= 1.5f

/** One line that shrinks a little to fit its slot rather than break a word: for labels in fixed-width places. */
@Composable
fun FitText(text: String, modifier: Modifier = Modifier, style: TextStyle = LocalTextStyle.current, color: Color = LocalContentColor.current,
    textAlign: TextAlign = TextAlign.Start) {
    BasicText(text, modifier, style = style.copy(color = color, textAlign = textAlign), maxLines = 1,
        autoSize = TextAutoSize.StepBased(minFontSize = 8.sp, maxFontSize = if (style.fontSize.isSpecified) style.fontSize else 14.sp))
}

/** Options side by side, equal widths, at most one selected: the reactions after class, the curricula, the batches.
 *  [perRow] to a row (all in one by default); two to a row with a large font. */
@Composable
fun Choices(labels: List<String>, selected: Int?, enabled: Boolean = true, perRow: Int = labels.size, onPick: (Int) -> Unit) {
    val perRow = if (largeFont()) minOf(2, perRow) else perRow
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        labels.indices.chunked(perRow).forEach { row ->
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                row.forEach { i ->
                    val on = selected == i
                    Surface(
                        onClick = { onPick(i) },
                        enabled = enabled,
                        shape = MaterialTheme.shapes.small,
                        color = if (on) Palette.moss else Color.Transparent,
                        border = BorderStroke(1.dp, if (on) Palette.moss else Palette.line),
                        modifier = Modifier.weight(1f),
                    ) {
                        FitText(labels[i], Modifier.padding(vertical = 10.dp, horizontal = 4.dp), MaterialTheme.typography.labelMedium,
                            if (on) Color.White else Palette.ink, TextAlign.Center)
                    }
                }
                repeat(perRow - row.size) { Spacer(Modifier.weight(1f)) }
            }
        }
    }
}

/** Stat tiles, (value, label): side by side; one under another with a large font, so the labels keep whole words. */
@Composable
fun StatTiles(vararg tiles: Pair<String, String>) {
    if (largeFont()) {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) { tiles.forEach { (value, label) -> StatTile(value, label, Modifier.fillMaxWidth()) } }
    } else {
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) { tiles.forEach { (value, label) -> StatTile(value, label, Modifier.weight(1f)) } }
    }
}

@Composable
private fun StatTile(value: String, label: String, modifier: Modifier) {
    SectionCard(modifier, tint = Palette.mossLight) {
        Text(value, style = MaterialTheme.typography.headlineSmall, color = Palette.moss)
        Text(label, style = MaterialTheme.typography.labelMedium, color = Palette.muted)
    }
}

/** How the app names the teacher, in the chosen language: from content/studio.json, never written into the strings. */
val LocalTeacher = staticCompositionLocalOf { "" }

val MOODS = listOf("😣", "😕", "😐", "🙂", "😄")

/** Five faces: a check-in that needs no reading. The selected face's word appears under it for those who read. */
@Composable
fun MoodPicker(selected: Int?, onPick: (Int) -> Unit) {
    val words = listOf(R.string.mood_1, R.string.mood_2, R.string.mood_3, R.string.mood_4, R.string.mood_5).map { stringResource(it) }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        MOODS.forEachIndexed { i, face ->
            val mood = i + 1
            Column(horizontalAlignment = Alignment.CenterHorizontally) {
                Surface(
                    onClick = { onPick(mood) },
                    shape = CircleShape,
                    color = if (selected == mood) Palette.saffronLight else Color.Transparent,
                    border = BorderStroke(if (selected == mood) 2.dp else 1.dp, if (selected == mood) Palette.saffron else Palette.line),
                    modifier = Modifier.size(56.dp).semantics { contentDescription = words[i] },
                ) {
                    Column(verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(face, fontSize = 28.sp, textAlign = TextAlign.Center)
                    }
                }
                Spacer(Modifier.height(4.dp))
                Text(
                    if (selected == mood) words[i] else " ",
                    style = MaterialTheme.typography.labelMedium,
                    color = Palette.saffron,
                )
            }
        }
    }
}

@Composable
fun Dot(color: Color) {
    Surface(Modifier.size(8.dp), shape = CircleShape, color = color) {}
}

/** A horizontal bar from 0 to 1, for mood averages on the 1–5 scale. */
@Composable
fun Bar(fraction: Float, color: Color, modifier: Modifier = Modifier) {
    Row(modifier.fillMaxWidth().height(10.dp).background(Palette.line, CircleShape)) {
        if (fraction > 0f) Surface(Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).height(10.dp), shape = CircleShape, color = color) {}
    }
}

// ---------- time ----------

@Composable
fun locale(): Locale = LocalConfiguration.current.locales[0]

private val IST = ZoneId.of("Asia/Kolkata")

/** A date or time pattern in the chosen language, its digits as that language writes them (Devanagari in Marathi, as
 *  the app's other numbers are). */
@Composable
fun dateFormat(pattern: String): DateTimeFormatter = locale().let { DateTimeFormatter.ofPattern(pattern, it).withDecimalStyle(DecimalStyle.of(it)) }

/** How many days [at] is from [now], both taken in [zone]: 0 the same day, 1 the next, -1 the one before. */
fun daysFromToday(at: Instant, now: Instant, zone: ZoneId): Long =
    ChronoUnit.DAYS.between(now.atZone(zone).toLocalDate(), at.atZone(zone).toLocalDate())

/** "Today", "Tomorrow" or "Mon 24 Nov" for a moment, on the student's own calendar (the phone's time zone): a class at
 *  7:00 in India on a Monday is "Today" on a Sunday evening in New York. */
@Composable
fun dayLabel(at: Instant): String {
    val zone = ZoneId.systemDefault()
    return dayName(daysFromToday(at, Instant.now(), zone), at.atZone(zone).toLocalDate())
}

/** The same for a day the server gives only as a date in India (an item's first time), against today in India. */
@Composable
fun indiaDayLabel(day: LocalDate): String = dayName(ChronoUnit.DAYS.between(LocalDate.now(IST), day), day)

@Composable
private fun dayName(fromToday: Long, day: LocalDate): String = when (fromToday) {
    0L -> stringResource(R.string.today)
    1L -> stringResource(R.string.tomorrow)
    else -> dateFormat("EEE d MMM").format(day)
}

/** "8:00 AM"; on a phone outside India, the class's India time too: "7:30 PM · 8:00 AM IST". */
@Composable
fun timeLabel(at: Instant): String {
    val format = dateFormat("h:mm a")
    val here = ZoneId.systemDefault()
    val local = format.format(at.atZone(here))
    return if (here.rules.getOffset(at) == IST.rules.getOffset(at)) local else "$local · ${format.format(at.atZone(IST))} IST"
}

/** "2 d 5 h", "3 h 20 min", "18 min"; in Hindi "3 घंटे 20 मिनट", in Marathi "3 तास 20 मिनिटे" (the units come from
 *  the strings, singular or plural). A zero second part is left out: "2 d", not "2 d 0 h". */
@Composable
fun untilLabel(from: Instant, to: Instant): String {
    val d = Duration.between(from, to)
    @Composable fun unit(id: Int, n: Long) = pluralStringResource(id, n.toInt(), n.toInt())
    fun pair(big: String, small: String?) = if (small == null) big else "$big $small"
    val days = d.toDays()
    val hours = d.toHours()
    val minutes = d.toMinutes() % 60
    return when {
        days >= 1 -> pair(unit(R.plurals.until_days, days), (hours % 24).takeIf { it > 0 }?.let { unit(R.plurals.until_hours, it) })
        hours >= 1 -> pair(unit(R.plurals.until_hours, hours), minutes.takeIf { it > 0 }?.let { unit(R.plurals.until_minutes, it) })
        else -> unit(R.plurals.until_minutes, d.toMinutes().coerceAtLeast(1))
    }
}

// ---------- leaving the app ----------

/** Hands [text] to Android's share sheet: the class's group on WhatsApp, an SMS, an e-mail, wherever the teacher
 *  chooses. */
fun shareText(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(send, null))
}

/** Puts [text] on the clipboard. */
fun copyText(context: Context, text: String) {
    context.getSystemService(ClipboardManager::class.java).setPrimaryClip(ClipData.newPlainText(null, text))
}

/** Opens a call's or a group's link in its app, or the browser. */
fun openLink(context: Context, url: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (_: ActivityNotFoundException) {
    }
}

/** A field the server named in a refused input ([com.sattchittanand.yoga.problemCode]), as the message names it. */
private val FIELDS = mapOf(
    "name" to R.string.name, "age" to R.string.age, "height_cm" to R.string.height_cm, "weight_kg" to R.string.weight_kg,
    "password" to R.string.field_password, "new_password" to R.string.field_password, "current_password" to R.string.field_password,
    "meals" to R.string.field_meals, "pain_note" to R.string.field_pain_note, "note" to R.string.field_note,
)

@Composable
fun errorText(code: String): String {
    val problem = code.split(':')
    if (problem.size > 1) { // a check the server refused: "too_long:pain_note:600"
        val field = stringResource(FIELDS[problem[1]] ?: R.string.field_text)
        return when (problem[0]) {
            "too_long" -> stringResource(R.string.err_field_too_long, field, problem.getOrNull(2)?.toIntOrNull() ?: 0)
            "range" -> stringResource(R.string.err_field_range, field)
            else -> stringResource(R.string.err_field_invalid, field)
        }
    }
    return stringResource(
        when (code) {
            "bad_phone" -> R.string.err_bad_phone
            "bad_login" -> R.string.err_bad_login
            "phone_taken" -> R.string.err_phone_taken
            "bad_group_code" -> R.string.err_bad_group_code
            "bad_teacher_code" -> R.string.err_bad_teacher_code
            "bad_meet_link" -> R.string.err_bad_meet_link
            "bad_group_link" -> R.string.err_bad_group_link
            "bad_password" -> R.string.err_bad_password
            "network" -> R.string.err_network
            "short_password" -> R.string.err_short_password
            "pending" -> R.string.err_pending
            "busy" -> R.string.err_busy
            "too_many_attempts" -> R.string.err_too_many_attempts
            "teacher_exists" -> R.string.err_teacher_exists
            "checkin_closed" -> R.string.err_checkin_closed
            "after_closed" -> R.string.err_after_closed
            "other_batch" -> R.string.err_other_batch
            "needs_batch" -> R.string.err_needs_batch
            "no_link" -> R.string.err_no_link
            "nothing_said" -> R.string.err_nothing_said
            "empty_note" -> R.string.err_empty_note
            "old_server" -> R.string.err_old_server
            else -> R.string.err_generic
        },
        LocalTeacher.current, // for the messages that name the teacher
    )
}

/** A text field that stops at [limit] code points, as the server counts them (so a Devanagari note is not cut short
 *  by surprise), and shows the count once it is near. */
@Composable
fun LimitedField(
    value: String,
    onChange: (String) -> Unit,
    limit: Int,
    modifier: Modifier = Modifier.fillMaxWidth(),
    label: @Composable (() -> Unit)? = null,
    placeholder: @Composable (() -> Unit)? = null,
    minLines: Int = 1,
    maxLines: Int = Int.MAX_VALUE,
) {
    val count = value.codePointLength()
    val near = count * 5 >= limit * 4 // from four fifths of the way
    OutlinedTextField(
        value, { onChange(it.limitedTo(limit)) }, modifier = modifier, label = label, placeholder = placeholder, minLines = minLines, maxLines = maxLines,
        supportingText = if (near) ({ Text("$count / $limit", Modifier.fillMaxWidth(), textAlign = TextAlign.End) }) else null,
    )
}

/** A sub-screen's title with an arrow back, so leaving it never depends on the phone's Back alone. */
@Composable
fun BackHeader(title: String, back: () -> Unit) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        IconButton(onClick = back, modifier = Modifier.offset(x = (-12).dp)) {
            Icon(Icons.AutoMirrored.Filled.ArrowBack, stringResource(R.string.back))
        }
        Text(title, Modifier.offset(x = (-8).dp), style = MaterialTheme.typography.headlineSmall)
    }
}
