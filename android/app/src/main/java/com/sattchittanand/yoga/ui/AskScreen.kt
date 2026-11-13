package com.sattchittanand.yoga.ui

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SuggestionChip
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun AskScreen(vm: AppViewModel) {
    var question by rememberSaveable { mutableStateOf("") }
    val list = rememberLazyListState()
    LaunchedEffect(vm.chat.size, vm.asking) { if (vm.chat.isNotEmpty()) list.animateScrollToItem(vm.chat.size) }

    Column(Modifier.fillMaxSize()) {
        LazyColumn(
            state = list,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(20.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(stringResource(R.string.ask_title), style = MaterialTheme.typography.headlineSmall)
                    Surface(color = Palette.saffronLight, shape = MaterialTheme.shapes.small) {
                        Text(stringResource(R.string.ask_disclaimer), Modifier.padding(12.dp), style = MaterialTheme.typography.bodyMedium)
                    }
                    if (vm.chat.isEmpty()) {
                        val suggestions = listOf(R.string.sugg_1, R.string.sugg_2, R.string.sugg_3, R.string.sugg_4).map { stringResource(it) }
                        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            suggestions.forEach { s -> SuggestionChip(onClick = { vm.ask(s) }, label = { Text(s) }) }
                        }
                    }
                }
            }
            itemsIndexed(vm.chat) { _, line -> ChatBubble(line) }
            if (vm.asking) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                        Text(stringResource(R.string.ask_thinking), color = Palette.muted)
                    }
                }
            }
        }
        Row(Modifier.fillMaxWidth().padding(12.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(
                question, { question = it }, placeholder = { Text(stringResource(R.string.ask_hint)) },
                modifier = Modifier.weight(1f), maxLines = 4, shape = RoundedCornerShape(24.dp),
            )
            FilledIconButton(
                onClick = { vm.ask(question); question = "" },
                enabled = question.isNotBlank() && !vm.asking,
                modifier = Modifier.size(52.dp),
            ) { Icon(Icons.AutoMirrored.Filled.Send, stringResource(R.string.ask_send)) }
        }
    }
}

@Composable
private fun ChatBubble(line: ChatLine) {
    val urgent = line.mode == "urgent"
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
                if (line.sources.isNotEmpty() && !urgent) {
                    Text(stringResource(R.string.sources, line.sources.joinToString(", ")), style = MaterialTheme.typography.labelMedium, color = Palette.muted)
                }
            }
        }
    }
}

/** Gemma writes light Markdown: "**bold**" and "* " bullets. Shown as bold text and "•". */
fun simpleMarkdown(text: String): AnnotatedString = buildAnnotatedString {
    text.lines().forEachIndexed { i, raw ->
        if (i > 0) append("\n")
        val line = raw.replace(Regex("^\\s*[*-]\\s+"), "• ")
        line.split("**").forEachIndexed { j, part ->
            if (j % 2 == 1) withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) { append(part) } else append(part)
        }
    }
}
