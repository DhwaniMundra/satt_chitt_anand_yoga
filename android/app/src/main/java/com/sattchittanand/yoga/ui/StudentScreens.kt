package com.sattchittanand.yoga.ui

import androidx.activity.compose.BackHandler
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ClassSession
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.Studio
import com.sattchittanand.yoga.StudioWords
import kotlinx.coroutines.delay
import java.time.Instant

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

/** The student's day: how the last class went, the next class and its sequence, the week ahead, and the studio. While
 *  the next class is within the hour or under way, the tab is read again every two minutes, so a link the teacher has
 *  just shared appears; coming back to the app reads it again too ([AppViewModel.onResume]). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TodayScreen(vm: AppViewModel) {
    val home = vm.home ?: return Waiting(vm, vm::refresh)
    val now = rememberNow()
    val words = vm.words()
    var afterClass by rememberSaveable { mutableStateOf(false) }
    var aboutMe by rememberSaveable { mutableStateOf(false) }
    val next = home.sessions.firstOrNull()
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(next?.id) {
        if (next == null) return@LaunchedEffect
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) { // only while the app is in front
            while (true) {
                delay(2 * 60_000)
                val at = Instant.now()
                if (at >= next.startsAt.minusSeconds(60 * 60) && at < next.endsAt) vm.refreshHome()
            }
        }
    }
    if (aboutMe || vm.askIntake) return IntakeScreen(vm) { aboutMe = false; vm.askIntake = false }
    val after = home.afterClass
    if (afterClass && after != null) {
        BackHandler { afterClass = false }
        AfterClassScreen(vm, after, home.afterSaid) { afterClass = false }
        return
    }
    PullToRefreshBox(isRefreshing = vm.busy, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Label(stringResource(R.string.brand_latin), Palette.saffron)
            Text(stringResource(R.string.greeting, home.user.name.substringBefore(' ')), style = MaterialTheme.typography.headlineSmall)
            home.batch?.let { Text(stringResource(R.string.your_batch, it.name), style = MaterialTheme.typography.titleMedium, color = Palette.moss) }

            if (after != null && home.afterSaid == null) {
                // One who did not check in may have joined from the class's message: asked whether they came.
                SectionCard(tint = Palette.saffronLight) {
                    Text(stringResource(if (after.checkedIn) R.string.how_did_it_go else R.string.were_you_in_class), style = MaterialTheme.typography.titleMedium)
                    Text("${after.batch.name} · ${dayLabel(after.startsAt)} · ${timeLabel(after.startsAt)}", style = MaterialTheme.typography.bodyMedium,
                        color = Palette.muted)
                    Button(onClick = { afterClass = true }) { Text(stringResource(R.string.tell_teacher, LocalTeacher.current)) }
                }
            } else if (after != null) { // said already: it can be changed until 12 hours after class
                val closes = after.startsAt.plusSeconds(after.minutes * 60L + 12 * 3600L)
                SectionCard(tint = Palette.mossLight) {
                    Text(stringResource(R.string.told_teacher, LocalTeacher.current), style = MaterialTheme.typography.titleMedium)
                    Text(after.batch.name + " · " + stringResource(R.string.change_until, timeLabel(closes)), style = MaterialTheme.typography.bodyMedium,
                        color = Palette.muted)
                    TextButton(onClick = { afterClass = true }) { Text(stringResource(R.string.change)) }
                }
            }
            if (!home.user.isApproved) PendingCard { aboutMe = true }

            next?.let { NextClassCard(vm, it, now) }

            home.groupLink?.let { link ->
                val context = LocalContext.current
                OutlinedButton(onClick = { openLink(context, link) }, modifier = Modifier.fillMaxWidth()) {
                    Icon(Icons.Filled.Groups, null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.open_group))
                }
            }

            if (home.sessions.size > 1) {
                Text(words.week, style = MaterialTheme.typography.titleLarge)
                SectionCard {
                    home.sessions.drop(1).forEachIndexed { i, s ->
                        if (i > 0) HorizontalDivider(color = Palette.line)
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.width(96.dp)) {
                                Text(dayLabel(s.startsAt), style = MaterialTheme.typography.titleMedium)
                                Text(timeLabel(s.startsAt), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                            }
                            Column(Modifier.weight(1f)) {
                                Text(vm.curricula?.find(s.curriculum)?.name ?: s.batch.name, style = MaterialTheme.typography.bodyLarge)
                                Text(stringResource(R.string.minutes, s.minutes), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                            }
                        }
                    }
                }
            }
            TheStudio(home.studio, words)
            Spacer(Modifier.height(8.dp))
        }
    }
}

/** The next class. Its check-in (the mood before) is offered from an hour before it, with or without a link: Join asks
 *  it, then opens the class at once while the check-in goes in the background; with no link yet, the faces are shown
 *  as they are. */
