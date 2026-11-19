package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.ItemReview
import com.sattchittanand.yoga.R
import com.sattchittanand.yoga.SessionInsight

/** How one class went, item by item: how many said each reaction, who felt strain or pain (first), and the notes. */
@Composable
fun ClassReviewScreen(vm: AppViewModel, session: SessionInsight) {
    LaunchedEffect(session.id) { vm.loadReview(session.id) }
    val review = vm.review
    val curricula = vm.curricula
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(stringResource(R.string.review_title), style = MaterialTheme.typography.headlineSmall)
        Text("${session.className} · ${dayLabel(session.startsAt)} · ${timeLabel(session.startsAt)}", color = Palette.muted)
        if (review == null || curricula == null) {
            Waiting(vm, { vm.loadReview(session.id) }, Modifier.fillMaxWidth())
            return@Column
        }
        curricula.find(review.curriculum)?.let { Label(it.name) }
        Text(stringResource(R.string.review_counts, review.joined, review.answered), style = MaterialTheme.typography.bodyMedium)
        if (review.answered == 0) {
            Text(stringResource(R.string.review_empty), color = Palette.muted)
            return@Column
        }
        review.items.filter { it.reactions.sum() > 0 || it.pain.isNotEmpty() || it.notes.isNotEmpty() }.forEach { item ->
            ItemReviewCard(curricula.library[item.item]?.title(vm.prefs.lang) ?: item.item, item)
        }
    }
}

@Composable
private fun ItemReviewCard(title: String, item: ItemReview) {
    SectionCard(tint = if (item.pain.isNotEmpty()) Palette.saffronLight else Palette.paper) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        val most = item.reactions.max().coerceAtLeast(1)
        REACTIONS.forEachIndexed { i, word ->
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(stringResource(word), Modifier.width(96.dp), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                Bar(item.reactions[i].toFloat() / most, Palette.moss, Modifier.weight(1f))
                Text(item.reactions[i].toString(), Modifier.width(24.dp), style = MaterialTheme.typography.bodyMedium)
            }
        }
        item.pain.forEach { (name, note) ->
            Text("${stringResource(R.string.pain_flag)}: $name" + (note?.let { " · “$it”" } ?: ""),
                style = MaterialTheme.typography.bodyMedium, color = Palette.danger)
        }
        item.notes.forEach { (name, text) ->
            Text("“$text” · $name", style = MaterialTheme.typography.bodyMedium)
        }
    }
}
