package org.bioid.tubecheck.ui.custody

import android.Manifest
import android.app.Application
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.compose.viewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import org.bioid.tubecheck.custody.CustodyAuthException
import org.bioid.tubecheck.custody.CustodyClient
import org.bioid.tubecheck.custody.CustodyException
import org.bioid.tubecheck.custody.CustodyIntent
import org.bioid.tubecheck.custody.InboundTube
import org.bioid.tubecheck.custody.Preflight
import org.bioid.tubecheck.custody.StaffSession
import org.bioid.tubecheck.custody.SubmitResult
import org.bioid.tubecheck.custody.WalletOption
import org.bioid.tubecheck.custody.WalletType
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.parse.parseScan
import org.bioid.tubecheck.settings.AppSettings
import org.bioid.tubecheck.ui.Amber
import org.bioid.tubecheck.ui.AmberBg
import org.bioid.tubecheck.ui.Green
import org.bioid.tubecheck.ui.GreenBg
import org.bioid.tubecheck.ui.ScannerView
import java.util.UUID

enum class CustodyMode { SHIP, RECEIVE }

private data class PreviewWallet(val label: String, val type: WalletType)

private data class PreviewTube(val code: String, val volumeUl: Long, val fromSite: String)

private val previewWallets = listOf(
    PreviewWallet("Freezer A (synthetic)", WalletType.STORAGE),
    PreviewWallet("Reception (synthetic)", WalletType.INTAKE),
    PreviewWallet("Quarantine shelf (synthetic)", WalletType.QUARANTINE),
    PreviewWallet("Courier to partner (synthetic)", WalletType.TRANSIT),
)

private val inboundPreview = listOf(
    PreviewTube("SY00000301", 500, "Partner lab (synthetic)"),
    PreviewTube("SY00000302", 250, "Partner lab (synthetic)"),
)

data class CustodyUiState(
    val configured: Boolean = false,
    val loading: Boolean = false,
    val session: StaffSession? = null,
    val inbound: List<InboundTube> = emptyList(),
    val error: String? = null,
    val code: String? = null,
    val selected: InboundTube? = null,
    val dest: WalletOption? = null,
    val preflight: Preflight? = null,
    val submitting: Boolean = false,
    val result: SubmitResult? = null,
)

class CustodyViewModel(
    application: Application,
    private val mode: CustodyMode,
    private val api: CustodyClient = CustodyClient(),
) : AndroidViewModel(application) {
    private val store = AppSettings(application)
    private val _state = MutableStateFlow(CustodyUiState())
    val state: StateFlow<CustodyUiState> = _state

    fun refresh() {
        val settings = store.signing()
        if (!settings.configured) {
            _state.value = CustodyUiState(configured = false)
            return
        }
        _state.update { it.copy(configured = true, loading = true, error = null, result = null) }
        viewModelScope.launch {
            try {
                val session = api.me(settings)
                val inbound = if (mode == CustodyMode.RECEIVE) api.inbound(settings) else emptyList()
                _state.update {
                    it.copy(
                        loading = false,
                        session = session,
                        inbound = inbound,
                        error = null,
                    )
                }
            } catch (e: CustodyAuthException) {
                _state.update { it.copy(loading = false, error = e.message, session = null) }
            } catch (e: CustodyException) {
                _state.update { it.copy(loading = false, error = e.message) }
            } catch (_: Exception) {
                _state.update {
                    it.copy(loading = false, error = "Could not reach the signing service. Check the address in Settings.")
                }
            }
        }
    }

    fun selectInbound(tube: InboundTube) {
        _state.update { it.copy(code = tube.code, selected = tube, result = null, preflight = null, error = null) }
    }

    fun enterCode(raw: String) {
        val parsed = parseScan(raw)
        val code = when (parsed) {
            is Lookup.Code -> parsed.code
            else -> raw.trim()
        }
        val known = _state.value.inbound.firstOrNull { it.code.equals(code, ignoreCase = true) }
        if (mode == CustodyMode.RECEIVE && _state.value.configured && known == null) {
            _state.update {
                it.copy(
                    code = null,
                    selected = null,
                    error = "That tube is not on the inbound list for this site.",
                )
            }
        } else {
            _state.update {
                it.copy(
                    code = code,
                    selected = known ?: InboundTube(0, code, "scanned", 0),
                    error = null,
                    result = null,
                    preflight = null,
                )
            }
        }
    }

    fun choose(dest: WalletOption) {
        _state.update { it.copy(dest = dest, result = null, preflight = null) }
    }

    fun submit() {
        val settings = store.signing()
        val current = _state.value
        val code = current.code ?: return
        val dest = current.dest ?: return
        val intent = CustodyIntent(
            clientRequestId = UUID.randomUUID().toString(),
            mode = if (mode == CustodyMode.SHIP) "ship" else "receive",
            tokenId = current.selected?.tokenId?.takeIf { it > 0 },
            tubeCode = code,
            toWallet = dest.address,
            registeredVia = "android-tubecheck",
        )
        _state.update { it.copy(submitting = true, error = null, result = null) }
        viewModelScope.launch {
            try {
                val pre = api.preflight(settings, intent)
                _state.update { it.copy(preflight = pre) }
                if (!pre.ok) {
                    _state.update { it.copy(submitting = false, result = SubmitResult.Review(pre.problems)) }
                    return@launch
                }
                val result = api.submit(settings, intent)
                _state.update { it.copy(submitting = false, result = result) }
            } catch (e: CustodyException) {
                _state.update { it.copy(submitting = false, result = SubmitResult.Failed(e.message ?: "Request failed.", false)) }
            } catch (_: Exception) {
                _state.update {
                    it.copy(
                        submitting = false,
                        result = SubmitResult.Failed("Could not reach the signing service. Try again.", true),
                    )
                }
            }
        }
    }

    fun resetResult() {
        _state.update { it.copy(result = null, preflight = null, code = null, selected = null, dest = null, error = null) }
        refresh()
    }
}

