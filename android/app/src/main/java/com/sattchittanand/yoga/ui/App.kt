package com.sattchittanand.yoga.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.Row
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SelfImprovement
import androidx.compose.material.icons.filled.WbSunny
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.R
import kotlinx.coroutines.delay
import java.time.Instant
import java.time.ZoneId

private data class Tab(val key: String, val label: Int, val icon: ImageVector)

private val STUDENT_TABS = listOf(
    Tab("today", R.string.tab_today, Icons.Filled.WbSunny),
    Tab("practice", R.string.tab_practice, Icons.Filled.SelfImprovement),
    Tab("ask", R.string.tab_ask, Icons.Filled.ChatBubble),
    Tab("me", R.string.tab_me, Icons.Filled.Person),
)
private val TEACHER_TABS = listOf(
    Tab("today", R.string.tab_today, Icons.Filled.WbSunny),
    Tab("students", R.string.tab_students, Icons.Filled.Groups),
    Tab("insights", R.string.tab_insights, Icons.Filled.Insights),
)

@Composable
fun App(vm: AppViewModel, onLanguage: (String) -> Unit) {
    val user = vm.user
    CompositionLocalProvider(LocalTeacher provides vm.words().teacher) {
        when {
            // Never the sign-up form for someone signed in: until their first screen has come, a spinner, and only once a
            // call has failed, why.
            user == null && vm.signedIn -> if (vm.busy || vm.error == null) Connecting(vm.signingIn) else Unreachable(vm)
            user == null -> WelcomeScreen(vm, onLanguage)
            user.status == "rejected" -> Closed(vm)
            else -> Main(vm, user.isTeacher, onLanguage)
        }
    }
}

@Composable
private fun Main(vm: AppViewModel, teacher: Boolean, onLanguage: (String) -> Unit) {
    val tabs = if (teacher) TEACHER_TABS else STUDENT_TABS
    var tab by rememberSaveable(teacher) { mutableStateOf(tabs.first().key) }
    var again by rememberSaveable { mutableIntStateOf(0) } // a tab tapped again goes back to its first screen
    val snackbar = remember { SnackbarHostState() }
    val error = vm.error?.let { errorText(it) }

    LaunchedEffect(vm.notice) { vm.notice?.let { snackbar.showSnackbar(it); vm.notice = null } }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    LaunchedEffect(Unit) { // what this phone has yet to send, every two minutes while the app is in front
        lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            while (true) {
                delay(2 * 60_000)
                vm.sendWaiting()
            }
        }
    }
    LaunchedEffect(vm.error, tab) { if (error != null && vm.error !in FORM_ERRORS) snackbar.showSnackbar(error) }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            NavigationBar(containerColor = Palette.paper) {
                tabs.forEach { t ->
                    NavigationBarItem(
                        selected = tab == t.key,
                        onClick = { if (tab == t.key) again++ else tab = t.key; vm.error = null },
                        icon = { Icon(t.icon, null) },
                        label = { FitText(stringResource(t.label)) },
                        colors = NavigationBarItemDefaults.colors(indicatorColor = Palette.mossLight, selectedIconColor = Palette.moss),
                    )
                }
            }
        },
    ) { padding ->
        // The screen ends above the keyboard while it is open (edge to edge, adjustResize alone does not do it), so
        // the Ask box and the other text fields stay in sight as the student types.
        Box(Modifier.padding(padding).consumeWindowInsets(padding).imePadding()) {
            Column {
                vm.shownFrom?.let { ShownFrom(it, vm::refresh) }
                Box(Modifier.weight(1f)) {
                    key(tab, again) {
                        when (tab) {
                            "today" -> if (teacher) TeacherTodayScreen(vm, onLanguage) { tab = "students" } else TodayScreen(vm)
                            "practice" -> PracticeScreen(vm)
                            "ask" -> AskScreen(vm)
                            "me" -> MeScreen(vm, onLanguage)
                            "students" -> StudentsScreen(vm)
                            "insights" -> InsightsScreen(vm)
                        }
                    }
                }
            }
            // A call to the server takes a second or more, and the screens are read again behind what they show: a thin
            // line over the top says so and moves nothing. A pull of the Today tab shows its own spinner instead.
            if (vm.busy || vm.refreshing && !vm.pulling) {
                val updating = stringResource(R.string.updating)
                LinearProgressIndicator(Modifier.fillMaxWidth().align(Alignment.TopCenter).semantics { contentDescription = updating }, color = Palette.moss)
            }
        }
    }
}

/** The screens show what was read at [at] (epoch ms), as the studio could not be reached since: one calm line, on the
 *  phone's own clock ("at 7:42 AM", or with its day when not today), and Try again. */
@Composable
private fun ShownFrom(at: Long, retry: () -> Unit) {
    val moment = Instant.ofEpochMilli(at)
    val time = dateFormat("h:mm a").format(moment.atZone(ZoneId.systemDefault()))
    val sameDay = daysFromToday(moment, Instant.now(), ZoneId.systemDefault()) == 0L
    Row(Modifier.fillMaxWidth().background(Palette.saffronLight).padding(start = 16.dp, end = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(stringResource(R.string.shown_from, if (sameDay) time else "${dayLabel(moment)} $time"), Modifier.weight(1f).padding(vertical = 8.dp),
            style = MaterialTheme.typography.bodyMedium, color = Palette.ink)
        TextButton(onClick = retry) { Text(stringResource(R.string.try_again)) }
    }
}

/** Signed in, and the first screen on its way: at start ("Connecting to the studio…"), or after logging in or signing
 *  up ([signingIn]: "Signing in…"). */
@Composable
private fun Connecting(signingIn: Boolean) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        BrandHeader(large = true)
        Spacer(Modifier.height(32.dp))
        CircularProgressIndicator(color = Palette.moss)
        Spacer(Modifier.height(16.dp))
        Text(stringResource(if (signingIn) R.string.signing_in else R.string.connecting), style = MaterialTheme.typography.bodyLarge, color = Palette.muted)
    }
}

/** Signed in, but the first screen could not be read: why, and try again, here or on coming back to the app. */
@Composable
private fun Unreachable(vm: AppViewModel) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        BrandHeader(large = true)
        Spacer(Modifier.height(24.dp))
        Text(stringResource(R.string.unreachable), style = MaterialTheme.typography.titleLarge)
        val why = vm.error?.takeIf { it != "network" }?.let { errorText(it) } // the server answered, but not with the screen
        Text(why ?: stringResource(R.string.unreachable_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted,
            textAlign = TextAlign.Center)
        Spacer(Modifier.height(16.dp))
        Button(onClick = vm::refresh, enabled = !vm.busy) { Text(stringResource(R.string.try_again)) }
    }
}

/** A student the teacher removed: one plain line, and Log out. */
@Composable
private fun Closed(vm: AppViewModel) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        BrandHeader(large = true)
        Spacer(Modifier.height(24.dp))
        Text(stringResource(R.string.closed_account, LocalTeacher.current), style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(16.dp))
        OutlinedButton(onClick = vm::logout) { Text(stringResource(R.string.logout)) }
    }
}

