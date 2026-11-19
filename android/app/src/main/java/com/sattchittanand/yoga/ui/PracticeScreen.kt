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
        ItemHistoryScreen(vm, item, null)
        return
    }
    LaunchedEffect(Unit) {
        vm.loadPractice()
        vm.loadItems()
    }
    val stats = vm.stats ?: return
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.my_practice), style = MaterialTheme.typography.headlineSmall)
        Button(onClick = { choosing = true }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.practise_alone)) }
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatTile(stats.classesJoined.toString(), stringResource(R.string.classes_joined), Modifier.weight(1f))
            StatTile(stats.streakDays.toString(), stringResource(R.string.streak), Modifier.weight(1f))
            StatTile(stats.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–", stringResource(R.string.mood_lift), Modifier.weight(1f))
        }
        Text(stringResource(R.string.mood_lift_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        Label(stringResource(R.string.each_item))
        ItemList(vm, vm.items, teacherViewing = false, collapsed = 6) { open = it }
        val days = (vm.practice.map { it.date } + vm.soloSessions.map { it.date }).distinct().sortedDescending()
        if (days.isNotEmpty()) {
            Label(stringResource(R.string.last_two_weeks))
            SectionCard {
                var first = true
                days.forEach { day ->
                    vm.soloSessions.filter { it.date == day }.forEach { // in the evening, after the day's class
                        if (!first) HorizontalDivider(color = Palette.line)
                        first = false
                        SoloDay(it)
                    }
                    vm.practice.filter { it.date == day }.forEach {
                        if (!first) HorizontalDivider(color = Palette.line)
                        first = false
                        ClassMoods(it)
                    }
                }
            }
        }
    }
}

@Composable
private fun SoloDay(s: SoloSession) {
    Column {
        Text(stringResource(R.string.solo_row, stringResource(R.string.minutes, s.minutes)), style = MaterialTheme.typography.bodyLarge)
        Text(dayLabel(s.date) + " · " + s.items.joinToString(", "), style = MaterialTheme.typography.bodyMedium, color = Palette.muted,
            maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun ClassMoods(c: JoinedClass) {
    val words = listOf(R.string.mood_1, R.string.mood_2, R.string.mood_3, R.string.mood_4, R.string.mood_5).map { stringResource(it) }
    val spoken = "${stringResource(R.string.before)}: ${words[c.moodBefore - 1]}. ${stringResource(R.string.after)}: ${c.moodAfter?.let { words[it - 1] } ?: "–"}."
    Row(verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(c.name, style = MaterialTheme.typography.bodyLarge)
            Text(dayLabel(c.date), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }
        Text("${MOODS[c.moodBefore - 1]} → ${c.moodAfter?.let { MOODS[it - 1] } ?: "–"}", fontSize = 22.sp, modifier = Modifier.semantics { contentDescription = spoken })
    }
}
