package org.bioid.tubecheck.custody

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.bioid.tubecheck.settings.SigningSettings
import org.json.JSONObject
import java.util.concurrent.TimeUnit

/** HTTP client for the Shadownet-only signing front. The phone holds no key. */
class CustodyClient(
    private val http: OkHttpClient = defaultClient(),
) {
    suspend fun me(settings: SigningSettings): StaffSession = withContext(Dispatchers.IO) {
        val (status, json) = request(settings, "GET", "/me")
        if (status == 401) throw CustodyAuthException()
        if (status != 200) throw CustodyException(json.optString("error", "Could not read the session."))
        parseSession(json)
    }

    suspend fun inbound(settings: SigningSettings): List<InboundTube> = withContext(Dispatchers.IO) {
        val (status, json) = request(settings, "GET", "/custody/inbound")
        if (status == 401) throw CustodyAuthException()
        if (status != 200) throw CustodyException(json.optString("error", "Could not load inbound tubes."))
        parseInbound(json)
    }

    suspend fun preflight(settings: SigningSettings, intent: CustodyIntent): Preflight = withContext(Dispatchers.IO) {
        val (status, json) = request(settings, "POST", "/custody/${intent.mode}/preflight", intent.toJson())
        if (status == 401) throw CustodyAuthException()
        parsePreflight(status, json)
    }

    suspend fun submit(settings: SigningSettings, intent: CustodyIntent): SubmitResult = withContext(Dispatchers.IO) {
        val (status, json) = request(settings, "POST", "/custody/${intent.mode}", intent.toJson())
        if (status == 401) throw CustodyAuthException()
        parseSubmit(status, json)
    }

    private fun request(
        settings: SigningSettings,
        method: String,
        path: String,
        body: JSONObject? = null,
    ): Pair<Int, JSONObject> {
        val url = settings.baseUrl.trimEnd('/') + path
        val builder = Request.Builder()
            .url(url)
            .header("Authorization", "Bearer ${settings.bearerToken}")
            .header("Accept", "application/json")
        if (body != null) {
            builder.method(method, body.toString().toRequestBody(JSON))
        } else if (method != "GET") {
            builder.method(method, ByteArray(0).toRequestBody(JSON))
        }
        http.newCall(builder.build()).execute().use { response ->
            val raw = response.body?.string().orEmpty()
            val json = if (raw.isBlank()) JSONObject() else try {
                JSONObject(raw)
            } catch (_: Exception) {
                JSONObject().put("error", "The signing service returned an unexpected response.")
            }
            return response.code to json
        }
    }

    companion object {
        private val JSON = "application/json; charset=utf-8".toMediaType()

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(20, TimeUnit.SECONDS)
            .build()
    }
}

open class CustodyException(message: String) : Exception(message)
class CustodyAuthException : CustodyException("The signing token was not accepted. Check Settings.")
