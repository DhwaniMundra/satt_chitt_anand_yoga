package com.sattchittanand.yoga.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.JoinedClass
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.SoloSession
import java.util.Locale

/** The student's practice: practice on one's own, the totals, how each item has gone (each opens its history), then
 *  the last two weeks: each class with the mood before and after, and each session on one's own. */
@Composable
fun PracticeScreen(vm: AppViewModel) {
    var open by rememberSaveable { mutableStateOf<String?>(null) }
    var choosing by rememberSaveable { mutableStateOf(false) }
    var aboutMe by rememberSaveable { mutableStateOf(false) }
    if (aboutMe) return IntakeScreen(vm) { aboutMe = false }
    if (vm.user?.isApproved != true) { // nothing to show, nor to send, until the teacher places them
        Column(Modifier.fillMaxSize().padding(20.dp)) { PendingCard { aboutMe = true } }
        return
    }
    vm.solo?.let {
        SoloPractise(vm, it)
        return
    }
    if (choosing) {
        SoloChoose(vm) { choosing = false }
        return
    }
    open?.let { item ->
        BackHandler { open = null }
        ItemHistoryScreen(vm, item, null) { open = null }
        return
    }
    LaunchedEffect(Unit) {
        vm.loadPractice()
        vm.loadItems()
    }
    val stats = vm.stats ?: return Waiting(vm, vm::refresh)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.my_practice), style = MaterialTheme.typography.headlineSmall)
        SendError(vm)
        Button(onClick = { choosing = true }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.practise_alone)) }
        StatTiles(
            stats.classesJoined.toString() to stringResource(R.string.classes_joined),
            stats.streakDays.toString() to stringResource(R.string.streak),
            (stats.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–") to stringResource(R.string.mood_lift),
        )
        Text(stringResource(R.string.mood_lift_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        Label(stringResource(R.string.each_item))
        ItemList(vm, vm.items, teacherViewing = false, reload = { vm.loadItems() }, collapsed = 6) { open = it }
        val history = (vm.practice.map { it.at to it } + vm.soloSessions.map { it.at to it }).sortedByDescending { it.first }
        if (history.isNotEmpty()) {
            Label(stringResource(R.string.last_two_weeks))
            SectionCard {
                history.forEachIndexed { i, (_, entry) ->
                    if (i > 0) HorizontalDivider(color = Palette.line)
                    if (entry is SoloSession) SoloDay(entry) else ClassMoods(entry as JoinedClass)
                }
            }
        }
    }
}

@Composable
private fun SoloDay(s: SoloSession) {
    Column {
        Text(stringResource(R.string.solo_row, stringResource(R.string.minutes, s.minutes)), style = MaterialTheme.typography.bodyLarge)
        Text(dayLabel(s.at) + " · " + s.items.joinToString(", "), style = MaterialTheme.typography.bodyMedium, color = Palette.muted,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun ClassMoods(c: JoinedClass) {
    val words = listOf(R.string.mood_1, R.string.mood_2, R.string.mood_3, R.string.mood_4, R.string.mood_5).map { stringResource(it) }
    // A mood may be missing: none after, if not given; none before, for a class said after without checking in first.
    fun word(mood: Int?) = mood?.takeIf { it in 1..5 }?.let { words[it - 1] } ?: "–"
    fun face(mood: Int?) = mood?.takeIf { it in 1..5 }?.let { MOODS[it - 1] } ?: "–"
    val spoken = "${stringResource(R.string.before)}: ${word(c.moodBefore)}. ${stringResource(R.string.after)}: ${word(c.moodAfter)}."
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(c.name, style = MaterialTheme.typography.bodyLarge)
            Text(dayLabel(c.at), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }
        Text("${face(c.moodBefore)} → ${face(c.moodAfter)}", fontSize = 22.sp, modifier = Modifier.semantics { contentDescription = spoken })
    }
}
