package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ClassSession
import com.sattchittanand.yoga.ItemFeedback
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.Said

/** After class: the mood now, then how each item of the class's curriculum went. Every part can be skipped. With
 *  [before], what was said already, to change. */
@Composable
fun AfterClassScreen(vm: AppViewModel, session: ClassSession, before: Said?, close: () -> Unit) {
    val curricula = vm.curricula
    val plan = curricula?.find(session.curriculum)
    var mood by rememberSaveable(session.id) { mutableStateOf(before?.mood) }
    val said = remember(session.id) { mutableStateMapOf<String, ItemFeedback>().apply { before?.items?.forEach { put(it.item, it) } } }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Column {
                BackHeader(stringResource(R.string.how_did_it_go), close)
                Text(session.batch.name, style = MaterialTheme.typography.bodyLarge, color = Palette.muted)
            }
        }
        item {
            SectionCard(tint = Palette.saffronLight) {
                Text(stringResource(R.string.how_feel_after), style = MaterialTheme.typography.titleMedium)
                MoodPicker(mood) { mood = it }
            }
        }
        if (curricula != null && plan != null) {
            item { Text(stringResource(R.string.after_class_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted) }
            items(plan.items, key = { it.item }) { p ->
                val title = curricula.library[p.item]?.title(vm.prefs.lang) ?: p.item
                ItemCard(title, said[p.item] ?: ItemFeedback(p.item, null, false, "")) { said[p.item] = it }
            }
        }
        item {
            Spacer(Modifier.height(4.dp))
            Button(onClick = { vm.sendAfterClass(session.id, mood, said.values.toList(), before != null, close) }, enabled = !vm.busy,
                modifier = Modifier.fillMaxWidth().height(52.dp)) { Text(stringResource(R.string.done)) }
        }
    }
}

/** One item: its four reactions in a row (tap again to clear), strain or pain, and a note. */
@Composable
private fun ItemCard(title: String, f: ItemFeedback, change: (ItemFeedback) -> Unit) {
    var noting by rememberSaveable(f.item) { mutableStateOf(f.note.isNotEmpty()) } // open when changing a note said before
    SectionCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(title, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
            if (!noting) TextButton(onClick = { noting = true }) { Text(stringResource(R.string.add_note)) }
        }
        Choices(REACTIONS.map { stringResource(it) }, f.reaction?.minus(1)) { i ->
            change(f.copy(reaction = if (f.reaction == i + 1) null else i + 1))
        }
        FilterChip(
            selected = f.pain, onClick = { change(f.copy(pain = !f.pain)) }, label = { Text(stringResource(R.string.pain_flag)) },
            colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Palette.danger, selectedLabelColor = Color.White),
        )
        if (noting) OutlinedTextField(f.note, { change(f.copy(note = it)) }, modifier = Modifier.fillMaxWidth(), minLines = 2)
    }
}
