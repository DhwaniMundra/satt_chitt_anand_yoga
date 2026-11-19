package com.sattchittanand.yoga.ui

import androidx.activity.compose.BackHandler
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
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ClassSession
import com.sattchittanand.yoga.Intake
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.User
import com.sattchittanand.yoga.Student
import java.util.Locale
import kotlin.math.roundToInt

@OptIn(ExperimentalMaterial3Api::class)
/** The teacher's day: the next day's classes, one per batch, each with its curriculum and its Meet link to share; each
 *  batch's everyday link and the group settings; the language and signing out. */
@Composable
fun TeacherTodayScreen(vm: AppViewModel, onLanguage: (String) -> Unit, openStudents: () -> Unit) {
    val home = vm.teacherHome ?: return Waiting(vm, vm::refresh)
    // The soonest class is open by default, and again whenever a sooner one appears.
    var expanded by rememberSaveable(home.sessions.firstOrNull()?.id) { mutableStateOf(home.sessions.firstOrNull()?.id ?: -1) }
    PullToRefreshBox(isRefreshing = vm.busy, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            Label(stringResource(R.string.brand_latin), Palette.saffron)
            Text(stringResource(R.string.classes_title), style = MaterialTheme.typography.headlineSmall)
            if (home.pendingStudents > 0) {
                SectionCard(Modifier.clickable(onClick = openStudents), tint = Palette.saffronLight) {
                    Text(pluralStringResource(R.plurals.students_waiting, home.pendingStudents, home.pendingStudents),
                        style = MaterialTheme.typography.titleMedium)
                }
            }
            home.sessions.forEach { s ->
                SessionCard(vm, s, expanded == s.id, home.batch(s.batch.key)?.meetLink) { expanded = if (expanded == s.id) -1 else s.id }
            }
            GroupCard(vm)
            Label(stringResource(R.string.language))
            LanguageChips(vm.prefs.lang, onLanguage)
            OutlinedButton(onClick = vm::logout, modifier = Modifier.fillMaxWidth()) { Text(stringResource(R.string.logout)) }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@Composable
private fun SessionCard(vm: AppViewModel, s: ClassSession, open: Boolean, batchLink: String?, toggle: () -> Unit) {
    val context = LocalContext.current
    var link by rememberSaveable(s.id) { mutableStateOf(if (s.ownLink) s.meetLink ?: "" else "") }
    SectionCard(Modifier.clickable(onClick = toggle), tint = if (open) Palette.paper else Palette.cream) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)}", style = MaterialTheme.typography.labelLarge, color = Palette.muted)
                Text(s.batch.name, style = MaterialTheme.typography.titleLarge)
            }
            if (s.joined > 0) Pill(pluralStringResource(R.plurals.joined_count, s.joined, s.joined))
        }
        val status = when {
            s.ownLink -> s.meetLink!!
            batchLink != null -> stringResource(R.string.uses_standing_link)
            else -> stringResource(R.string.no_link_yet)
        }
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Dot(if (s.hasLink) Palette.moss else Palette.saffron)
            Text(status, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        }
        if (open) {
            Plan(vm, s)
            OutlinedTextField(
                link, { link = it }, label = { Text(stringResource(R.string.meet_link)) },
                placeholder = { Text("meet.google.com/abc-defg-hij") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
            vm.error?.takeIf { it == "bad_meet_link" }?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error) }
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

/** The class's curriculum, one tap to change, and its sequence. */
@Composable
private fun Plan(vm: AppViewModel, s: ClassSession) {
    val curricula = vm.curricula ?: return
    Label(stringResource(R.string.curriculum))
    val keys = curricula.curricula.map { it.key }
    Choices(curricula.curricula.map { it.name }, keys.indexOf(s.curriculum).takeIf { it >= 0 }, enabled = !vm.busy, perRow = 2) { i ->
        if (s.curriculum != keys[i]) vm.setCurriculum(s.id, keys[i])
    }
    curricula.find(s.curriculum)?.let { plan ->
        Text(plan.about, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        Sequence(plan, curricula, vm.prefs.lang, collapsed = 3)
    }
    HorizontalDivider(color = Palette.line)
}

@Composable
private fun GroupCard(vm: AppViewModel) {
    val home = vm.teacherHome ?: return
    val settings = home.settings
    val context = LocalContext.current
    val links = remember { mutableStateMapOf<String, String>().apply { home.batches.forEach { put(it.info.key, it.meetLink ?: "") } } }
    var group by rememberSaveable { mutableStateOf(settings.groupLink ?: "") }
    val saved = stringResource(R.string.saved)
    Label(stringResource(R.string.settings_title))
    SectionCard {
        Text(stringResource(R.string.standing_link), style = MaterialTheme.typography.titleSmall)
        Text(stringResource(R.string.standing_link_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        home.batches.forEach { b ->
            OutlinedTextField(
                links[b.info.key].orEmpty(), { links[b.info.key] = it }, label = { Text(b.info.name + (b.info.time?.let { " · $it" } ?: "")) },
                placeholder = { Text("meet.google.com/abc-defg-hij") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
        }
        OutlinedTextField(
            group, { group = it }, label = { Text(stringResource(R.string.group_link)) },
            placeholder = { Text("chat.whatsapp.com/…") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
        )
        vm.error?.takeIf { it == "bad_group_link" || it == "bad_meet_link" }?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error) }
        Button(onClick = { vm.saveSettings(group, links.toMap(), saved) }, enabled = !vm.busy) { Text(stringResource(R.string.save)) }
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
    // (name, new password). Saveable: the server has already changed the password, so it must survive rotation.
    var shownPassword by rememberSaveable { mutableStateOf<Pair<String, String>?>(null) }
    var askingPassword by rememberSaveable { mutableStateOf<Int?>(null) } // a new password signs the student out everywhere: ask first
    var openStudent by rememberSaveable { mutableStateOf<Int?>(null) }
    var openItem by rememberSaveable { mutableStateOf<String?>(null) }
    vm.students.firstOrNull { it.user.id == openStudent }?.let { student ->
        val item = openItem
        if (item != null) {
            BackHandler { openItem = null }
            ItemHistoryScreen(vm, item, student) { openItem = null }
        } else {
            BackHandler { openStudent = null }
            StudentPractice(vm, student, back = { openStudent = null }) { openItem = it }
        }
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.students_title), style = MaterialTheme.typography.headlineSmall)
        if (vm.sharedNotes.isNotEmpty()) { // what students chose to share from their companion, one note at a time
            Label(stringResource(R.string.shared_title))
            Text(stringResource(R.string.shared_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
            vm.sharedNotes.forEach { n ->
                SectionCard(tint = Palette.cream) {
                    Text("“${n.text}”", style = MaterialTheme.typography.bodyLarge)
                    Text("${n.student} · ${dayLabel(n.sharedAt)}", style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                }
            }
            Spacer(Modifier.height(4.dp))
            Label(stringResource(R.string.students_title))
        }
        if (vm.students.isEmpty()) {
            if (vm.busy || vm.error != null) Waiting(vm, { vm.loadStudents() }, Modifier.fillMaxWidth()) else Text(stringResource(R.string.no_students), color = Palette.muted)
        }
        vm.students.forEach { (student, joined, intake) ->
            var placing by rememberSaveable(student.id) { mutableStateOf(false) }
            val batch = vm.teacherHome?.batch(student.batch)
            SectionCard(tint = if (student.status == "pending") Palette.saffronLight else Palette.paper) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(student.name, style = MaterialTheme.typography.titleMedium)
                        Text("${student.phone} · ${pluralStringResource(R.plurals.joined_count, joined, joined)}", style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                        if (batch != null && student.batchSince != null) {
                            Text(stringResource(R.string.batch_since, batch.info.name, dayLabel(student.batchSince)), style = MaterialTheme.typography.bodyMedium,
                                color = Palette.moss)
                        }
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
                IntakeSummary(vm, intake, placed = student.batch != null)
                if (student.batch == null) {
                    Label(stringResource(R.string.place_in_batch))
                    BatchPicker(vm, student, preselect = intake?.suggestedBatch ?: "beginner", action = R.string.approve_into)
                } else if (placing) {
                    BatchPicker(vm, student, preselect = student.batch, action = R.string.move_to) { placing = false }
                }
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (student.status == "approved" && !placing) OutlinedButton(onClick = { placing = true }) { Text(stringResource(R.string.move_batch)) }
                    if (student.status == "rejected" && student.batch != null) {
                        Button(onClick = { vm.setStudentStatus(student.id, "approved") }) { Text(stringResource(R.string.take_back)) }
                    }
                    if (student.status != "rejected") OutlinedButton(onClick = { vm.setStudentStatus(student.id, "rejected") }) { Text(stringResource(R.string.remove)) }
                    TextButton(onClick = { askingPassword = student.id }) { Text(stringResource(R.string.new_password)) }
                }
                if (student.status == "approved") {
                    TextButton(onClick = { openStudent = student.id }) { Text(stringResource(R.string.each_item) + " ›") }
                }
            }
        }
    }
    vm.students.firstOrNull { it.user.id == askingPassword }?.let { student ->
        val name = student.user.name
        AlertDialog(
            onDismissRequest = { askingPassword = null },
            title = { Text(stringResource(R.string.new_password_ask, name)) },
            text = { Text(stringResource(R.string.new_password_why, name.substringBefore(' '))) },
            confirmButton = {
                TextButton(onClick = { askingPassword = null; vm.resetPassword(student.user.id) { shownPassword = name to it } }) {
                    Text(stringResource(R.string.new_password))
                }
            },
            dismissButton = { TextButton(onClick = { askingPassword = null }) { Text(stringResource(R.string.cancel)) } },
        )
    }
    shownPassword?.let { (name, password) ->
        AlertDialog(
            onDismissRequest = { shownPassword = null },
            confirmButton = { TextButton(onClick = { shownPassword = null }) { Text(stringResource(R.string.ok)) } },
            text = { Text(stringResource(R.string.new_password_is, name, password), style = MaterialTheme.typography.titleMedium) },
        )
    }
}

/** A student's answers about themselves, for the teacher: a summary line, pain, the batch they point to while the
 *  student waits to be [placed], and the rest ("See all"): meals, the pain note, each self-assessment asana. */
@Composable
private fun IntakeSummary(vm: AppViewModel, intake: Intake?, placed: Boolean) {
    if (intake == null) return Text(stringResource(R.string.intake_none), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
    var all by rememberSaveable(intake) { mutableStateOf(false) }
    val food = FOODS.firstOrNull { it.first == intake.food }?.let { stringResource(it.second) } ?: intake.food
    Text(stringResource(R.string.intake_line, intake.age, intake.heightCm, intake.weightKg, food), style = MaterialTheme.typography.bodyMedium)
    if (intake.pain.isNotEmpty()) {
        val areas = intake.pain.map { area -> PAIN_AREAS.firstOrNull { it.first == area }?.let { stringResource(it.second) } ?: area }
        Text(stringResource(R.string.intake_pain, areas.joinToString(", ")), style = MaterialTheme.typography.bodyMedium, color = Palette.danger)
    }
    if (!placed) vm.teacherHome?.batch(intake.suggestedBatch)?.let {
        Text(stringResource(R.string.intake_suggests, it.info.name), style = MaterialTheme.typography.labelLarge, color = Palette.moss)
    }
    TextButton(onClick = { all = !all }) { Text(stringResource(if (all) R.string.show_less else R.string.see_all)) }
    if (all) {
        intake.meals?.let { Text(stringResource(R.string.intake_meals, it), style = MaterialTheme.typography.bodyMedium) }
        intake.painNote?.let { Text("“$it”", style = MaterialTheme.typography.bodyMedium) }
        intake.ratings.forEach { r ->
            val title = vm.curricula?.library?.get(r.item)?.title(vm.prefs.lang) ?: r.item
            val said = listOfNotNull(r.reaction?.let { stringResource(REACTIONS[it - 1]) }, stringResource(R.string.pain_flag).takeIf { r.pain })
            Text("$title: ${said.joinToString(" · ")}", style = MaterialTheme.typography.bodyMedium, color = if (r.pain) Palette.danger else Palette.ink)
        }
    }
}

/** Choosing a student's batch, with a note for the review history: the batches two to a row, the note, and [action]
 *  ("Approve into …", "Move to …"), named with the batch chosen. */
@Composable
private fun BatchPicker(vm: AppViewModel, student: User, preselect: String?, action: Int, done: () -> Unit = {}) {
    val batches = vm.teacherHome?.batches ?: return
    var chosen by rememberSaveable(student.id) { mutableStateOf(preselect) }
    var note by rememberSaveable(student.id) { mutableStateOf("") }
    Choices(batches.map { it.info.name }, batches.indexOfFirst { it.info.key == chosen }.takeIf { it >= 0 }, perRow = 2) { chosen = batches[it].info.key }
    OutlinedTextField(note, { note = it }, placeholder = { Text(stringResource(R.string.batch_note)) }, minLines = 2, maxLines = 3,
        modifier = Modifier.fillMaxWidth())
    val name = batches.firstOrNull { it.info.key == chosen }?.info?.name
    Button(onClick = { chosen?.let { vm.placeStudent(student.id, it, note); done() } }, enabled = name != null && !vm.busy, modifier = Modifier.fillMaxWidth()) {
        Text(stringResource(action, name.orEmpty()))
    }
}

/** One student's practice per item, for the teacher; each item opens its history and the box for feedback on it. */
@Composable
private fun StudentPractice(vm: AppViewModel, student: Student, back: () -> Unit, open: (String) -> Unit) {
    LaunchedEffect(student.user.id) { vm.loadItems(student.user.id) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BackHeader(student.user.name, back)
        Text("${student.user.phone} · ${pluralStringResource(R.plurals.joined_count, student.joined, student.joined)}", color = Palette.muted)
        Label(stringResource(R.string.each_item))
        ItemList(vm, vm.items, teacherViewing = true, reload = { vm.loadItems(student.user.id) }, open = open)
    }
}

@Composable
fun InsightsScreen(vm: AppViewModel) {
    LaunchedEffect(Unit) { vm.loadInsights() }
    val data = vm.insights
    var reviewing by rememberSaveable { mutableStateOf<Int?>(null) }
    data?.sessions?.firstOrNull { it.id == reviewing }?.let { session ->
        BackHandler { reviewing = null }
        ClassReviewScreen(vm, session) { reviewing = null }
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
        Text(stringResource(R.string.insights_title), style = MaterialTheme.typography.headlineSmall)
        if (data == null) {
            Waiting(vm, { vm.loadInsights() }, Modifier.fillMaxWidth())
            return@Column
        }
        StatTiles(
            data.approved.toString() to stringResource(R.string.students_title),
            (data.moodChange?.let { String.format(Locale.US, "%+.1f", it) } ?: "–") to stringResource(R.string.avg_lift),
            vm.sharedCount.toString() to stringResource(R.string.notes_shared),
        )
        if (data.moodPairs > 0) Text(pluralStringResource(R.plurals.pairs, data.moodPairs, data.moodPairs), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)

        Label(stringResource(R.string.last_two_weeks))
        val withCheckins = data.sessions.filter { it.joined > 0 }
        if (withCheckins.isEmpty()) Text(stringResource(R.string.no_data), color = Palette.muted)
        withCheckins.forEach { s ->
            SectionCard(Modifier.clickable { reviewing = s.id }) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(s.className, style = MaterialTheme.typography.titleMedium)
                        Text("${dayLabel(s.startsAt)} · ${timeLabel(s.startsAt)}", style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                    }
                    Pill(pluralStringResource(R.plurals.joined_count, s.joined, s.joined))
                }
                MoodRow(stringResource(R.string.before), s.moodBefore, Palette.moss)
                MoodRow(stringResource(R.string.after), s.moodAfter, Palette.saffron)
                Text(stringResource(R.string.review_open), style = MaterialTheme.typography.labelLarge, color = Palette.moss)
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
        FitText(label, Modifier.width(72.dp), MaterialTheme.typography.bodyMedium, Palette.muted)
        Bar(((mood ?: 0.0) / 5.0).toFloat(), color, Modifier.weight(1f))
        FitText(mood?.let { MOODS[(it.roundToInt() - 1).coerceIn(0, 4)] + String.format(Locale.US, " %.1f", it) } ?: "–", Modifier.width(64.dp))
    }
}
