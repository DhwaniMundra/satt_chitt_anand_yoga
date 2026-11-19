package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.TextButton
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.Note
import com.sattchittanand.yoga.R
import java.util.Locale

@Composable
fun MeScreen(vm: AppViewModel, onLanguage: (String) -> Unit) {
    val user = vm.user ?: return
    var feedback by rememberSaveable { mutableStateOf("") }
    val thanks = stringResource(R.string.feedback_thanks)
    val sharedDone = stringResource(R.string.shared_note)
    // The note waiting for "Share" in the dialog. Not saveable: a note is not, and the dialog can simply be asked again.
    var sharing by remember { mutableStateOf<Note?>(null) }
    LaunchedEffect(user.isTeacher) { if (!user.isTeacher) vm.loadNotes() }
    sharing?.let { note ->
        AlertDialog(
            onDismissRequest = { sharing = null },
            title = { Text(stringResource(R.string.share_confirm_title)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("“${note.text}”", style = MaterialTheme.typography.bodyLarge)
                    Text(stringResource(R.string.share_confirm_body), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                }
            },
            confirmButton = { TextButton(onClick = { vm.shareNote(note, sharedDone); sharing = null }) { Text(stringResource(R.string.share)) } },
            dismissButton = { TextButton(onClick = { sharing = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(user.name, style = MaterialTheme.typography.headlineSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(user.phone, color = Palette.muted)
            Pill(stringResource(if (user.isTeacher) R.string.role_teacher else R.string.role_student))
        }

        vm.stats?.takeIf { !user.isTeacher }?.let { stats ->
            Label(stringResource(R.string.my_practice))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                StatTile(stats.classesJoined.toString(), stringResource(R.string.classes_joined), Modifier.weight(1f))
                StatTile(stats.streakDays.toString(), stringResource(R.string.streak), Modifier.weight(1f))
                StatTile(stats.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–", stringResource(R.string.mood_lift), Modifier.weight(1f))
            }
            Text(stringResource(R.string.mood_lift_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }

        if (!user.isTeacher) {
            Label(stringResource(R.string.memory_title))
            SectionCard {
                Text(stringResource(R.string.memory_private), style = MaterialTheme.typography.bodyMedium, color = Palette.moss)
                if (vm.notes.isEmpty()) Text(stringResource(R.string.memory_empty), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                vm.notes.forEach { note ->
                    HorizontalDivider(color = Palette.line)
                    Row(verticalAlignment = Alignment.Top) {
                        Column(Modifier.weight(1f).padding(top = 8.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(note.text, style = MaterialTheme.typography.bodyLarge)
                            Text(dayLabel(note.savedAt), style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                            if (note.sharedId != null) {
                                Pill("✓ " + stringResource(R.string.shared_note))
                            } else {
                                TextButton(onClick = { sharing = note }, contentPadding = PaddingValues(horizontal = 0.dp)) {
                                    Icon(Icons.AutoMirrored.Filled.Send, null, Modifier.size(16.dp))
                                    Spacer(Modifier.width(6.dp))
                                    Text(stringResource(R.string.share_note))
                                }
                            }
                        }
                        IconButton(onClick = { vm.forgetNote(note) }) {
                            Icon(Icons.Filled.Close, stringResource(R.string.forget_note), tint = Palette.muted)
                        }
                    }
                }
            }
        }

        Label(stringResource(R.string.language))
        LanguageChips(vm.prefs.lang, onLanguage)

        SectionCard {
            Text(stringResource(R.string.feedback_title), style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(feedback, { feedback = it }, placeholder = { Text(stringResource(R.string.feedback_hint)) }, minLines = 3, modifier = Modifier.fillMaxWidth())
            Button(onClick = { vm.sendFeedback("me", feedback, thanks); feedback = "" }, enabled = feedback.isNotBlank()) { Text(stringResource(R.string.send)) }
        }

        OutlinedButton(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.logout)) }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
fun StatTile(value: String, label: String, modifier: Modifier = Modifier) {
    SectionCard(modifier, tint = Palette.mossLight) {
        Text(value, style = MaterialTheme.typography.headlineSmall, color = Palette.moss)
        Text(label, style = MaterialTheme.typography.labelMedium, color = Palette.muted)
    }
}
