package com.example.crackdetection.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val LightColors = lightColorScheme(
    primary = Color(0xFF087D63),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFDDF4EB),
    onPrimaryContainer = Color(0xFF073F33),
    background = Color(0xFFF4F8F6),
    onBackground = Color(0xFF14231F),
    surface = Color.White,
    onSurface = Color(0xFF14231F),
    error = Color(0xFFB3261E),
)

@Composable
fun CrackDetectionTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = LightColors, content = content)
}
