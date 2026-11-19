package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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

@Composable
fun MeScreen(vm: AppViewModel, onLanguage: (String) -> Unit) {
    val user = vm.user ?: return
    var feedback by rememberSaveable { mutableStateOf("") }
    var aboutMe by rememberSaveable { mutableStateOf(false) }
    if (aboutMe) return IntakeScreen(vm) { aboutMe = false }
    val thanks = stringResource(R.string.feedback_thanks)

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(user.name, style = MaterialTheme.typography.headlineSmall)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(user.phone, color = Palette.muted)
            Pill(stringResource(R.string.role_student))
        }

        OutlinedButton(onClick = { aboutMe = true }, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.about_me, LocalTeacher.current)) }

        HealthNotes(vm)

        Label(stringResource(R.string.language))
        LanguageChips(vm.prefs.lang, onLanguage)

        SectionCard {
            Text(stringResource(R.string.feedback_title), style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(feedback, { feedback = it }, placeholder = { Text(stringResource(R.string.feedback_hint)) }, minLines = 3, modifier = Modifier.fillMaxWidth())
            Button(onClick = { vm.sendFeedback(feedback, thanks); feedback = "" }, enabled = feedback.isNotBlank()) { Text(stringResource(R.string.send)) }
        }

        OutlinedButton(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.logout)) }
        Spacer(Modifier.height(8.dp))
    }
}

/** The student's health notes, kept on this phone: written here, or saved by the companion ("Remember that…"). */
@Composable
private fun HealthNotes(vm: AppViewModel) {
    var draft by rememberSaveable { mutableStateOf("") }
    // The note waiting for "Share" in the dialog. Not saveable: a note is not, and the dialog can simply be asked again.
    var sharing by remember { mutableStateOf<Note?>(null) }
    val sharedDone = stringResource(R.string.shared_note, LocalTeacher.current)
    sharing?.let { note ->
        AlertDialog(
            onDismissRequest = { sharing = null },
            title = { Text(stringResource(R.string.share_confirm_title, LocalTeacher.current)) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("“${note.text}”", style = MaterialTheme.typography.bodyLarge)
                    Text(stringResource(R.string.share_confirm_body, LocalTeacher.current), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                }
            },
            confirmButton = { TextButton(onClick = { vm.shareNote(note, sharedDone); sharing = null }) { Text(stringResource(R.string.share)) } },
            dismissButton = { TextButton(onClick = { sharing = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }

    Label(stringResource(R.string.memory_title))
    SectionCard {
        Text(stringResource(R.string.privacy, LocalTeacher.current), style = MaterialTheme.typography.bodyMedium, color = Palette.moss)
        if (vm.notes.isEmpty()) Text(stringResource(R.string.memory_empty, LocalTeacher.current), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        vm.notes.forEach { note ->
            HorizontalDivider(color = Palette.line)
            Text(note.text, style = MaterialTheme.typography.bodyLarge)
            Text(dayLabel(note.savedAt), style = MaterialTheme.typography.labelMedium, color = Palette.muted)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (note.sharedId != null) {
                    Pill("✓ " + stringResource(R.string.shared_note, LocalTeacher.current))
                } else {
                    TextButton(onClick = { sharing = note }, contentPadding = PaddingValues(horizontal = 0.dp)) {
                        Icon(Icons.AutoMirrored.Filled.Send, null, Modifier.size(16.dp))
                        Spacer(Modifier.width(6.dp))
                        Text(stringResource(R.string.share_note, LocalTeacher.current))
                    }
                }
                Spacer(Modifier.weight(1f))
                TextButton(onClick = { vm.forgetNote(note) }) { Text(stringResource(R.string.forget_note), color = Palette.muted) }
            }
        }
        HorizontalDivider(color = Palette.line)
        OutlinedTextField(draft, { draft = it }, placeholder = { Text(stringResource(R.string.note_hint)) }, minLines = 2, modifier = Modifier.fillMaxWidth())
        Button(onClick = { vm.addNote(draft); draft = "" }, enabled = draft.isNotBlank()) { Text(stringResource(R.string.save)) }
    }
}
