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
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.R
import java.util.Locale

@Composable
fun MeScreen(vm: AppViewModel, onLanguage: (String) -> Unit) {
    val user = vm.user ?: return
    var feedback by rememberSaveable { mutableStateOf("") }
    var server by rememberSaveable { mutableStateOf(vm.prefs.server) }
    val thanks = stringResource(R.string.feedback_thanks)

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

        Label(stringResource(R.string.language))
        LanguageChips(vm.prefs.lang, onLanguage)

        if (!user.isTeacher) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(stringResource(R.string.research), Modifier.weight(1f), style = MaterialTheme.typography.bodyLarge)
                Switch(user.researchConsent, { vm.setConsent(it) })
            }
        }

        SectionCard {
            Text(stringResource(R.string.feedback_title), style = MaterialTheme.typography.titleMedium)
            OutlinedTextField(feedback, { feedback = it }, placeholder = { Text(stringResource(R.string.feedback_hint)) }, minLines = 3, modifier = Modifier.fillMaxWidth())
            Button(onClick = { vm.sendFeedback("me", feedback, thanks); feedback = "" }, enabled = feedback.isNotBlank()) { Text(stringResource(R.string.send)) }
        }

        Label(stringResource(R.string.server))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(server, { server = it }, singleLine = true, modifier = Modifier.weight(1f))
            OutlinedButton(onClick = { vm.saveServer(server) }) { Text(stringResource(R.string.save)) }
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
