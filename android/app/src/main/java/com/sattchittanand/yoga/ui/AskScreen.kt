package com.sattchittanand.yoga.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.PhoneAndroid
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ChatLine
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.companion.GemmaFile
import com.sattchittanand.yoga.companion.GemmaState
import com.sattchittanand.yoga.companion.Problem
import com.sattchittanand.yoga.companion.Waiting
import java.util.Locale

/** What a reply says it did, for each tool the companion used. */
private val TOOL_LABELS = mapOf(
    "practice" to R.string.tool_practice,
    "schedule" to R.string.tool_schedule,
    "notes" to R.string.tool_notes,
    "saved" to R.string.tool_saved,
    "memory" to R.string.tool_memory,
)

/** The chat with the practice companion, answered on this phone: by Gemma once downloaded, before that (or on a phone
 *  with too little memory) from the studio's notes. The conversation is kept on the phone. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AskScreen(vm: AppViewModel) {
    var question by rememberSaveable { mutableStateOf("") }
    val list = rememberLazyListState()
    val open = vm.user?.let { it.isTeacher || it.isApproved } ?: false
    var scrolled by remember { mutableStateOf(false) }
    val gemma by vm.gemma.state.collectAsState()
    LaunchedEffect(Unit) { vm.openAsk() }
    // The newest message at the top of the view: a long reply is read from its start. No animation on opening.
    LaunchedEffect(vm.chat.size, vm.asking) {
        if (vm.chat.isEmpty()) return@LaunchedEffect
        if (scrolled) list.animateScrollToItem(vm.chat.size) else list.scrollToItem(vm.chat.size)
        scrolled = true
    }
    val send = { text: String -> vm.ask(text) }

    Column(Modifier.fillMaxSize()) {
        // The title stays put above the conversation, so Clear is always at hand.
        Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 8.dp, top = 12.dp)) {
            Text(stringResource(R.string.ask_title), Modifier.weight(1f).padding(vertical = 8.dp).alignByBaseline(), style = MaterialTheme.typography.headlineSmall)
            if (vm.chat.isNotEmpty()) {
                TextButton(onClick = vm::clearChat, enabled = !vm.asking, modifier = Modifier.alignByBaseline()) { Text(stringResource(R.string.chat_clear)) }
            }
        }
        HorizontalDivider(color = if (list.canScrollBackward) Palette.line else Color.Transparent)
        LazyColumn(
            state = list,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 8.dp, bottom = 20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Surface(color = Palette.saffronLight, shape = MaterialTheme.shapes.small) {
                        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Filled.PhoneAndroid, null, Modifier.size(18.dp), tint = Palette.moss)
                                Text(stringResource(R.string.ask_privacy), style = MaterialTheme.typography.titleSmall, color = Palette.moss)
                            }
                            // "Knows your classes…" only once Gemma can look them up
                            Text(stringResource(if (gemma is GemmaState.Ready) R.string.ask_disclaimer else R.string.ask_disclaimer_notes),
                                style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                    if (open) GemmaCard(gemma, vm)
                    if (open && vm.chat.isEmpty()) {
                        // About the student's own practice and the schedule only once Gemma can look them up: the notes alone
                        // answered "How was my practice this week?" with the notes for beginners.
                        val ids = if (gemma is GemmaState.Ready) listOf(R.string.sugg_1, R.string.sugg_2, R.string.sugg_3, R.string.sugg_4)
                        else listOf(R.string.sugg_2, R.string.sugg_4)
                        val suggestions = ids.map { stringResource(it) }
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            suggestions.forEach { s -> SuggestionChip(onClick = { send(s) }, label = { Text(s) }) }
                        }
                    }
                }
            }
            items(vm.chat) { line -> ChatBubble(line) }
            if (vm.asking) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Text(stringResource(R.string.ask_thinking_phone), color = Palette.muted)
                    }
                }
            }
        }
        if (!open) { // next to the box it explains, whatever the conversation above
            Surface(color = Palette.mossLight, shape = MaterialTheme.shapes.small, modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp)) {
                Text(stringResource(R.string.err_pending), Modifier.padding(12.dp), style = MaterialTheme.typography.bodyLarge)
            }
        }
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                question, { question = it }, placeholder = { Text(stringResource(R.string.ask_hint)) },
                modifier = Modifier.weight(1f), enabled = open, maxLines = 4, shape = RoundedCornerShape(24.dp),
            )
            FilledIconButton(
                onClick = { send(question); question = "" },
                enabled = open && question.isNotBlank() && !vm.asking,
                modifier = Modifier.size(52.dp),
            ) { Icon(Icons.AutoMirrored.Filled.Send, stringResource(R.string.ask_send)) }
        }
    }
}

/** Where Gemma on this phone stands: the offer to download it, the download, the check, the start, or why answers
 *  come from the notes. Nothing once Gemma is ready. */