@Composable
private fun NextClassCard(vm: AppViewModel, s: ClassSession, now: Instant) {
    val context = LocalContext.current
    var askMood by rememberSaveable(s.id) { mutableStateOf(false) }
    val live = now >= s.startsAt && now < s.endsAt
    // The "before" check-in opens an hour before class, as the server allows; earlier, Join just opens the link.
    val checkinOpen = now >= s.startsAt.minusSeconds(60 * 60) && now <= s.endsAt
    val link = s.meetLink
    SectionCard(tint = Palette.moss) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Label(stringResource(R.string.next_class), Palette.mossLight)
            Spacer(Modifier.weight(1f))
            if (live) Pill(stringResource(R.string.live_now), Palette.saffron, Color.White)
        }
        Text(s.batch.name, style = MaterialTheme.typography.headlineSmall, color = Color.White)
        Text(
            "${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)} · ${stringResource(R.string.minutes, s.minutes)}",
            style = MaterialTheme.typography.bodyLarge, color = Palette.mossLight,
        )
        Text(s.batch.about, style = MaterialTheme.typography.bodyMedium, color = Palette.mossLight)
        if (!live && now < s.startsAt) {
            Text(stringResource(R.string.starts_in, untilLabel(now, s.startsAt)), style = MaterialTheme.typography.titleMedium, color = Color.White)
        }
        if (s.checkedIn) Pill(stringResource(R.string.checked_in), Palette.mossLight, Palette.moss)

        if (askMood || (link == null && checkinOpen && !s.checkedIn)) {
            SectionCard(tint = Palette.paper) {
                Text(stringResource(R.string.how_feel_before), style = MaterialTheme.typography.titleMedium)
                MoodPicker(null) { mood ->
                    vm.checkIn(s.id, mood)
                    askMood = false
                    link?.let { openLink(context, it) }
                }
                if (link != null) TextButton(onClick = { askMood = false; openLink(context, link) }) { Text(stringResource(R.string.skip)) }
            }
        }
        when {
            link == null -> Text(stringResource(R.string.link_soon), style = MaterialTheme.typography.bodyMedium, color = Palette.mossLight)
            askMood -> {}
            else -> Button(
                onClick = { if (s.checkedIn || !checkinOpen) openLink(context, link) else askMood = true },
                colors = ButtonDefaults.buttonColors(containerColor = Palette.saffron),
                modifier = Modifier.fillMaxWidth().height(56.dp),
            ) {
                Icon(Icons.Filled.Videocam, null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.join_class))
            }
        }
    }
    vm.curricula?.let { curricula ->
        curricula.find(s.curriculum)?.let { plan ->
            SectionCard {
                Label(stringResource(R.string.sequence) + " · " + plan.name)
                Sequence(plan, curricula, vm.prefs.lang, collapsed = 3)
            }
        }
    }
}

/** For a student still waiting to be placed: Today and Practice say so, and offer the intake. */
@Composable
fun PendingCard(tellAbout: () -> Unit) {
    SectionCard(tint = Palette.saffronLight) {
        Text(stringResource(R.string.pending_title, LocalTeacher.current), style = MaterialTheme.typography.titleMedium)
        Text(stringResource(R.string.pending_body, LocalTeacher.current), style = MaterialTheme.typography.bodyMedium)
        Button(onClick = tellAbout, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.tell_about_you, LocalTeacher.current)) }
    }
}

/** The teacher and the meaning of the studio's name, in the studio's own words. */
@Composable
private fun TheStudio(studio: Studio, words: StudioWords) {
    Text(words.teacherHeading, style = MaterialTheme.typography.titleLarge)
    SectionCard(tint = Palette.mossLight) {
        Text(studio.teacherName, style = MaterialTheme.typography.titleLarge, color = Palette.moss)
        Text(studio.teacherTitle, style = MaterialTheme.typography.labelLarge, color = Palette.muted)
        Text(studio.teacherBio, style = MaterialTheme.typography.bodyLarge)
    }
    SectionCard(tint = Palette.cream) {
        Text(words.nameIsAMap, style = MaterialTheme.typography.titleMedium, color = Palette.moss)
        words.name.forEach { (devanagari, latin, meaning) ->
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(devanagari, style = MaterialTheme.typography.titleLarge, color = Palette.saffron, modifier = Modifier.width(80.dp))
                Column {
                    Text(latin, style = MaterialTheme.typography.titleMedium)
                    Text(meaning, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                }
            }
        }
    }
    Pill(stringResource(R.string.first_class_free), Palette.saffronLight, Palette.saffron)
}
