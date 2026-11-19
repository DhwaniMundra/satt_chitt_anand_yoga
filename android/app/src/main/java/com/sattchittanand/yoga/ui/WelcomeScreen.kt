package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.SelfImprovement
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.BuildConfig
import com.sattchittanand.yoga.R

/** The server address, folded away under a small link: a debug build can be pointed at a laptop on the Wi-Fi. */
@Composable
private fun ServerAddress(vm: AppViewModel) {
    var open by rememberSaveable { mutableStateOf(false) }
    var address by rememberSaveable { mutableStateOf(vm.prefs.server) }
    TextButton(onClick = { open = !open }) {
        Text("${stringResource(R.string.server)}: ${vm.prefs.server}", style = MaterialTheme.typography.labelMedium, color = Palette.muted)
    }
    if (open) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                address, { address = it }, singleLine = true, modifier = Modifier.weight(1f),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
            )
            OutlinedButton(onClick = { vm.saveServer(address); open = false }) { Text(stringResource(R.string.save)) }
        }
    }
}

val LANGUAGES = listOf("en" to "English", "hi" to "हिन्दी", "mr" to "मराठी")

@Composable
fun LanguageChips(current: String, onPick: (String) -> Unit) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        LANGUAGES.forEach { (code, name) ->
            FilterChip(selected = current == code, onClick = { if (current != code) onPick(code) }, label = { Text(name) })
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun WelcomeScreen(vm: AppViewModel, onLanguage: (String) -> Unit) {
    var role by rememberSaveable { mutableStateOf<String?>(null) } // null until "student" or "teacher" is picked
    var signup by rememberSaveable { mutableStateOf(true) }
    var name by rememberSaveable { mutableStateOf("") }
    var phone by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var code by rememberSaveable { mutableStateOf("") }

    Column(
        Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Spacer(Modifier.height(if (role == null) 48.dp else 8.dp))
        BrandHeader(large = role == null)
        Text(stringResource(R.string.welcome_sub), style = MaterialTheme.typography.bodyLarge, color = Palette.muted, textAlign = TextAlign.Center)
        Spacer(Modifier.height(4.dp))
        LanguageChips(vm.prefs.lang, onLanguage)
        Spacer(Modifier.height(12.dp))

        vm.error?.takeIf { role == null }?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center) }
        val chosen = role
        if (chosen == null) {
            Button(onClick = { role = "student" }, modifier = Modifier.fillMaxWidth().height(60.dp)) {
                Icon(Icons.Filled.SelfImprovement, null)
                Spacer(Modifier.padding(4.dp))
                Text(stringResource(R.string.i_am_student))
            }
            OutlinedButton(onClick = { role = "teacher"; signup = false }, modifier = Modifier.fillMaxWidth().height(60.dp)) {
                Icon(Icons.Filled.Person, null)
                Spacer(Modifier.padding(4.dp))
                Text(stringResource(R.string.i_am_teacher))
            }
            if (BuildConfig.DEBUG) ServerAddress(vm)
            return@Column
        }

        val teacher = chosen == "teacher"
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TextButton(onClick = { role = null; vm.error = null }) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, null)
                Text(stringResource(R.string.back))
            }
            Spacer(Modifier.weight(1f))
            Text(stringResource(if (teacher) R.string.i_am_teacher else R.string.i_am_student), style = MaterialTheme.typography.titleMedium, color = Palette.moss)
        }
        // Both choices sit above the form, so a returning student never has to scroll to find "Log in".
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(true to R.string.signup, false to R.string.login).forEachIndexed { i, (isSignup, label) ->
                SegmentedButton(
                    selected = signup == isSignup,
                    onClick = { signup = isSignup; vm.error = null },
                    shape = SegmentedButtonDefaults.itemShape(i, 2),
                ) { Text(stringResource(label)) }
            }
        }
        if (signup) {
            OutlinedTextField(name, { name = it }, label = { Text(stringResource(R.string.name)) }, singleLine = true, modifier = Modifier.fillMaxWidth())
        }
        OutlinedTextField(
            phone, { phone = it }, label = { Text(stringResource(R.string.phone)) }, singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone), modifier = Modifier.fillMaxWidth(),
        )
        OutlinedTextField(
            password, { password = it }, label = { Text(stringResource(R.string.password)) }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password),
            modifier = Modifier.fillMaxWidth(),
        )
        if (signup) {
            OutlinedTextField(
                code, { code = it.uppercase() },
                label = { Text(stringResource(if (teacher) R.string.teacher_code else R.string.group_code)) },
                supportingText = if (teacher) null else ({ Text(stringResource(R.string.group_code_help)) }),
                singleLine = true, modifier = Modifier.fillMaxWidth(),
            )
        }
        vm.error?.let { Text(errorText(it), color = MaterialTheme.colorScheme.error, modifier = Modifier.fillMaxWidth()) }
        Button(
            onClick = { if (signup) vm.signup(name, phone, password, teacher, code) else vm.login(phone, password) },
            enabled = !vm.busy && phone.isNotBlank() && password.isNotBlank() && (!signup || name.isNotBlank()),
            modifier = Modifier.fillMaxWidth().height(56.dp),
        ) { Text(stringResource(if (signup) R.string.signup else R.string.login)) }
    }
}
