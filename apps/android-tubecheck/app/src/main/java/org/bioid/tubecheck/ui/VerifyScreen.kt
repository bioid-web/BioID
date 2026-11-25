package org.bioid.tubecheck.ui

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import org.bioid.tubecheck.BioIdConfig
import org.bioid.tubecheck.model.Dataset
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.model.Network
import org.bioid.tubecheck.model.TimelineEvent
import org.bioid.tubecheck.model.TokenRecord
import org.bioid.tubecheck.model.TubeView
import org.bioid.tubecheck.parse.StatusKind
import org.bioid.tubecheck.parse.humanStatus
import org.bioid.tubecheck.parse.parseScan
import org.bioid.tubecheck.parse.statusKind
import org.bioid.tubecheck.tzkt.TubeResult
import org.bioid.tubecheck.tzkt.TzktClient
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter

sealed interface VerifyState {
    data object Idle : VerifyState
    data object Loading : VerifyState
    data class Found(val tube: TubeView) : VerifyState
    data class NotFound(val message: String) : VerifyState
    data class Failed(val message: String) : VerifyState
}

class VerifyViewModel(
    private val api: TzktClient = TzktClient(),
) : ViewModel() {
    private val _network = MutableStateFlow(BioIdConfig.DEFAULT)
    val network: StateFlow<Network> = _network
    private val _state = MutableStateFlow<VerifyState>(VerifyState.Idle)
    val state: StateFlow<VerifyState> = _state

    fun chooseNetwork(network: Network) {
        _network.value = network
        _state.value = VerifyState.Idle
    }

    fun lookup(raw: String) {
        val parsed = parseScan(raw)
        if (parsed is Lookup.Empty) return
        _state.value = VerifyState.Loading
        val current = _network.value
        viewModelScope.launch {
            _state.value = when (val result = api.loadTube(current, parsed)) {
                TubeResult.Empty -> VerifyState.Idle
                is TubeResult.Invalid -> VerifyState.NotFound("That does not look like a tube code or token id.")
                is TubeResult.NotFound -> VerifyState.NotFound(notFoundMessage(parsed))
                is TubeResult.Found -> VerifyState.Found(result.tube)
                is TubeResult.Failed -> VerifyState.Failed(result.message)
            }
        }
    }
}

private fun notFoundMessage(lookup: Lookup): String = when (lookup) {
    is Lookup.Code -> "No token found for that code. Check the code, or the tube may not be registered on this network."
    is Lookup.Token -> "No token found for that id on this network."
    else -> "No token found."
}

@Composable
fun VerifyScreen(vm: VerifyViewModel = viewModel()) {
    val state by vm.state.collectAsState()
    val network by vm.network.collectAsState()
    var code by remember { mutableStateOf("") }
    var scanning by remember { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        scanning = granted
    }

    Column(
        Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        NetworkPicker(network, onSelect = vm::chooseNetwork)
        Text(network.caption, style = MaterialTheme.typography.bodySmall, color = Ink.copy(alpha = 0.7f))

        if (scanning) {
            Box(Modifier.fillMaxWidth().height(260.dp).clip(RoundedCornerShape(16.dp))) {
                ScannerView(Modifier.fillMaxSize()) { raw ->
                    scanning = false
                    val parsed = parseScan(raw)
                    code = when (parsed) {
                        is Lookup.Code -> parsed.code
                        is Lookup.Token -> parsed.tokenId
                        else -> raw.trim()
                    }
                    vm.lookup(raw)
                }
            }
            TextButton(onClick = { scanning = false }) { Text("Cancel scan") }
        } else {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    label = { Text("Tube code or token id") },
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                    keyboardActions = KeyboardActions(onSearch = { vm.lookup(code) }),
                )
                Button(onClick = { permission.launch(Manifest.permission.CAMERA) }) { Text("Scan") }
            }
        }

        when (val s = state) {
            VerifyState.Idle -> Hint("Scan a tube's Data Matrix or QR code, or type its code.")
            VerifyState.Loading -> CircularProgressIndicator(Modifier.align(Alignment.CenterHorizontally))
            is VerifyState.NotFound -> Hint(s.message)
            is VerifyState.Failed -> Hint(s.message)
            is VerifyState.Found -> TubeDetail(s.tube)
        }

        Spacer(Modifier.height(8.dp))
        Text(
            "The chain proves a record was made, not that the tube is in the freezer.",
            style = MaterialTheme.typography.bodySmall,
            color = Ink.copy(alpha = 0.7f),
            modifier = Modifier.padding(bottom = 12.dp),
        )
    }
}

