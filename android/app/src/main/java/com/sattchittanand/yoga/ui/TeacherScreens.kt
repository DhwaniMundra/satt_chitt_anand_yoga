package com.sattchittanand.yoga.ui

import androidx.compose.foundation.clickable
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
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ClassSession
import com.sattchittanand.yoga.R
import java.util.Locale
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TeacherClassesScreen(vm: AppViewModel, openStudents: () -> Unit) {
    val home = vm.teacherHome ?: return
    var expanded by rememberSaveable { mutableStateOf(home.sessions.firstOrNull()?.id ?: -1) }
    PullToRefreshBox(isRefreshing = vm.busy, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Label(stringResource(R.string.brand_latin), Palette.saffron)
            Text(stringResource(R.string.classes_title), style = MaterialTheme.typography.headlineSmall)
            if (home.pendingStudents > 0) {
                SectionCard(Modifier.clickable(onClick = openStudents), tint = Palette.saffronLight) {
                    Text("${home.pendingStudents} · ${stringResource(R.string.waiting)}", style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.students_title), color = Palette.muted)
                }
            }
            home.sessions.forEach { s ->
                SessionCard(vm, s, expanded == s.id, home.settings.defaultMeetLink) { expanded = if (expanded == s.id) -1 else s.id }
            }
            GroupCard(vm)
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun SessionCard(vm: AppViewModel, s: ClassSession, open: Boolean, standingLink: String?, toggle: () -> Unit) {
    val context = LocalContext.current
    var link by rememberSaveable(s.id) { mutableStateOf(if (s.ownLink) s.meetLink ?: "" else "") }
    SectionCard(Modifier.clickable(onClick = toggle), tint = if (open) Palette.paper else Palette.cream) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)}", style = MaterialTheme.typography.labelLarge, color = Palette.muted)
                Text(s.info.name, style = MaterialTheme.typography.titleLarge)
            }
            if (s.joined > 0) Pill(stringResource(R.string.joined_count, s.joined))
        }
        val status = when {
            s.ownLink -> s.meetLink!!
            standingLink != null -> stringResource(R.string.uses_standing_link)
            else -> stringResource(R.string.no_link_yet)
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Dot(if (s.hasLink) Palette.moss else Palette.saffron)
            Text(status, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }
        if (open) {
            OutlinedTextField(
                link, { link = it }, label = { Text(stringResource(R.string.meet_link)) },
                placeholder = { Text("meet.google.com/abc-defg-hij") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            vm.error?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error) }
            Button(
                onClick = { vm.saveLinkAndShare(s.id, link) { shareToWhatsApp(context, it) } },
                enabled = link.isNotBlank() && !vm.busy,
                colors = ButtonDefaults.buttonColors(containerColor = Palette.saffron),
                modifier = Modifier.fillMaxWidth().height(52.dp),
            ) {
                Icon(Icons.AutoMirrored.Filled.Send, null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.save_share))
            }
            if (s.hasLink) {
                OutlinedButton(onClick = { vm.shareSession(s.id) { shareToWhatsApp(context, it) } }, modifier = Modifier.fillMaxWidth()) {
                    Text(stringResource(R.string.share_whatsapp))
                }
            }
        }
    }
}

