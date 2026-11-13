package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ClassSession
import com.sattchittanand.yoga.R
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.LocalDate

/** The clock, ticking every 30 seconds, for countdowns. */
@Composable
fun rememberNow(): Instant {
    var now by remember { mutableStateOf(Instant.now()) }
    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            now = Instant.now()
        }
    }
    return now
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TodayScreen(vm: AppViewModel) {
    val home = vm.home ?: return
    val now = rememberNow()
    PullToRefreshBox(isRefreshing = vm.busy, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Label(stringResource(R.string.brand_latin), Palette.saffron)
            Text(stringResource(R.string.greeting, home.user.name.substringBefore(' ')), style = MaterialTheme.typography.headlineSmall)

            home.afterCheckin?.let { AfterClassCard(vm, it) }
            if (!home.user.isApproved) PendingCard(vm)

            home.sessions.firstOrNull()?.let { NextClassCard(vm, it, now) }

            home.groupLink?.let { link ->
                val context = LocalContext.current
                OutlinedButton(onClick = { openLink(context, link) }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.Groups, null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.open_group))
                }
            }

            if (home.sessions.size > 1) {
                Label(stringResource(R.string.coming_up))
                SectionCard {
                    home.sessions.drop(1).forEachIndexed { i, s ->
                        if (i > 0) HorizontalDivider(color = Palette.line)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.width(96.dp)) {
                                Text(dayLabel(s.startsAt), style = MaterialTheme.typography.titleMedium)
                                Text(timeLabel(s.startsAt), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                            }
                            Column(Modifier.weight(1f)) {
                                Text(s.info.name, style = MaterialTheme.typography.bodyLarge)
                                Text(s.info.level, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun NextClassCard(vm: AppViewModel, s: ClassSession, now: Instant) {
    val context = LocalContext.current
    var askMood by rememberSaveable(s.id) { mutableStateOf(false) }
    val live = now >= s.startsAt && now < s.endsAt
    SectionCard(tint = Palette.moss) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Label(stringResource(R.string.next_class), Palette.mossLight)
            Spacer(Modifier.weight(1f))
            if (live) Pill(stringResource(R.string.live_now), Palette.saffron, Color.White)
        }
        Text(s.info.name, style = MaterialTheme.typography.headlineSmall, color = Color.White)
        Text(
            "${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)} · ${stringResource(R.string.minutes, s.minutes)}",
            style = MaterialTheme.typography.bodyLarge, color = Palette.mossLight,
        )
        Text(s.info.about, style = MaterialTheme.typography.bodyMedium, color = Palette.mossLight)
        if (!live && now < s.startsAt) {
            Text(stringResource(R.string.starts_in, untilLabel(now, s.startsAt)), style = MaterialTheme.typography.titleMedium, color = Color.White)
        }
        if (s.checkedIn) Pill(stringResource(R.string.checked_in), Palette.mossLight, Palette.moss)

        val link = s.meetLink
        when {
            link == null -> Text(stringResource(R.string.link_soon), style = MaterialTheme.typography.bodyMedium, color = Palette.mossLight)
            askMood -> SectionCard(tint = Palette.paper) {
                Text(stringResource(R.string.how_feel_before), style = MaterialTheme.typography.titleMedium)
                MoodPicker(null) { mood -> vm.checkin(s.id, "before", mood) { askMood = false; openLink(context, link) } }
                TextButton(onClick = { askMood = false; openLink(context, link) }) { Text(stringResource(R.string.skip)) }
            }
            else -> Button(
                onClick = { if (s.checkedIn) openLink(context, link) else askMood = true },
                colors = ButtonDefaults.buttonColors(containerColor = Palette.saffron),
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                Icon(Icons.Filled.Videocam, null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.join_class))
            }
        }
    }
}

@Composable
private fun AfterClassCard(vm: AppViewModel, s: ClassSession) {
    SectionCard(tint = Palette.saffronLight) {
        Text(stringResource(R.string.how_feel_after), style = MaterialTheme.typography.titleMedium)
        Text(s.info.name, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        MoodPicker(null) { mood -> vm.checkin(s.id, "after", mood) }
    }
}

@Composable
private fun PendingCard(vm: AppViewModel) {
    var code by rememberSaveable { mutableStateOf("") }
    SectionCard(tint = Palette.saffronLight) {
        Text(stringResource(R.string.pending_title), style = MaterialTheme.typography.titleMedium)
        Text(stringResource(R.string.pending_body), style = MaterialTheme.typography.bodyMedium)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(code, { code = it.uppercase() }, singleLine = true, label = { Text(stringResource(R.string.group_code_label)) }, modifier = Modifier.weight(1f))
            Button(onClick = { vm.enterGroupCode(code) }, enabled = code.isNotBlank() && !vm.busy) { Text(stringResource(R.string.enter_code)) }
        }
        vm.error?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error) }
    }
}

private val DAY_NAMES = mapOf(
    "mon" to R.string.mon, "tue" to R.string.tue, "wed" to R.string.wed, "thu" to R.string.thu,
    "fri" to R.string.fri, "sat" to R.string.sat, "sun" to R.string.sun,
)

@Composable
fun WeekScreen(vm: AppViewModel) {
    val studio = vm.home?.studio ?: return
    val today = LocalDate.now().dayOfWeek.value - 1 // Monday is 0, as in the studio's list
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Label(studio.tagline, Palette.saffron)
        Text(stringResource(R.string.week_title), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.week_time), style = MaterialTheme.typography.bodyLarge, color = Palette.muted)
        SectionCard {
            studio.weekly.forEachIndexed { i, (day, info) ->
                if (i > 0) HorizontalDivider(color = Palette.line)
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        stringResource(DAY_NAMES.getValue(day)),
                        style = MaterialTheme.typography.titleMedium,
                        color = if (i == today) Palette.saffron else Palette.ink,
                        modifier = Modifier.width(64.dp),
                    )
                    Column(Modifier.weight(1f)) {
                        Text(info.name, style = MaterialTheme.typography.bodyLarge)
                        Text(info.about, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                    }
                }
            }
        }
        Label(stringResource(R.string.your_teacher))
        SectionCard(tint = Palette.mossLight) {
            Text(studio.teacherName, style = MaterialTheme.typography.titleLarge, color = Palette.moss)
            Text(studio.teacherTitle, style = MaterialTheme.typography.labelLarge, color = Palette.muted)
            Text(studio.teacherBio, style = MaterialTheme.typography.bodyLarge)
        }
        Pill(stringResource(R.string.first_class_free), Palette.saffronLight, Palette.saffron)
        Spacer(Modifier.height(8.dp))
    }
}
