package com.sattchittanand.yoga.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ItemSummary
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.Student
import kotlin.math.roundToInt

/** The reaction word nearest an average on the 1 to 4 scale. */
@Composable
private fun reactionWord(average: Double) = stringResource(REACTIONS[(average.roundToInt() - 1).coerceIn(0, 3)])

/** Who wrote the feedback, as the viewer reads it: the teacher's name for a student, "You" for the teacher. */
@Composable
private fun wroteLabel(teacherViewing: Boolean) =
    if (teacherViewing) stringResource(R.string.you_wrote) else stringResource(R.string.teacher_wrote, LocalTeacher.current)

/** How often, in class and solo: "9 times in class · 5 solo". */
@Composable
private fun timesLine(inClass: Int, solo: Int) = listOfNotNull(
    pluralStringResource(R.plurals.times_in_class, inClass, inClass).takeIf { inClass > 0 },
    pluralStringResource(R.plurals.times_solo, solo, solo).takeIf { solo > 0 },
).joinToString(" · ")

/** Each item a student has practised: how often, the first reactions against the latest, strain or pain, whether
 *  the teacher wrote; with [collapsed], that many until "Show all". [teacherViewing] when the teacher reads it. */
@Composable
fun ItemList(vm: AppViewModel, items: List<ItemSummary>, teacherViewing: Boolean, collapsed: Int = items.size, open: (String) -> Unit) {
    val curricula = vm.curricula ?: return
    if (items.isEmpty()) {
        Text(stringResource(R.string.no_items), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        return
    }
    var all by rememberSaveable { mutableStateOf(false) }
    SectionCard {
        (if (all) items else items.take(collapsed)).forEachIndexed { i, s ->
            if (i > 0) HorizontalDivider(color = Palette.line)
            Column(Modifier.fillMaxWidth().clickable { open(s.item) }.padding(vertical = 4.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(curricula.library[s.item]?.title(vm.prefs.lang) ?: s.item, style = MaterialTheme.typography.bodyLarge)
                Text(listOfNotNull(timesLine(s.inClass, s.solo).ifEmpty { null }, s.trend?.let { "${reactionWord(it.early)} → ${reactionWord(it.recent)}" })
                    .joinToString(" · "),
                    style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                if (s.painTimes > 0) Text(pluralStringResource(R.plurals.pain_times, s.painTimes, s.painTimes), style = MaterialTheme.typography.bodyMedium, color = Palette.danger)
                if (s.teacherSaid != null) Text(wroteLabel(teacherViewing), style = MaterialTheme.typography.labelMedium, color = Palette.moss)
            }
        }
        if (items.size > collapsed) {
            TextButton(onClick = { all = !all }) {
                Text(if (all) stringResource(R.string.show_less) else stringResource(R.string.show_all, items.size))
            }
        }
    }
}

/** One item's history for one student: the summary, the teacher's feedback, and each time, newest first. For the
 *  teacher ([student] given), a box to write feedback on it. */
@Composable
fun ItemHistoryScreen(vm: AppViewModel, item: String, student: Student?) {
    LaunchedEffect(item, student) { vm.loadItem(item, student?.user?.id) }
    val h = vm.itemHistory?.takeIf { it.item == item }
    val title = vm.curricula?.library?.get(item)?.title(vm.prefs.lang) ?: item
    var draft by rememberSaveable(item) { mutableStateOf("") }
    val sent = stringResource(R.string.feedback_sent)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        student?.let { Label(it.user.name) }
        Text(title, style = MaterialTheme.typography.headlineSmall)
        if (h == null) return@Column
        Text(listOfNotNull(timesLine(h.inClass, h.solo).ifEmpty { null }, h.first?.let { stringResource(R.string.since, dayLabel(it)) })
            .joinToString(" · "), style = MaterialTheme.typography.bodyLarge)
        h.trend?.let { Text(stringResource(R.string.trend_line, reactionWord(it.early), reactionWord(it.recent)), style = MaterialTheme.typography.bodyLarge, color = Palette.moss) }
        h.holds?.let { Text(stringResource(R.string.holds_line, stopwatch(it.longest), stopwatch(it.recent)), style = MaterialTheme.typography.bodyLarge) }
        if (h.painTimes > 0) Text(pluralStringResource(R.plurals.pain_times, h.painTimes, h.painTimes), color = Palette.danger)
        if (h.feedback.isNotEmpty()) {
            Label(wroteLabel(student != null))
            h.feedback.forEach { (date, text) ->
                SectionCard(tint = Palette.mossLight) {
                    Text("“$text”", style = MaterialTheme.typography.bodyLarge)
                    Text(dayLabel(date), style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                }
            }
        }
        if (student != null) {
            val about = vm.curricula?.library?.get(item)?.short(vm.prefs.lang) ?: item
            OutlinedTextField(draft, { draft = it }, placeholder = { Text(stringResource(R.string.feedback_for, student.user.name.substringBefore(' '), about)) },
                minLines = 2, modifier = Modifier.fillMaxWidth())
            Button(onClick = { vm.sendItemFeedback(student.user.id, item, draft, sent); draft = "" }, enabled = draft.isNotBlank() && !vm.busy) {
                Text(stringResource(R.string.send))
            }
        }
        if (h.entries.isNotEmpty()) {
            Label(stringResource(R.string.each_time))
            SectionCard {
                h.entries.forEachIndexed { i, e ->
                    if (i > 0) HorizontalDivider(color = Palette.line)
                    Row(verticalAlignment = Alignment.Top) {
                        Text(dayLabel(e.date), Modifier.weight(0.4f), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                        Column(Modifier.weight(0.6f)) {
                            if (e.solo) {
                                Text(e.heldSeconds?.let { stringResource(R.string.solo_held, stopwatch(it)) } ?: stringResource(R.string.solo),
                                    style = MaterialTheme.typography.labelMedium, color = Palette.moss)
                            }
                            e.reaction?.let { Text(stringResource(REACTIONS[it - 1]), style = MaterialTheme.typography.bodyLarge) }
                            if (e.pain) Text(stringResource(R.string.pain_flag), style = MaterialTheme.typography.bodyMedium, color = Palette.danger)
                            e.note?.let { Text("“$it”", style = MaterialTheme.typography.bodyMedium) }
                        }
                    }
                }
            }
        }
    }
}
