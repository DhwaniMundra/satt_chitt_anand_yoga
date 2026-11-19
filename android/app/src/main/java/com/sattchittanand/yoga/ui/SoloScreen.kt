package com.sattchittanand.yoga.ui

import android.os.SystemClock
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.SoloRun
import kotlinx.coroutines.delay

private val TYPES = listOf("asana" to R.string.type_asana, "pranayama" to R.string.type_pranayama, "meditation" to R.string.type_meditation)

/** Choosing what to practise on one's own: the last class again, a whole sequence, or items found in the library.
 *  [close] when leaving it, or once the practice has started. */
@Composable
fun SoloChoose(vm: AppViewModel, close: () -> Unit) {
    BackHandler(onBack = close)
    val curricula = vm.curricula ?: return Waiting(vm, vm::refresh)
    val lang = vm.prefs.lang
    var chosen by rememberSaveable { mutableStateOf(listOf<String>()) }
    var from by rememberSaveable { mutableStateOf<String?>(null) } // the sequence repeated, for its doses and cues
    var query by rememberSaveable { mutableStateOf("") }
    val repeat = { key: String ->
        from = key
        chosen = curricula.find(key)?.items?.map { it.item }.orEmpty()
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.practise_alone), style = MaterialTheme.typography.headlineSmall)
        Text(stringResource(R.string.solo_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        vm.practice.firstOrNull { it.curriculum != null }?.let { last ->
            OutlinedButton(onClick = { repeat(last.curriculum!!) }, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.repeat_last, last.name), textAlign = TextAlign.Center)
            }
        }
        Label(stringResource(R.string.repeat_sequence))
        val keys = curricula.curricula.map { it.key }
        Choices(curricula.curricula.map { it.name }, keys.indexOf(from).takeIf { it >= 0 }) { repeat(keys[it]) }
        Label(stringResource(R.string.choose_items))
        OutlinedTextField(query, { query = it }, placeholder = { Text(stringResource(R.string.search_library)) }, singleLine = true,
            modifier = Modifier.fillMaxWidth())
        val found = curricula.library.values.filter { it.key !in chosen && it.matches(query) }
        TYPES.forEach { (type, heading) ->
            val some = found.filter { it.type == type }
            if (some.isNotEmpty()) {
                Text(stringResource(heading), style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                some.forEach { item ->
                    Text("+ " + item.title(lang), Modifier.fillMaxWidth().clickable { chosen = chosen + item.key }.padding(vertical = 8.dp),
                        style = MaterialTheme.typography.bodyLarge, color = Palette.moss)
                }
            }
        }
        Button(onClick = { vm.solo = SoloRun.start(chosen, from, SystemClock.elapsedRealtime()); close() }, enabled = chosen.isNotEmpty(),
            modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.start_count, chosen.size))
        }
        if (chosen.isNotEmpty()) {
            Label(stringResource(R.string.your_list))
            SectionCard {
                chosen.forEachIndexed { i, key ->
                    if (i > 0) HorizontalDivider(color = Palette.line)
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(curricula.library[key]?.title(lang) ?: key, Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                        TextButton(onClick = { chosen = chosen - key }) { Text(stringResource(R.string.remove)) }
                    }
                }
            }
        }
    }
}

/** One item at a time: its dose and cue when it comes from a sequence, the stopwatch, how it went, strain or pain and
 *  a note; Back, Next, and Finish, which sends it all. Leaving before Finish asks first: nothing is saved until then. */
@Composable
fun SoloPractise(vm: AppViewModel, run: SoloRun) {
    var leaving by remember { mutableStateOf(false) }
    BackHandler { leaving = true }
    if (leaving) {
        AlertDialog(
            onDismissRequest = { leaving = false },
            title = { Text(stringResource(R.string.leave_title)) },
            text = { Text(stringResource(R.string.leave_body)) },
            confirmButton = { TextButton(onClick = { leaving = false; vm.solo = null }) { Text(stringResource(R.string.leave)) } },
            dismissButton = { TextButton(onClick = { leaving = false }) { Text(stringResource(R.string.keep_going)) } },
        )
    }
    val curricula = vm.curricula ?: return Waiting(vm, vm::refresh)
    val f = run.current
    var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(run.runningSince) {
        while (run.runningSince != null) {
            now = SystemClock.elapsedRealtime()
            delay(200)
        }
    }
    val update = { next: SoloRun -> vm.solo = next }
    val last = run.at == run.said.size - 1
    val saved = stringResource(R.string.solo_saved)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Label(stringResource(R.string.item_of, run.at + 1, run.said.size))
        Text(curricula.library[f.item]?.title(vm.prefs.lang) ?: f.item, style = MaterialTheme.typography.headlineSmall)
        curricula.find(run.curriculum)?.items?.firstOrNull { it.item == f.item }?.let {
            Text(doseLabel(it.dose, it.unit) + " · " + it.cue, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }
        Text(stopwatch((run.held(now) / 1000).toInt()), Modifier.fillMaxWidth(), style = MaterialTheme.typography.displayMedium, textAlign = TextAlign.Center)
        Button(onClick = { update(run.toggled(SystemClock.elapsedRealtime())) }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(if (run.runningSince == null) R.string.watch_start else R.string.watch_stop))
        }
        Label(stringResource(R.string.how_did_it_go))
        Choices(REACTIONS.map { stringResource(it) }, f.reaction?.minus(1)) { i ->
            update(run.changed(f.copy(reaction = if (f.reaction == i + 1) null else i + 1)))
        }
        FilterChip(
            selected = f.pain, onClick = { update(run.changed(f.copy(pain = !f.pain))) }, label = { Text(stringResource(R.string.pain_flag)) },
            colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Palette.danger, selectedLabelColor = Color.White),
        )
        OutlinedTextField(f.note, { update(run.changed(f.copy(note = it))) }, placeholder = { Text(stringResource(R.string.add_note)) },
            modifier = Modifier.fillMaxWidth(), minLines = 2)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            if (run.at > 0) {
                OutlinedButton(onClick = { update(run.moved(run.at - 1, SystemClock.elapsedRealtime())) }, Modifier.weight(1f)) { Text(stringResource(R.string.back)) }
            }
            Button(onClick = { if (last) vm.finishSolo(saved) else update(run.moved(run.at + 1, SystemClock.elapsedRealtime())) },
                Modifier.weight(1f), enabled = !vm.busy) {
                Text(stringResource(if (last) R.string.finish else R.string.next))
            }
        }
        if (!last) TextButton(onClick = { vm.finishSolo(saved) }, enabled = !vm.busy) { Text(stringResource(R.string.finish_here)) }
    }
}
