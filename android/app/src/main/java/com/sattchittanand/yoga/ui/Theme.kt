package com.sattchittanand.yoga.ui

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Earth and temple tones, after the studio's site: moss, saffron, warm stone.
object Palette {
    val cream = Color(0xFFF6F1E7)
    val paper = Color(0xFFFFFCF6)
    val moss = Color(0xFF3F5B45)
    val mossLight = Color(0xFFDDE6D8)
    val saffron = Color(0xFFC26A2D)
    val saffronLight = Color(0xFFF6E0CC)
    val ink = Color(0xFF2B2A26)
    val muted = Color(0xFF6E6A60)
    val line = Color(0xFFE5DDCF)
    val danger = Color(0xFFB3261E)
}

private val colors = lightColorScheme(
    primary = Palette.moss,
    onPrimary = Color.White,
    primaryContainer = Palette.mossLight,
    onPrimaryContainer = Palette.ink,
    secondary = Palette.saffron,
    onSecondary = Color.White,
    secondaryContainer = Palette.saffronLight,
    onSecondaryContainer = Palette.ink,
    background = Palette.cream,
    onBackground = Palette.ink,
    surface = Palette.paper,
    onSurface = Palette.ink,
    surfaceVariant = Palette.cream,
    onSurfaceVariant = Palette.muted,
    surfaceContainer = Palette.paper,
    outline = Palette.line,
    outlineVariant = Palette.line,
    error = Palette.danger,
)

private val serif = FontFamily.Serif

// Body text is a size larger than Material's default: many students read on small phones, some without glasses.
private val type = Typography(
    displaySmall = TextStyle(fontFamily = serif, fontWeight = FontWeight.Normal, fontSize = 34.sp, lineHeight = 40.sp),
    headlineSmall = TextStyle(fontFamily = serif, fontWeight = FontWeight.Normal, fontSize = 26.sp, lineHeight = 32.sp),
    titleLarge = TextStyle(fontFamily = serif, fontWeight = FontWeight.Normal, fontSize = 22.sp, lineHeight = 28.sp),
    titleMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 17.sp, lineHeight = 24.sp),
    bodyLarge = TextStyle(fontSize = 17.sp, lineHeight = 25.sp),
    bodyMedium = TextStyle(fontSize = 15.sp, lineHeight = 22.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp),
    labelMedium = TextStyle(fontWeight = FontWeight.Medium, fontSize = 13.sp, lineHeight = 18.sp, letterSpacing = 0.4.sp),
)

private val shapes = Shapes(
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
)

@Composable
fun YogaTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = colors, typography = type, shapes = shapes, content = content)
}
