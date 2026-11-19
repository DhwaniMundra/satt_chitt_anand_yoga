package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.consumeWindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.ChatBubble
import androidx.compose.material.icons.filled.Groups
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SelfImprovement
import androidx.compose.material.icons.filled.WbSunny
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.stringResource
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.R

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
            vm.starting -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { BrandHeader(large = true) }
            user == null -> WelcomeScreen(vm, onLanguage)
            else -> Main(vm, user.isTeacher, onLanguage)
        }
    }
}

@Composable
private fun Main(vm: AppViewModel, teacher: Boolean, onLanguage: (String) -> Unit) {
    val tabs = if (teacher) TEACHER_TABS else STUDENT_TABS
    var tab by rememberSaveable(teacher) { mutableStateOf(tabs.first().key) }
    val snackbar = remember { SnackbarHostState() }
    val error = vm.error?.let { errorText(it) }

    LaunchedEffect(vm.notice) { vm.notice?.let { snackbar.showSnackbar(it); vm.notice = null } }
    // Screens with their own form show errors inline; elsewhere a snackbar does.
    LaunchedEffect(error, tab) { if (error != null && tab != "today") snackbar.showSnackbar(error) }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbar) },
        bottomBar = {
            NavigationBar(containerColor = Palette.paper) {
                tabs.forEach { t ->
                    NavigationBarItem(
                        selected = tab == t.key,
                        onClick = { tab = t.key; vm.error = null },
                        icon = { Icon(t.icon, null) },
                        label = { Text(stringResource(t.label)) },
                        colors = NavigationBarItemDefaults.colors(indicatorColor = Palette.mossLight, selectedIconColor = Palette.moss),
                    )
                }
            }
        },
    ) { padding ->
        // The screen ends above the keyboard while it is open (edge to edge, adjustResize alone does not do it), so
        // the Ask box and the other text fields stay in sight as the student types.
        Box(Modifier.padding(padding).consumeWindowInsets(padding).imePadding()) {
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
