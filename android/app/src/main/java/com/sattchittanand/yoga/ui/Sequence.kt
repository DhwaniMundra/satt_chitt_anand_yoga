package com.sattchittanand.yoga.ui

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.Curricula
import com.sattchittanand.yoga.Curriculum
import com.sattchittanand.yoga.PlanItem
import com.sattchittanand.yoga.R

/** The reaction scale, 1 to 4, as the student taps it and the teacher reads it. */
val REACTIONS = listOf(R.string.reaction_1, R.string.reaction_2, R.string.reaction_3, R.string.reaction_4)

private val DOSE_UNITS = mapOf(
    "breaths" to R.plurals.dose_breaths,
    "seconds" to R.plurals.dose_seconds,
    "minutes" to R.plurals.dose_minutes,
    "rounds" to R.plurals.dose_rounds,
    "strokes" to R.plurals.dose_strokes,
)

/** "5 breaths", "3 min", "2.5 min": a unit the app does not know (the owner can type any in the Sheet) is shown as
 *  written, and so is the unit alone when the owner left the dose empty or wrote words in it. A count that is not
 *  whole takes the unit's word for many, its number as written. */
@Composable
fun doseLabel(p: PlanItem): String {
    val words = DOSE_UNITS[p.unit]
    return when {
        p.doseLabel != null -> words?.let { pluralStringResource(it, 2, 2).replaceFirst(Regex("[0-9०-९]+"), p.doseLabel) } ?: "${p.doseLabel} ${p.unit}".trim()
        p.dose == null -> p.unit
        else -> words?.let { pluralStringResource(it, p.dose, p.dose) } ?: "${p.dose} ${p.unit}".trim()
    }
}

/** A curriculum's items in order, each with how much and how to do it; with [collapsed], that many until "Show all". */
@Composable
fun Sequence(plan: Curriculum, curricula: Curricula, lang: String, collapsed: Int = plan.items.size) {
    var all by rememberSaveable(plan.key) { mutableStateOf(false) }
    val shown = if (all) plan.items else plan.items.take(collapsed)
    shown.forEachIndexed { i, p ->
        if (i > 0) HorizontalDivider(color = Palette.line)
        Row(verticalAlignment = Alignment.Top) {
            Column(Modifier.weight(1f).padding(end = 12.dp)) {
                Text(curricula.library[p.item]?.title(lang) ?: p.item, style = MaterialTheme.typography.bodyLarge)
                Text(p.cue, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
            }
            Text(doseLabel(p), style = MaterialTheme.typography.labelLarge, color = Palette.moss)
        }
    }
    if (plan.items.size > collapsed) {
        TextButton(onClick = { all = !all }) {
            Text(if (all) stringResource(R.string.show_less) else stringResource(R.string.show_all, plan.items.size))
        }
    }
}
