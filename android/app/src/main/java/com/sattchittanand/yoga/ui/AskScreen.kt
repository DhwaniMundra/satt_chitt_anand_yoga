package com.sattchittanand.yoga.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.LinearProgressIndicator
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
import com.sattchittanand.yoga.companion.GemmaState
import com.sattchittanand.yoga.companion.Problem
import com.sattchittanand.yoga.companion.Waiting
import java.util.Locale

/** What a reply says it did, for each of the companion's tools. */
private val TOOL_LABELS = mapOf(
    "get_my_practice" to R.string.tool_practice,
    "get_upcoming_classes" to R.string.tool_schedule,
    "search_studio_notes" to R.string.tool_notes,
    "save_my_note" to R.string.tool_saved,
    "get_my_notes" to R.string.tool_memory,
)

private fun gb(bytes: Long) = String.format(Locale.US, "%.1f GB", bytes / 1e9)

/** The chat with the practice companion: Gemma on this phone, once downloaded. A phone with too little memory for
 *  Gemma is told so. */
@Composable
fun AskScreen(vm: AppViewModel) {
    val gemma by vm.gemma.state.collectAsState()
    LaunchedEffect(Unit) { vm.gemma.refresh() }
    Column(Modifier.fillMaxSize()) {
        when (val state = gemma) {
            is GemmaState.TooLittleMemory -> Column(Modifier.padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text(stringResource(R.string.ask_title), style = MaterialTheme.typography.headlineSmall)
                SectionCard(tint = Palette.saffronLight) {
                    Text(stringResource(R.string.chat_needs_memory), style = MaterialTheme.typography.titleMedium)
                    Text(stringResource(R.string.gemma_too_little_memory, gb(state.totalBytes)), style = MaterialTheme.typography.bodyMedium)
                }
            }
            else -> Chat(vm, state)
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ColumnScope.Chat(vm: AppViewModel, gemma: GemmaState) {
    var question by rememberSaveable { mutableStateOf("") }
    val list = rememberLazyListState()
    val open = vm.user?.let { it.isTeacher || it.isApproved } ?: false
    val ready = gemma == GemmaState.Ready
    var scrolled by remember { mutableStateOf(false) }
    // The newest message at the top of the view: a long reply is read from its start. No animation on opening.
    LaunchedEffect(vm.chat.size, vm.asking) {
        if (vm.chat.isEmpty()) return@LaunchedEffect
        if (scrolled) list.animateScrollToItem(vm.chat.size) else list.scrollToItem(vm.chat.size)
        scrolled = true
    }

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
                    Text(stringResource(R.string.ask_disclaimer), Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
                }
                GemmaCard(gemma, vm)
                if (open && ready && vm.chat.isEmpty()) {
                    val suggestions = listOf(R.string.sugg_1, R.string.sugg_2, R.string.sugg_3, R.string.sugg_4).map { stringResource(it) }
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        suggestions.forEach { s -> SuggestionChip(onClick = { vm.ask(s) }, label = { Text(s) }) }
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
    if (ready) {
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                question, { question = it }, placeholder = { Text(stringResource(R.string.ask_hint)) },
                modifier = Modifier.weight(1f), enabled = open, maxLines = 4, shape = RoundedCornerShape(24.dp),
            )
            FilledIconButton(
                onClick = { vm.ask(question); question = "" },
                enabled = open && question.isNotBlank() && !vm.asking,
                modifier = Modifier.size(52.dp),
            ) { Icon(Icons.AutoMirrored.Filled.Send, stringResource(R.string.ask_send)) }
        }
    }
}

/** Where Gemma on this phone stands: the offer to download it, the download, the check, the start, or what went
 *  wrong. Nothing once Gemma is ready. */
@Composable
private fun GemmaCard(state: GemmaState, vm: AppViewModel) {
    val gemma = vm.gemma
    when (state) {
        is GemmaState.Ready, is GemmaState.TooLittleMemory -> Unit
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
            if (state.problem != Problem.START) OutlinedButton(onClick = { gemma.download() }) { Text(stringResource(R.string.try_again)) }
        }
        GemmaState.NotDownloaded -> SectionCard {
            Text(stringResource(R.string.gemma_title), style = MaterialTheme.typography.titleMedium)
            Text(stringResource(R.string.gemma_offer), style = MaterialTheme.typography.bodyMedium)
            Button(onClick = { gemma.download() }) { Text(stringResource(R.string.gemma_download)) }
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
                if (state.waiting == Waiting.WIFI) OutlinedButton(onClick = gemma::useMobileData) { Text(stringResource(R.string.gemma_use_mobile)) }
                TextButton(onClick = gemma::cancel) { Text(stringResource(R.string.cancel)) }
            }
        }
        is GemmaState.Checking -> SectionCard {
            Text(stringResource(R.string.gemma_checking), style = MaterialTheme.typography.titleSmall)
            LinearProgressIndicator(progress = { (state.done.toFloat() / state.total).coerceIn(0f, 1f) }, Modifier.fillMaxWidth(), color = Palette.moss)
        }
        GemmaState.Loading -> SectionCard {
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp), verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                Text(stringResource(R.string.gemma_loading), style = MaterialTheme.typography.bodyMedium)
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChatBubble(line: ChatLine) {
    val tools = line.tools.mapNotNull { TOOL_LABELS[it] }
    Row(Modifier.fillMaxWidth(), horizontalArrangement = if (line.fromStudent) Arrangement.End else Arrangement.Start) {
        Surface(
            color = if (line.fromStudent) Palette.moss else Palette.paper,
            border = if (line.fromStudent) null else BorderStroke(if (line.urgent) 2.dp else 1.dp, if (line.urgent) Palette.danger else Palette.line),
            shape = RoundedCornerShape(18.dp),
            modifier = Modifier.widthIn(max = 320.dp),
        ) {
            Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                if (line.urgent) Text(stringResource(R.string.urgent_label), color = Palette.danger, style = MaterialTheme.typography.titleMedium)
                Text(
                    if (line.fromStudent) AnnotatedString(line.text) else simpleMarkdown(line.text),
                    color = if (line.fromStudent) Color.White else Palette.ink,
                    style = MaterialTheme.typography.bodyLarge,
                )
                if (tools.isNotEmpty()) {
                    FlowRow(Modifier.padding(top = 4.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        tools.forEach { Pill(stringResource(it), Palette.cream, Palette.muted) }
                    }
                }
            }
        }
    }
}

/** Gemma writes light Markdown: "**bold**", "* " or "- " bullets, and a bullet's long text wrapped onto indented
 *  lines. Shown as bold text and "•", with the wrapped lines joined up again. */
private fun simpleMarkdown(text: String): AnnotatedString = buildAnnotatedString {
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