@Composable
private fun GroupCard(vm: AppViewModel) {
    val settings = vm.teacherHome?.settings ?: return
    val context = LocalContext.current
    var standing by rememberSaveable { mutableStateOf(settings.defaultMeetLink ?: "") }
    var group by rememberSaveable { mutableStateOf(settings.groupLink ?: "") }
    val saved = stringResource(R.string.saved)
    Label(stringResource(R.string.settings_title))
    SectionCard {
        OutlinedTextField(
            standing, { standing = it }, label = { Text(stringResource(R.string.standing_link)) },
            supportingText = { Text(stringResource(R.string.standing_link_help)) }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            group, { group = it }, label = { Text(stringResource(R.string.group_link)) },
            placeholder = { Text("chat.whatsapp.com/…") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        Button(onClick = { vm.saveSettings(group, standing, saved) }, enabled = !vm.busy) { Text(stringResource(R.string.save)) }
        HorizontalDivider(color = Palette.line)
        Label(stringResource(R.string.group_code_label))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(settings.groupCode, style = MaterialTheme.typography.displaySmall.copy(letterSpacing = 6.sp), color = Palette.moss, modifier = Modifier.weight(1f))
            TextButton(onClick = vm::newGroupCode) {
                Icon(Icons.Filled.Refresh, null)
                Text(stringResource(R.string.new_code))
            }
        }
        OutlinedButton(onClick = { vm.shareInvite { shareToWhatsApp(context, it) } }, modifier = Modifier.fillMaxWidth()) {
            Text(stringResource(R.string.invite_students))
        }
    }
}

@Composable
fun StudentsScreen(vm: AppViewModel) {
    LaunchedEffect(Unit) { vm.loadStudents() }
    var shownPassword by remember { mutableStateOf<Pair<String, String>?>(null) } // (name, new password)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.students_title), style = MaterialTheme.typography.headlineSmall)
        if (vm.students.isEmpty() && !vm.busy) Text(stringResource(R.string.no_students), color = Palette.muted)
        vm.students.forEach { (student, joined) ->
            SectionCard(tint = if (student.status == "pending") Palette.saffronLight else Palette.paper) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(student.name, style = MaterialTheme.typography.titleMedium)
                        Text("${student.phone} · ${stringResource(R.string.joined_count, joined)}", style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                    }
                    Pill(
                        stringResource(
                            when (student.status) {
                                "pending" -> R.string.waiting
                                "approved" -> R.string.approved
                                else -> R.string.removed
                            },
                        ),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (student.status != "approved") Button(onClick = { vm.setStudentStatus(student.id, "approved") }) { Text(stringResource(R.string.approve)) }
                    if (student.status != "rejected") OutlinedButton(onClick = { vm.setStudentStatus(student.id, "rejected") }) { Text(stringResource(R.string.remove)) }
                    TextButton(onClick = { vm.resetPassword(student.id) { shownPassword = student.name to it } }) { Text(stringResource(R.string.new_password)) }
                }
            }
        }
    }
    shownPassword?.let { (name, password) ->
        AlertDialog(
            onDismissRequest = { shownPassword = null },
            confirmButton = { TextButton(onClick = { shownPassword = null }) { Text("OK") } },
            text = { Text(stringResource(R.string.new_password_is, name, password), style = MaterialTheme.typography.titleMedium) },
        )
    }
}

@Composable
fun InsightsScreen(vm: AppViewModel) {
    LaunchedEffect(Unit) { vm.loadInsights() }
    val data = vm.insights
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.insights_title), style = MaterialTheme.typography.headlineSmall)
        if (data == null) return@Column
        Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            StatTile(data.approved.toString(), stringResource(R.string.students_title), Modifier.weight(1f))
            StatTile(data.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–", stringResource(R.string.avg_lift), Modifier.weight(1f))
            StatTile(data.questions.toString(), stringResource(R.string.questions_asked), Modifier.weight(1f))
        }
        if (data.moodPairs > 0) Text(stringResource(R.string.pairs, data.moodPairs), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)

        Label(stringResource(R.string.last_two_weeks))
        val withCheckins = data.sessions.filter { it.joined > 0 }
        if (withCheckins.isEmpty()) Text(stringResource(R.string.no_data), color = Palette.muted)
        withCheckins.forEach { s ->
            SectionCard {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(s.className, style = MaterialTheme.typography.titleMedium)
                        Text("${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)}", style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                    }
                    Pill(stringResource(R.string.joined_count, s.joined))
                }
                MoodRow(stringResource(R.string.before), s.moodBefore, Palette.moss)
                MoodRow(stringResource(R.string.after), s.moodAfter, Palette.saffron)
            }
        }

        if (data.feedback.isNotEmpty()) {
            Label(stringResource(R.string.what_students_said))
            data.feedback.forEach { f ->
                SectionCard(tint = Palette.cream) {
                    Text("“${f.text}”", style = MaterialTheme.typography.bodyLarge)
                    Text(f.name, style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                }
            }
        }
        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun MoodRow(label: String, mood: Double?, color: Color) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(label, Modifier.width(72.dp), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        Bar(((mood ?: 0.0) / 5.0).toFloat(), color, Modifier.weight(1f))
        Text(mood?.let { MOODS[(it.roundToInt() - 1).coerceIn(0, 4)] + String.format(Locale.US, " %.1f", it) } ?: "–", Modifier.width(64.dp))
    }
}
