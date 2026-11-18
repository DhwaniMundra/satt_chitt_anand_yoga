package com.sattchittanand.yoga.ui

import android.content.ActivityNotFoundException
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
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.R
import java.time.Duration
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
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

/** "Today", "Tomorrow" or "Mon 24 Nov", in the phone's time zone. */
@Composable
fun dayLabel(at: Instant): String {
    val day = at.atZone(ZoneId.systemDefault()).toLocalDate()
    val today = LocalDate.now()
    return when (day) {
        today -> stringResource(R.string.today)
        today.plusDays(1) -> stringResource(R.string.tomorrow)
        else -> DateTimeFormatter.ofPattern("EEE d MMM", locale()).format(day)
    }
}

private val IST = ZoneId.of("Asia/Kolkata")

/** "8:00 AM"; on a phone outside India, the class's India time too: "7:30 PM · 8:00 AM IST". */
@Composable
fun timeLabel(at: Instant): String {
    val format = DateTimeFormatter.ofPattern("h:mm a", locale())
    val here = ZoneId.systemDefault()
    val local = format.format(at.atZone(here))
    return if (here.rules.getOffset(at) == IST.rules.getOffset(at)) local else "$local · ${format.format(at.atZone(IST))} IST"
}

fun untilLabel(from: Instant, to: Instant): String {
    val d = Duration.between(from, to)
    val hours = d.toHours()
    val minutes = d.toMinutes() % 60
    return when {
        d.toDays() >= 1 -> "${d.toDays()} d ${hours % 24} h"
        hours >= 1 -> "$hours h $minutes min"
        else -> "${d.toMinutes().coerceAtLeast(1)} min"
    }
}

// ---------- leaving the app ----------

/** Opens WhatsApp with [text] ready to send to a chat or group; if WhatsApp is missing, the share sheet. */
fun shareToWhatsApp(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    try {
        context.startActivity(Intent(send).setPackage("com.whatsapp"))
    } catch (_: ActivityNotFoundException) {
        context.startActivity(Intent.createChooser(send, null))
    }
}

/** Opens a Meet, Zoom or WhatsApp-group link in its app, or the browser. */
fun openLink(context: Context, url: String) {
    try {
        context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)))
    } catch (_: ActivityNotFoundException) {
    }
}

@Composable
fun errorText(code: String): String = stringResource(
    when (code) {
        "bad_phone" -> R.string.err_bad_phone
        "bad_login" -> R.string.err_bad_login
        "phone_taken" -> R.string.err_phone_taken
        "bad_group_code" -> R.string.err_bad_group_code
        "bad_teacher_code" -> R.string.err_bad_teacher_code
        "bad_meet_link" -> R.string.err_bad_meet_link
        "bad_group_link" -> R.string.err_bad_group_link
        "network" -> R.string.err_network
        "short_password" -> R.string.err_short_password
        "pending" -> R.string.err_pending
        "busy" -> R.string.err_busy
        "too_many_attempts" -> R.string.err_too_many_attempts
        "teacher_exists" -> R.string.err_teacher_exists
        "checkin_closed" -> R.string.err_checkin_closed
        else -> R.string.err_generic
    },
)
