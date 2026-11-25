package org.bioid.tubecheck.settings

import android.content.Context

/** Signing-service settings. The URL and token are entered by the user, never hard-coded. */
data class SigningSettings(val baseUrl: String, val bearerToken: String) {
    val configured: Boolean get() = baseUrl.isNotBlank() && bearerToken.isNotBlank()
}

class AppSettings(context: Context) {
    private val prefs = context.applicationContext.getSharedPreferences("bioid_tubecheck", Context.MODE_PRIVATE)

    fun signing(): SigningSettings = SigningSettings(
        baseUrl = prefs.getString(KEY_URL, "")?.trim().orEmpty().trimEnd('/'),
        bearerToken = prefs.getString(KEY_TOKEN, "")?.trim().orEmpty(),
    )

    fun saveSigning(baseUrl: String, bearerToken: String) {
        prefs.edit()
            .putString(KEY_URL, baseUrl.trim().trimEnd('/'))
            .putString(KEY_TOKEN, bearerToken.trim())
            .apply()
    }

    companion object {
        const val KEY_URL = "signing_base_url"
        const val KEY_TOKEN = "signing_bearer"
    }
}

fun normalizeSigningUrl(raw: String): String = raw.trim().trimEnd('/')
