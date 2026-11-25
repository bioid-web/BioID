package org.bioid.tubecheck.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import org.bioid.tubecheck.ui.custody.CustodyMode
import org.bioid.tubecheck.ui.custody.CustodyScreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppRoot() {
    var tab by remember { mutableIntStateOf(0) }
    val title = when (tab) {
        0 -> "BioID Tube Check"
        1 -> "Ship (preview)"
        else -> "Receive (preview)"
    }
    Scaffold(
        topBar = { TopAppBar(title = { Text(title, fontWeight = FontWeight.SemiBold) }) },
        bottomBar = {
            NavigationBar {
                NavigationBarItem(
                    selected = tab == 0,
                    onClick = { tab = 0 },
                    icon = { Icon(Icons.Default.Search, contentDescription = "Verify") },
                    label = { Text("Verify") },
                )
                NavigationBarItem(
                    selected = tab == 1,
                    onClick = { tab = 1 },
                    icon = { Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Ship") },
                    label = { Text("Ship") },
                )
                NavigationBarItem(
                    selected = tab == 2,
                    onClick = { tab = 2 },
                    icon = { Icon(Icons.Default.Check, contentDescription = "Receive") },
                    label = { Text("Receive") },
                )
            }
        },
    ) { pad ->
        Box(Modifier.padding(pad)) {
            when (tab) {
                0 -> VerifyScreen()
                1 -> CustodyScreen(CustodyMode.SHIP)
                else -> CustodyScreen(CustodyMode.RECEIVE)
            }
        }
    }
}
