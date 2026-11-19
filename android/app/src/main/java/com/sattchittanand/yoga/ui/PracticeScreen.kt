package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.JoinedClass
import com.sattchittanand.yoga.R
import java.util.Locale

/** The student's practice: the totals, then each class of the last two weeks with the mood before and after. */
@Composable
fun PracticeScreen(vm: AppViewModel) {
    LaunchedEffect(Unit) { vm.loadPractice() }
    val stats = vm.stats ?: return
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.my_practice), style = MaterialTheme.typography.headlineSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatTile(stats.classesJoined.toString(), stringResource(R.string.classes_joined), Modifier.weight(1f))
            StatTile(stats.streakDays.toString(), stringResource(R.string.streak), Modifier.weight(1f))
            StatTile(stats.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–", stringResource(R.string.mood_lift), Modifier.weight(1f))
        }
        Text(stringResource(R.string.mood_lift_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        if (vm.practice.isNotEmpty()) {
            Label(stringResource(R.string.last_two_weeks))
            SectionCard {
                vm.practice.forEachIndexed { i, c ->
                    if (i > 0) HorizontalDivider(color = Palette.line)
                    ClassMoods(c)
                }
            }
        }
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