@Composable
private fun NetworkPicker(current: Network, onSelect: (Network) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("Network", style = MaterialTheme.typography.labelLarge, modifier = Modifier.padding(end = 8.dp))
        Box {
            FilterChip(selected = true, onClick = { open = true }, label = { Text(current.label) })
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                BioIdConfig.NETWORKS.forEach { network ->
                    DropdownMenuItem(
                        text = { Text(network.label + if (network.id == "mainnet") " (opt-in)" else " (default)") },
                        onClick = {
                            open = false
                            onSelect(network)
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun Hint(text: String) =
    Text(text, style = MaterialTheme.typography.bodyMedium, color = Ink.copy(alpha = 0.8f))

private val timeFmt = DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm").withZone(ZoneId.systemDefault())

@Composable
private fun TubeDetail(view: TubeView) {
    val token = view.token
    val uri = LocalUriHandler.current
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(10.dp),
        contentPadding = PaddingValues(bottom = 16.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        item {
            Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(token.code, style = MaterialTheme.typography.titleLarge, fontFamily = FontFamily.Monospace)
                    if (token.sampleType.isNotBlank()) {
                        Text(token.sampleType, style = MaterialTheme.typography.bodyMedium)
                    }
                    Text("${token.balanceUl} µL", style = MaterialTheme.typography.headlineSmall, color = Teal)
                    val holder = buildString {
                        append(view.wallet.label)
                        if (view.wallet.type.isNotBlank()) append(" · ${view.wallet.type}")
                        if (view.wallet.site.isNotBlank()) append(" · ${view.wallet.site}")
                    }
                    Text(
                        if (token.isEmpty) "Used up. Stays on record at 0 µL. Last held by $holder"
                        else "Held by $holder",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                    StatusBanner(token.status)
                    if (view.parents.isNotEmpty()) {
                        Text(
                            "Parent: " + view.parents.joinToString(" ← ") { it.code },
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                    if (view.children.isNotEmpty()) {
                        Text(
                            "Children: " + view.children.joinToString(", ") { it.code },
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                }
            }
        }
        if (view.datasets.own.isNotEmpty() || view.datasets.inherited.isNotEmpty()) {
            item { Text("Datasets", style = MaterialTheme.typography.titleMedium) }
            items(view.datasets.own + view.datasets.inherited) { DatasetRow(it) }
        }
        item { Text("Custody timeline", style = MaterialTheme.typography.titleMedium) }
        if (view.timeline.isEmpty()) {
            item { Hint("No contract events were returned for this tube.") }
        }
        items(view.timeline, key = { it.id }) { event ->
            EventRow(event, onOpen = { if (event.explorer.isNotEmpty()) uri.openUri(event.explorer) })
        }
    }
}

@Composable
private fun StatusBanner(status: String) {
    val kind = statusKind(status)
    if (kind == StatusKind.OK && status.isBlank()) return
    val (bg, fg, text) = when (kind) {
        StatusKind.WITHDRAWN -> Triple(
            RoseBg,
            Rose,
            when (status) {
                "frozen" -> "Frozen: consent withdrawn. This tube cannot be moved."
                "stopped" -> "Stopped: consent withdrawn (stop use). This tube cannot be moved."
                "destroyed" -> "Destroyed. Stays on record."
                "anonymised" -> "Anonymised after withdrawal."
                else -> "Status: ${humanStatus(status)}"
            },
        )
        StatusKind.TRANSIT -> Triple(AmberBg, Amber, "In transit. Custody passes only when the receiver confirms arrival.")
        StatusKind.PROCESS -> Triple(AmberBg, Amber, "In process.")
        StatusKind.OK -> Triple(Mist, Ink, "Status: ${humanStatus(status)}")
    }
    Text(
        text,
        style = MaterialTheme.typography.bodyMedium,
        color = fg,
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(bg)
            .padding(horizontal = 10.dp, vertical = 8.dp),
    )
}

@Composable
private fun DatasetRow(item: Dataset) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            val title = item.type.ifBlank { "Dataset" }
            Text(
                if (item.inherited) "$title (inherited from ${item.fromCode})" else title,
                fontWeight = FontWeight.Medium,
            )
            if (item.step.isNotBlank()) Text(item.step, style = MaterialTheme.typography.bodySmall)
            if (item.sha256.isNotBlank()) {
                Text(
                    "Fingerprint ${item.sha256.take(16)}…",
                    style = MaterialTheme.typography.bodySmall,
                    fontFamily = FontFamily.Monospace,
                )
            }
        }
    }
}

@Composable
private fun EventRow(event: TimelineEvent, onOpen: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = Color.White), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Text(event.label, fontWeight = FontWeight.Medium)
            if (event.summary.isNotBlank()) {
                Text(event.summary, style = MaterialTheme.typography.bodyMedium)
            }
            val whenText = formatTime(event.timestamp)
            Text(whenText, style = MaterialTheme.typography.bodySmall, color = Ink.copy(alpha = 0.7f))
            if (event.explorer.isNotEmpty()) {
                TextButton(onClick = onOpen) { Text("View on explorer") }
            }
        }
    }
}

private fun formatTime(iso: String): String = try {
    timeFmt.format(Instant.parse(iso))
} catch (_: Exception) {
    iso
}
