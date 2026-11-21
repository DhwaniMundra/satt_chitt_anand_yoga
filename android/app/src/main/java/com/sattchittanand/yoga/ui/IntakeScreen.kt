package com.sattchittanand.yoga.ui

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FilterChipDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.listSaver
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshots.SnapshotStateList
import androidx.compose.runtime.toMutableStateList
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.Intake
import com.sattchittanand.yoga.IntakeRating
import com.sattchittanand.yoga.Limits
import com.sattchittanand.yoga.R

val FOODS = listOf("vegetarian" to R.string.food_vegetarian, "eggetarian" to R.string.food_eggetarian,
    "non_vegetarian" to R.string.food_non_vegetarian, "vegan" to R.string.food_vegan)
val PAIN_AREAS = listOf("knee" to R.string.pain_knee, "back" to R.string.pain_back, "neck" to R.string.pain_neck,
    "shoulder" to R.string.pain_shoulder, "hip" to R.string.pain_hip, "other" to R.string.pain_other)

/** The pain areas ticked, kept through a rotation. */
private val PainSaver = listSaver<SnapshotStateList<String>, String>({ it.toList() }, { it.toMutableStateList() })

/** The self-assessment, kept through a rotation: each pose as [item, reaction (0 for none), strain or pain]. */
private val RatingsSaver = listSaver<SnapshotStateList<IntakeRating>, List<Any>>(
    save = { ratings -> ratings.map { listOf(it.item, it.reaction ?: 0, it.pain) } },
    restore = { saved -> saved.map { (item, reaction, pain) -> IntakeRating(item as String, (reaction as Int).takeIf { it > 0 }, pain as Boolean) }.toMutableStateList() },
)

/** The intake: a student's answers about themselves, for the teacher to place them in a batch. Filled after sign-up,
 *  changed later from the Me tab; it opens with the answers already given. */
@Composable
fun IntakeScreen(vm: AppViewModel, close: () -> Unit) {
    BackHandler(onBack = close)
    LaunchedEffect(Unit) { vm.loadIntake() }
    if (!vm.intakeRead) return Waiting(vm, vm::loadIntake)
    IntakeForm(vm, vm.intake, close)
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun IntakeForm(vm: AppViewModel, before: Intake?, close: () -> Unit) {
    val teacher = LocalTeacher.current
    val curricula = vm.curricula
    val assessment = remember { vm.assessment() }
    var age by rememberSaveable { mutableStateOf(before?.age?.toString().orEmpty()) }
    var height by rememberSaveable { mutableStateOf(before?.heightCm?.toString().orEmpty()) }
    var weight by rememberSaveable { mutableStateOf(before?.weightKg?.toString().orEmpty()) }
    var food by rememberSaveable { mutableStateOf(before?.food) }
    var meals by rememberSaveable { mutableStateOf(before?.meals.orEmpty()) }
    val pain = rememberSaveable(saver = PainSaver) { mutableStateListOf<String>().apply { before?.pain?.let { addAll(it) } } }
    var painNote by rememberSaveable { mutableStateOf(before?.painNote.orEmpty()) }
    val ratings = rememberSaveable(saver = RatingsSaver) {
        mutableStateListOf<IntakeRating>().apply {
            assessment.forEach { (item, _) -> add(before?.ratings?.firstOrNull { it.item == item } ?: IntakeRating(item, null, false)) }
        }
    }
    val thanks = stringResource(R.string.intake_thanks, teacher)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BackHeader(stringResource(R.string.intake_title), close)
        // Who sees these answers, and what for, before any is given.
        Text(stringResource(R.string.intake_consent, teacher), style = MaterialTheme.typography.bodyMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            NumberField(age, { age = it }, R.string.age, Limits.AGE, Modifier.weight(1f))
            NumberField(height, { height = it }, R.string.height_cm, Limits.HEIGHT_CM, Modifier.weight(1f))
            NumberField(weight, { weight = it }, R.string.weight_kg, Limits.WEIGHT_KG, Modifier.weight(1f))
        }
        Label(stringResource(R.string.food_title))
        Choices(FOODS.map { stringResource(it.second) }, FOODS.indexOfFirst { it.first == food }.takeIf { it >= 0 }, perRow = 2) { food = FOODS[it].first }
        LimitedField(meals, { meals = it }, Limits.MEALS, placeholder = { Text(stringResource(R.string.meals_hint)) })
        Label(stringResource(R.string.pain_title))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PAIN_AREAS.forEach { (key, label) ->
                FilterChip(selected = key in pain, onClick = { if (key in pain) pain.remove(key) else pain.add(key) }, label = { Text(stringResource(label)) },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Palette.danger, selectedLabelColor = Color.White))
            }
        }
        LimitedField(painNote, { painNote = it }, Limits.PAIN_NOTE, placeholder = { Text(stringResource(R.string.pain_note_hint)) })
        Label(stringResource(R.string.assessment_title))
        Text(stringResource(R.string.assessment_help), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        assessment.forEachIndexed { i, (item, how) ->
            val r = ratings[i]
            SectionCard {
                Text(curricula?.library?.get(item)?.title(vm.prefs.lang) ?: item, style = MaterialTheme.typography.titleMedium)
                Text(how, style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
                Choices(REACTIONS.map { stringResource(it) }, r.reaction?.minus(1)) { j ->
                    ratings[i] = r.copy(reaction = if (r.reaction == j + 1) null else j + 1)
                }
                FilterChip(selected = r.pain, onClick = { ratings[i] = r.copy(pain = !r.pain) }, label = { Text(stringResource(R.string.pain_flag)) },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Palette.danger, selectedLabelColor = Color.White))
            }
        }
        val inRange = listOf(age to Limits.AGE, height to Limits.HEIGHT_CM, weight to Limits.WEIGHT_KG).all { (typed, range) -> typed.toIntOrNull() in range }
        val ready = inRange && food != null
        val saving = vm.saving("intake")
        Button(
            onClick = {
                if (saving) return@Button
                val intake = Intake(age.toInt(), height.toInt(), weight.toInt(), food!!, meals.trim().ifEmpty { null }, pain.toList(),
                    painNote.trim().ifEmpty { null }, ratings.toList(), null)
                vm.saveIntake(intake, thanks, close)
            },
            enabled = ready, modifier = Modifier.fillMaxWidth(),
        ) { SavingLabel(stringResource(R.string.send_to, teacher), saving) }
    }
}

/** A whole number checked as the server checks it: outside [range], the field says the range. */
@Composable
private fun NumberField(typed: String, set: (String) -> Unit, label: Int, range: IntRange, modifier: Modifier) {
    val outside = typed.toIntOrNull()?.let { it !in range } == true
    OutlinedTextField(
        typed, { set(it.filter(Char::isDigit).take(3)) }, label = { Text(stringResource(label)) }, singleLine = true,
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number), modifier = modifier, isError = outside,
        supportingText = if (outside) ({ Text(stringResource(R.string.range_hint, range.first, range.last)) }) else null,
    )
}
