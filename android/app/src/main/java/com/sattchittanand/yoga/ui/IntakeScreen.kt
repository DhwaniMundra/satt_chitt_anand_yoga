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
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.sattchittanand.yoga.AppViewModel
import com.sattchittanand.yoga.Intake
import com.sattchittanand.yoga.IntakeRating
import com.sattchittanand.yoga.R

val FOODS = listOf("vegetarian" to R.string.food_vegetarian, "eggetarian" to R.string.food_eggetarian,
    "non_vegetarian" to R.string.food_non_vegetarian, "vegan" to R.string.food_vegan)
val PAIN_AREAS = listOf("knee" to R.string.pain_knee, "back" to R.string.pain_back, "neck" to R.string.pain_neck,
    "shoulder" to R.string.pain_shoulder, "hip" to R.string.pain_hip, "other" to R.string.pain_other)

/** The intake: a student's answers about themselves, for the teacher to place them in a batch. Filled after sign-up,
 *  changed later from Me; it opens with the answers already given. */
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
    val pain = remember { mutableStateListOf<String>().apply { before?.pain?.let { addAll(it) } } }
    var painNote by rememberSaveable { mutableStateOf(before?.painNote.orEmpty()) }
    val ratings = remember {
        mutableStateListOf<IntakeRating>().apply {
            assessment.forEach { (item, _) -> add(before?.ratings?.firstOrNull { it.item == item } ?: IntakeRating(item, null, false)) }
        }
    }
    val thanks = stringResource(R.string.intake_thanks, teacher)
    val number = KeyboardOptions(keyboardType = KeyboardType.Number)
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        BackHeader(stringResource(R.string.intake_title), close)
        Text(stringResource(R.string.intake_help, teacher), style = MaterialTheme.typography.bodyMedium, color = Palette.muted)
        // Who sees these answers, before any is given.
        Text(stringResource(R.string.intake_consent, teacher), style = MaterialTheme.typography.bodyMedium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedTextField(age, { age = it.filter(Char::isDigit).take(3) }, label = { Text(stringResource(R.string.age)) }, singleLine = true,
                keyboardOptions = number, modifier = Modifier.weight(1f))
            OutlinedTextField(height, { height = it.filter(Char::isDigit).take(3) }, label = { Text(stringResource(R.string.height_cm)) }, singleLine = true,
                keyboardOptions = number, modifier = Modifier.weight(1f))
            OutlinedTextField(weight, { weight = it.filter(Char::isDigit).take(3) }, label = { Text(stringResource(R.string.weight_kg)) }, singleLine = true,
                keyboardOptions = number, modifier = Modifier.weight(1f))
        }
        Label(stringResource(R.string.food_title))
        Choices(FOODS.map { stringResource(it.second) }, FOODS.indexOfFirst { it.first == food }.takeIf { it >= 0 }, perRow = 2) { food = FOODS[it].first }
        OutlinedTextField(meals, { meals = it }, placeholder = { Text(stringResource(R.string.meals_hint)) }, modifier = Modifier.fillMaxWidth())
        Label(stringResource(R.string.pain_title))
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            PAIN_AREAS.forEach { (key, label) ->
                FilterChip(selected = key in pain, onClick = { if (key in pain) pain.remove(key) else pain.add(key) }, label = { Text(stringResource(label)) },
                    colors = FilterChipDefaults.filterChipColors(selectedContainerColor = Palette.danger, selectedLabelColor = Color.White))
            }
        }
        OutlinedTextField(painNote, { painNote = it }, placeholder = { Text(stringResource(R.string.pain_note_hint)) }, modifier = Modifier.fillMaxWidth())
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
        val ready = age.toIntOrNull() != null && height.toIntOrNull() != null && weight.toIntOrNull() != null && food != null
        Button(
            onClick = {
                val intake = Intake(age.toInt(), height.toInt(), weight.toInt(), food!!, meals.trim().ifEmpty { null }, pain.toList(),
                    painNote.trim().ifEmpty { null }, ratings.toList(), null)
                vm.saveIntake(intake, thanks, close)
            },
            enabled = ready && !vm.busy, modifier = Modifier.fillMaxWidth(),
        ) { Text(stringResource(R.string.send_to, teacher)) }
    }
}
