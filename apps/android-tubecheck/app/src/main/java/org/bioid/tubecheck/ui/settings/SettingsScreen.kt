package org.bioid.tubecheck.ui.settings

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import kotlinx.coroutines.launch
import org.bioid.tubecheck.custody.CustodyAuthException
import org.bioid.tubecheck.custody.CustodyClient
import org.bioid.tubecheck.custody.CustodyException
import org.bioid.tubecheck.settings.AppSettings
import org.bioid.tubecheck.settings.SigningSettings
import org.bioid.tubecheck.settings.normalizeSigningUrl

@Composable
fun SettingsScreen() {
    val context = LocalContext.current
    val store = remember { AppSettings(context) }
    var url by remember { mutableStateOf("") }
    var token by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val api = remember { CustodyClient() }

    LaunchedEffect(Unit) {
        val current = store.signing()
        url = current.baseUrl
        token = current.bearerToken
    }

    Column(
        Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("Signing service", style = MaterialTheme.typography.headlineSmall)
        Text(
            "Ship and receive are signed on a Shadownet-only service, not on this phone. " +
                "Enter the address and the bearer token your operator gave you. " +
                "Neither is hard-coded in the app. Leave both blank to keep the preview screens.",
            style = MaterialTheme.typography.bodyMedium,
        )
        OutlinedTextField(
            value = url,
            onValueChange = { url = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Service URL") },
            placeholder = { Text("http://127.0.0.1:8787") },
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        )
        OutlinedTextField(
            value = token,
            onValueChange = { token = it },
            modifier = Modifier.fillMaxWidth(),
            singleLine = true,
            label = { Text("Bearer token") },
            visualTransformation = PasswordVisualTransformation(),
        )
        Button(
            onClick = {
                store.saveSigning(url, token)
                message = "Saved on this phone."
                error = null
            },
        ) { Text("Save") }
        OutlinedButton(
            onClick = {
                store.saveSigning(url, token)
                val settings = SigningSettings(normalizeSigningUrl(url), token.trim())
                if (!settings.configured) {
                    error = "Enter both a URL and a token first."
                    message = null
                    return@OutlinedButton
                }
                scope.launch {
                    try {
                        val me = api.me(settings)
                        message = "Connected as ${me.name} (${me.org})."
                        error = null
                    } catch (_: CustodyAuthException) {
                        error = "The token was not accepted."
                        message = null
                    } catch (e: CustodyException) {
                        error = e.message
                        message = null
                    } catch (_: Exception) {
                        error = "Could not reach the service. Check the URL, and that this phone can open that address."
                        message = null
                    }
                }
            },
        ) { Text("Test connection") }
        message?.let { Text(it, fontWeight = FontWeight.Medium) }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error) }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("This phone cannot see 127.0.0.1 on another computer.", fontWeight = FontWeight.SemiBold)
                Text(
                    "The signing service binds to loopback on the machine that holds the testnet keys. " +
                        "A physical phone needs a path the user approves, such as an SSH tunnel, a VPN, or a temporary public tunnel. " +
                        "Do not open a public tunnel unless you mean to.",
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
        }
    }
}