@Composable
private fun GemmaCard(state: GemmaState, vm: AppViewModel) {
    val gb = { bytes: Long -> String.format(Locale.US, "%.1f GB", bytes / 1e9) }
    when (state) {
        is GemmaState.Ready -> Unit
        is GemmaState.TooLittleMemory -> QuietLine(stringResource(R.string.gemma_too_little_memory, gb(state.totalBytes)))
        is GemmaState.Failed -> SectionCard {
            Text(stringResource(R.string.gemma_title), style = MaterialTheme.typography.titleMedium)
            Text(
                stringResource(
                    when (state.problem) {
                        Problem.NO_SPACE -> R.string.gemma_no_space
                        Problem.WRONG_FILE -> R.string.gemma_wrong_file
                        Problem.DOWNLOAD -> R.string.gemma_download_failed
                        Problem.START -> R.string.gemma_start_failed
                    },
                ),
                style = MaterialTheme.typography.bodyMedium,
            )
            if (state.problem != Problem.START) OutlinedButton(onClick = vm::downloadGemma) { Text(stringResource(R.string.try_again)) }
        }
        GemmaState.NotDownloaded -> SectionCard {
            Text(stringResource(R.string.gemma_title), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.gemma_offer), style = MaterialTheme.typography.bodyMedium)
            Button(onClick = vm::downloadGemma) { Text(stringResource(R.string.gemma_download)) }
        }
        is GemmaState.Downloading -> SectionCard {
            Text(stringResource(R.string.gemma_downloading, gb(state.done), gb(state.total)), style = MaterialTheme.typography.titleSmall)
            LinearProgressIndicator(progress = { (state.done.toFloat() / state.total).coerceIn(0f, 1f) }, Modifier.fillMaxWidth(), color = Palette.moss)
            Text(
                stringResource(
                    when (state.waiting) {
                        Waiting.WIFI -> R.string.gemma_waiting_wifi
                        Waiting.NETWORK -> R.string.gemma_waiting_network
                        null -> R.string.gemma_keeps_going
                    },
                ),
                style = MaterialTheme.typography.bodyMedium, color = Palette.muted,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (state.waiting == Waiting.WIFI) OutlinedButton(onClick = vm::useMobileData) { Text(stringResource(R.string.gemma_use_mobile)) }
                TextButton(onClick = vm::cancelDownload) { Text(stringResource(R.string.cancel)) }
            }
        }
        is GemmaState.Checking -> SectionCard {
            Text(stringResource(R.string.gemma_checking), style = MaterialTheme.typography.titleSmall)
            LinearProgressIndicator(progress = { (state.done.toFloat() / GemmaFile.SIZE).coerceIn(0f, 1f) }, Modifier.fillMaxWidth(), color = Palette.moss)
        }
        GemmaState.Loading -> SectionCard {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                Text(stringResource(R.string.gemma_loading), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@Composable
private fun QuietLine(text: String) {
    Text(text, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChatBubble(line: ChatLine) {
    val urgent = line.mode == "urgent"
    val tools = line.tools.mapNotNull { TOOL_LABELS[it] }.distinct()
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (line.fromStudent) Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (line.fromStudent) Palette.moss else Palette.paper,
            border = if (line.fromStudent) null else BorderStroke(if (urgent) 2.dp else 1.dp, if (urgent) Palette.danger else Palette.line),
            shape = RoundedCornerShape(18.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (urgent) Text(stringResource(R.string.urgent_label), color = Palette.danger, style = MaterialTheme.typography.titleMedium)
                Text(
                    if (line.fromStudent) AnnotatedString(line.text) else simpleMarkdown(line.text),
                    color = if (line.fromStudent) Color.White else Palette.ink,
                    style = MaterialTheme.typography.bodyLarge,
                )
                if (tools.isNotEmpty() && !urgent) {
                    FlowRow(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        tools.forEach { Pill(stringResource(it), Palette.cream, Palette.muted) }
                    }
                }
            }
        }
    }
}

/** Gemma and the studio's notes write light Markdown: "**bold**", "* " or "- " bullets, and a bullet's long text
 *  wrapped onto indented lines. Shown as bold text and "•", with the wrapped lines joined up again. */
fun simpleMarkdown(text: String): AnnotatedString = buildAnnotatedString {
    val bullet = Regex("^\\s*[*-]\\s+")
    val lines = mutableListOf<String>()
    for (raw in text.lines()) {
        val wrapped = raw.isNotBlank() && raw[0].isWhitespace() && !bullet.containsMatchIn(raw) && lines.lastOrNull().orEmpty().isNotBlank()
        if (wrapped) lines[lines.lastIndex] += " " + raw.trim() else lines += raw.replace(bullet, "• ")
    }
    lines.forEachIndexed { i, line ->
        if (i > 0) append("\n")
        line.split("**").forEachIndexed { j, part ->
            if (j % 2 == 1) withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(part) } else append(part)
        }
    }
}
