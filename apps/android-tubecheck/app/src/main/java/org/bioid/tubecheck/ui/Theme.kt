package org.bioid.tubecheck.ui

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

val Ink = Color(0xFF0F2A33)
val Teal = Color(0xFF0E7C86)
val Mist = Color(0xFFF2F6F7)
val Amber = Color(0xFFB45309)
val AmberBg = Color(0xFFFEF3C7)
val Rose = Color(0xFF9F1239)
val RoseBg = Color(0xFFFFE4E6)
val Green = Color(0xFF065F46)
val GreenBg = Color(0xFFD1FAE5)

private val Colors = lightColorScheme(
    primary = Teal,
    onPrimary = Color.White,
    background = Mist,
    surface = Color.White,
    onBackground = Ink,
    onSurface = Ink,
)

@Composable
fun TubeCheckTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = Colors, content = content)
}
