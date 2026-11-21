package com.sattchittanand.yoga.ui

import android.os.SystemClock
import android.provider.Settings
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.withFrameMillis
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.R
import kotlinx.coroutines.delay
import kotlin.math.PI
import kotlin.math.cos

/** One breath: four seconds in, four out. */
private const val BREATH_MS = 8_000L
/** After this long, a line says the studio's server is slow, so a long wait does not feel stuck. */
private const val SLOW_MS = 15_000L

/**
 * The wait for signing in, or for the first screen when nothing is kept on the phone, as a breath: a circle in the
 * studio's colours that fills over four seconds and empties over four, with "Breathe in…" and "Breathe out…" in step,
 * so the server's six to ten seconds are one or two breaths. Under it, what is happening, in a small line; after
 * fifteen seconds, that the server is slow and the app still at it. Timed from [since] (elapsedRealtime), so the
 * breath goes on unbroken from the sign-in form to the wait for the first screen. With animations turned off on the
 * phone, the circle stands still and the words still change.
 */
@Composable
fun BreathingWait(signingIn: Boolean, since: Long) {
    val context = LocalContext.current
    val still = remember { Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) == 0f }
    var now by remember { mutableLongStateOf(SystemClock.elapsedRealtime()) }
    LaunchedEffect(still) {
        while (true) {
            if (still) delay(250) else withFrameMillis { }
            now = SystemClock.elapsedRealtime()
        }
    }
    val elapsed = (now - since).coerceAtLeast(0)
    val t = (elapsed % BREATH_MS) / BREATH_MS.toFloat() // 0 to 1 over one breath
    val breathingIn = t < 0.5f
    val depth = if (breathingIn) t * 2 else (1 - t) * 2 // 0 empty, 1 full
    val fill = if (still) 0.8f else 0.5f + 0.5f * ((1 - cos(PI * depth)) / 2).toFloat()
    Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) { // and takes the touches meant for what is under it
        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp), verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally) {
            BrandHeader(large = true)
            Spacer(Modifier.height(40.dp))
            Box(Modifier.size(CIRCLE.dp).border(1.dp, Palette.line, CircleShape), contentAlignment = Alignment.Center) {
                Box(Modifier.size((CIRCLE * fill).dp).background(Palette.mossLight, CircleShape).border(2.dp, Palette.moss.copy(alpha = 0.35f), CircleShape))
            }
            Spacer(Modifier.height(28.dp))
            Text(stringResource(if (breathingIn) R.string.breathe_in else R.string.breathe_out), style = MaterialTheme.typography.titleLarge,
                color = Palette.moss)
            Spacer(Modifier.height(12.dp))
            Text(stringResource(if (signingIn) R.string.signing_in else R.string.connecting), style = MaterialTheme.typography.bodyMedium,
                color = Palette.muted)
            Spacer(Modifier.height(8.dp))
            // Kept in place from the start, unseen, so nothing moves when it shows.
            val slow = elapsed >= SLOW_MS
            Text(stringResource(R.string.server_slow), Modifier.alpha(if (slow) 1f else 0f).then(if (slow) Modifier else Modifier.clearAndSetSemantics { }),
                style = MaterialTheme.typography.bodyMedium, color = Palette.saffron, textAlign = TextAlign.Center)
        }
    }
}

private const val CIRCLE = 168
