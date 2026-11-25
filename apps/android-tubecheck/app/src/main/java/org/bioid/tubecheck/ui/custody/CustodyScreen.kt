package org.bioid.tubecheck.ui.custody

import android.Manifest
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
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import org.bioid.tubecheck.parse.parseScan
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.ui.Amber
import org.bioid.tubecheck.ui.AmberBg
import org.bioid.tubecheck.ui.ScannerView

/**
 * Ship and receive screens are a UI preview only. There is no signing
 * backend, the app holds no keys, and nothing is written to a chain.
 */
enum class CustodyMode { SHIP, RECEIVE }

enum class WalletType { STORAGE, INTAKE, PROCESS, TRANSIT, QUARANTINE, EXTERNAL_USER }

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

@Composable
fun CustodyScreen(mode: CustodyMode) {
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
                    "Ship and receive are a screen preview only. There is no signing service yet, " +
                        "this phone holds no key, and nothing is written to the ledger. " +
                        "The planned HTTP front to the existing Python bridge is described in " +
                        "docs/android-tubecheck.md (planned).",
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
                "In the planned flow, the sender moves the tube into a transit wallet. The receiving site confirms it on arrival."
            else
                "In the planned flow, custody passes only after the receiving custodian confirms arrival.",
            style = MaterialTheme.typography.bodyMedium,
        )

        if (confirmed) {
            Card(modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text("Preview only", fontWeight = FontWeight.SemiBold)
                    Text("Nothing was written to the ledger. There is no signing backend to send this to.")
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
                lookupError = "In the real app this would have to be on your inbound list. This preview only lists the synthetic tubes above."
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
            Text("If the tube looks wrong, the planned flow receives it into quarantine.", style = MaterialTheme.typography.bodySmall)
        }

        Button(
            onClick = { confirmed = true },
            enabled = dest != null,
        ) {
            Text("Review preview")
        }
        if (dest != null) {
            Text(
                "${tube.code} → ${dest?.label}. Confirming still writes nothing.",
                style = MaterialTheme.typography.bodySmall,
            )
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