class CustodyVmFactory(
    private val app: Application,
    private val mode: CustodyMode,
) : ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <T : ViewModel> create(modelClass: Class<T>): T = CustodyViewModel(app, mode) as T
}

@Composable
fun CustodyScreen(mode: CustodyMode) {
    val app = LocalContext.current.applicationContext as Application
    val vm: CustodyViewModel = viewModel(key = mode.name, factory = CustodyVmFactory(app, mode))
    val state by vm.state.collectAsState()

    LaunchedEffect(mode) { vm.refresh() }

    if (!state.configured) {
        PreviewCustody(mode)
        return
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        val session = state.session
        if (session != null) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(2.dp)) {
                    Text(session.name, fontWeight = FontWeight.SemiBold)
                    Text(session.org, style = MaterialTheme.typography.bodyMedium)
                    Text("Signing stays on the Shadownet service. This phone holds no key.", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        Text(
            if (mode == CustodyMode.SHIP) "Ship a tube" else "Receive a tube",
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            if (mode == CustodyMode.SHIP)
                "The sender moves the tube into a transit wallet. The receiving site confirms it on arrival."
            else
                "Custody passes only after the receiving custodian confirms arrival.",
            style = MaterialTheme.typography.bodyMedium,
        )

        if (state.loading) {
            CircularProgressIndicator()
            return
        }
        state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        val result = state.result
        if (result != null) {
            ResultCard(result) { vm.resetResult() }
            return
        }

        if (mode == CustodyMode.RECEIVE) {
            Text("Inbound", style = MaterialTheme.typography.titleMedium)
            if (state.inbound.isEmpty()) {
                Text("Nothing is waiting in transit for this site.", style = MaterialTheme.typography.bodyMedium)
            }
            state.inbound.forEach { tube ->
                Card(
                    Modifier.fillMaxWidth().clickable { vm.selectInbound(tube) },
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(tube.code, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Medium)
                        val volume = if (tube.volumeUl > 0) " · ${tube.volumeUl} µL" else ""
                        Text("From ${tube.fromSite}$volume", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        CodeEntry { vm.enterCode(it) }

        val code = state.code ?: return
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text(code, style = MaterialTheme.typography.titleLarge, fontFamily = FontFamily.Monospace)
                state.selected?.takeIf { it.volumeUl > 0 }?.let { Text("${it.volumeUl} µL") }
            }
        }

        val destinations = if (mode == CustodyMode.SHIP) {
            session?.shipDestinations.orEmpty()
        } else {
            session?.receiveDestinations.orEmpty()
        }
        Text(
            if (mode == CustodyMode.SHIP) "Transit wallet" else "Receive into",
            style = MaterialTheme.typography.titleMedium,
        )
        destinations.forEach { wallet ->
            Row(
                Modifier.fillMaxWidth().clickable { vm.choose(wallet) }.padding(vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = state.dest == wallet, onClick = { vm.choose(wallet) })
                Column {
                    Text(wallet.label)
                    Text(wallet.type.name, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
        if (mode == CustodyMode.RECEIVE) {
            Text("If the tube looks wrong, receive it into quarantine.", style = MaterialTheme.typography.bodySmall)
        }

        Button(
            onClick = { vm.submit() },
            enabled = state.dest != null && !state.submitting,
        ) {
            Text(if (state.submitting) "Signing…" else if (mode == CustodyMode.SHIP) "Ship" else "Receive")
        }
        if (state.dest != null) {
            Text("$code → ${state.dest?.label}", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun ResultCard(result: SubmitResult, onAgain: () -> Unit) {
    val (title, body, color, bg) = when (result) {
        is SubmitResult.Injected ->
            Quadruple("Signed on Shadownet", "Operation ${result.opHash}", Green, GreenBg)
        is SubmitResult.Review ->
            Quadruple("Needs review", result.reasons.joinToString("\n").ifBlank { "The service did not inject this." }, Amber, AmberBg)
        is SubmitResult.Failed ->
            Quadruple("Not sent", result.message, MaterialTheme.colorScheme.error, MaterialTheme.colorScheme.errorContainer)
    }
    Card(colors = CardDefaults.cardColors(containerColor = bg), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, fontWeight = FontWeight.SemiBold, color = color)
            Text(body, fontFamily = if (result is SubmitResult.Injected) FontFamily.Monospace else FontFamily.Default)
            Button(onClick = onAgain) { Text("Start another") }
        }
    }
}

private data class Quadruple<A, B, C, D>(val a: A, val b: B, val c: C, val d: D)

@Composable
private fun PreviewCustody(mode: CustodyMode) {
    var scanned by remember { mutableStateOf<PreviewTube?>(null) }
    var lookupError by remember { mutableStateOf<String?>(null) }
    var dest by remember { mutableStateOf<PreviewWallet?>(null) }
    var confirmed by remember { mutableStateOf(false) }

    val options = previewWallets.filter {
        if (mode == CustodyMode.SHIP) it.type == WalletType.TRANSIT
        else it.type in setOf(WalletType.STORAGE, WalletType.INTAKE, WalletType.QUARANTINE)
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Card(colors = CardDefaults.cardColors(containerColor = AmberBg), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Not connected", fontWeight = FontWeight.SemiBold, color = Amber)
                Text(
                    "Enter the signing service address and token in Settings to ship or receive on Shadownet. " +
                        "Until then this tab is a preview: this phone holds no key, and nothing is written to the ledger.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }

        Text(
            if (mode == CustodyMode.SHIP) "Ship a tube (preview)" else "Receive a tube (preview)",
            style = MaterialTheme.typography.headlineSmall,
        )
        Text(
            if (mode == CustodyMode.SHIP)
                "The sender moves the tube into a transit wallet. The receiving site confirms it on arrival."
            else
                "Custody passes only after the receiving custodian confirms arrival.",
            style = MaterialTheme.typography.bodyMedium,
        )

        if (confirmed) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Preview only", fontWeight = FontWeight.SemiBold)
                    Text("Nothing was written to the ledger. Open Settings to connect the signing service.")
                    Button(onClick = {
                        confirmed = false
                        scanned = null
                        dest = null
                        lookupError = null
                    }) { Text("Start another preview") }
                }
            }
            return
        }

        if (mode == CustodyMode.RECEIVE) {
            Text("Inbound (synthetic preview)", style = MaterialTheme.typography.titleMedium)
            inboundPreview.forEach { tube ->
                Card(
                    Modifier.fillMaxWidth().clickable {
                        scanned = tube
                        lookupError = null
                    },
                ) {
                    Column(Modifier.padding(12.dp)) {
                        Text(tube.code, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Medium)
                        Text("From ${tube.fromSite} · ${tube.volumeUl} µL", style = MaterialTheme.typography.bodySmall)
                    }
                }
            }
        }

        CodeEntry { raw ->
            val parsed = parseScan(raw)
            val code = when (parsed) {
                is Lookup.Code -> parsed.code
                else -> raw.trim()
            }
            val known = inboundPreview.firstOrNull { it.code.equals(code, ignoreCase = true) }
            if (mode == CustodyMode.RECEIVE && known == null) {
                scanned = null
                lookupError = "In the connected app this would have to be on your inbound list. This preview only lists the synthetic tubes above."
            } else {
                scanned = known ?: PreviewTube(code, 1000, "Demo site (synthetic)")
                lookupError = null
            }
        }
        lookupError?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        val tube = scanned ?: return
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp)) {
                Text(tube.code, style = MaterialTheme.typography.titleLarge, fontFamily = FontFamily.Monospace)
                Text("${tube.volumeUl} µL (synthetic)")
            }
        }

        Text(
            if (mode == CustodyMode.SHIP) "Transit wallet (preview)" else "Receive into (preview)",
            style = MaterialTheme.typography.titleMedium,
        )
        options.forEach { wallet ->
            Row(
                Modifier.fillMaxWidth().clickable { dest = wallet }.padding(vertical = 2.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                RadioButton(selected = dest == wallet, onClick = { dest = wallet })
                Text(wallet.label)
            }
        }
        if (mode == CustodyMode.RECEIVE) {
            Text("If the tube looks wrong, receive it into quarantine.", style = MaterialTheme.typography.bodySmall)
        }

        Button(onClick = { confirmed = true }, enabled = dest != null) { Text("Review preview") }
        if (dest != null) {
            Text("${tube.code} → ${dest?.label}. Confirming still writes nothing.", style = MaterialTheme.typography.bodySmall)
        }
    }
}

@Composable
private fun CodeEntry(onCode: (String) -> Unit) {
    var code by remember { mutableStateOf("") }
    var scanning by remember { mutableStateOf(false) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { scanning = it }

    if (scanning) {
        Box(Modifier.fillMaxWidth().height(240.dp).clip(RoundedCornerShape(16.dp))) {
            ScannerView(Modifier.fillMaxSize()) { raw ->
                scanning = false
                val parsed = parseScan(raw)
                code = when (parsed) {
                    is Lookup.Code -> parsed.code
                    is Lookup.Token -> parsed.tokenId
                    else -> raw.trim()
                }
                onCode(code)
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
                label = { Text("Tube code") },
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                keyboardActions = KeyboardActions(onSearch = { onCode(code) }),
            )
            Button(onClick = { permission.launch(Manifest.permission.CAMERA) }) { Text("Scan") }
        }
    }
}
