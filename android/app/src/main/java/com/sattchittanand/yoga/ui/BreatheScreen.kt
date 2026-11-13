package com.sattchittanand.yoga.ui

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.R
import kotlinx.coroutines.delay

/** One breathing rhythm: a label, and its phases as (word, seconds). */
private data class Pace(val label: Int, val phases: List<Pair<Int, Int>>)

private val PACES = listOf(
    Pace(R.string.pace_calm, listOf(R.string.breathe_in to 4, R.string.breathe_out to 6)),
    Pace(R.string.pace_even, listOf(R.string.breathe_in to 5, R.string.breathe_out to 5)),
    Pace(R.string.pace_box, listOf(R.string.breathe_in to 4, R.string.hold to 4, R.string.breathe_out to 4, R.string.hold to 4)),
)
private const val SMALL = 0.5f

/** A circle that grows as you breathe in and shrinks as you breathe out: follows the eye, not the words. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun BreatheScreen() {
    var paceIndex by rememberSaveable { mutableIntStateOf(0) }
    var running by remember { mutableStateOf(false) }
    var phase by remember { mutableIntStateOf(R.string.breathe_in) }
    var breaths by remember { mutableIntStateOf(0) }
    val scale = remember { Animatable(SMALL) }
    val haptics = LocalHapticFeedback.current

    LaunchedEffect(running, paceIndex) {
        if (!running) {
            scale.animateTo(SMALL, tween(800))
            return@LaunchedEffect
        }
        breaths = 0
        while (true) {
            for ((word, seconds) in PACES[paceIndex].phases) {
                phase = word
                haptics.performHapticFeedback(HapticFeedbackType.TextHandleMove)
                when (word) {
                    R.string.breathe_in -> scale.animateTo(1f, tween(seconds * 1000, easing = FastOutSlowInEasing))
                    R.string.breathe_out -> scale.animateTo(SMALL, tween(seconds * 1000, easing = FastOutSlowInEasing))
                    else -> delay(seconds * 1000L)
                }
            }
            breaths++
        }
    }

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
    ) {
        Text(stringResource(R.string.breathe_title), style = MaterialTheme.typography.headlineSmall, modifier = Modifier.fillMaxWidth())
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            PACES.forEachIndexed { i, pace ->
                FilterChip(selected = paceIndex == i, onClick = { paceIndex = i }, label = { Text(stringResource(pace.label)) })
            }
        }
        Box(Modifier.size(280.dp), contentAlignment = Alignment.Center) {
            Box(Modifier.size(280.dp).background(Palette.mossLight.copy(alpha = 0.35f), CircleShape))
            Box(
                Modifier.size(280.dp)
                    .graphicsLayer { scaleX = scale.value; scaleY = scale.value }
                    .background(Brush.radialGradient(listOf(Palette.mossLight, Palette.moss)), CircleShape),
            )
            Text(
                if (running) stringResource(phase) else "",
                style = MaterialTheme.typography.titleLarge,
                color = Color.White,
                textAlign = TextAlign.Center,
            )
        }
        Text(
            if (running) stringResource(R.string.breaths, breaths) else " ",
            style = MaterialTheme.typography.titleMedium,
            color = Palette.muted,
        )
        Button(onClick = { running = !running }, modifier = Modifier.fillMaxWidth().height(56.dp)) {
            Text(stringResource(if (running) R.string.stop else R.string.start))
        }
        Text(stringResource(R.string.breathe_note), style = MaterialTheme.typography.bodyMedium, color = Palette.muted, textAlign = TextAlign.Center)
        Spacer(Modifier.height(8.dp))
    }
}
