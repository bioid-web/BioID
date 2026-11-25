package org.bioid.tubecheck.custody

import org.json.JSONArray
import org.json.JSONObject

enum class WalletType { STORAGE, INTAKE, PROCESS, TRANSIT, QUARANTINE, EXTERNAL_USER, UNKNOWN }

data class WalletOption(val address: String, val label: String, val type: WalletType, val site: String)

data class StaffSession(
    val name: String,
    val org: String,
    val wallets: List<WalletOption>,
    val shipDestinations: List<WalletOption>,
    val receiveDestinations: List<WalletOption>,
)

data class InboundTube(
    val tokenId: Long,
    val code: String,
    val fromSite: String,
    val volumeUl: Long,
)

data class CustodyIntent(
    val clientRequestId: String,
    val mode: String,
    val tokenId: Long?,
    val tubeCode: String,
    val toWallet: String,
    val registeredVia: String?,
) {
    fun toJson(): JSONObject = JSONObject()
        .put("client_request_id", clientRequestId)
        .put("tube_code", tubeCode)
        .put("to_wallet", toWallet)
        .apply {
            if (tokenId != null) put("token_id", tokenId)
            if (!registeredVia.isNullOrBlank()) put("registered_via", registeredVia)
        }
}

data class Preflight(val ok: Boolean, val feeMutez: Long, val problems: List<String>)

sealed interface SubmitResult {
    data class Injected(val opHash: String) : SubmitResult
    data class Review(val reasons: List<String>) : SubmitResult
    data class Failed(val message: String, val retryable: Boolean) : SubmitResult
}

fun parseWalletType(raw: String?): WalletType = try {
    WalletType.valueOf((raw ?: "").uppercase())
} catch (_: Exception) {
    WalletType.UNKNOWN
}

fun parseWallets(array: JSONArray): List<WalletOption> =
    (0 until array.length()).map { i ->
        val w = array.getJSONObject(i)
        WalletOption(
            address = w.getString("address"),
            label = w.optString("label"),
            type = parseWalletType(w.optString("type")),
            site = w.optString("site"),
        )
    }

fun parseSession(json: JSONObject): StaffSession {
    return StaffSession(
        name = json.optString("name"),
        org = json.optString("org"),
        wallets = parseWallets(json.optJSONArray("wallets") ?: JSONArray()),
        shipDestinations = parseWallets(json.optJSONArray("ship_destinations") ?: JSONArray()),
        receiveDestinations = parseWallets(json.optJSONArray("receive_destinations") ?: JSONArray()),
    )
}

fun parseInbound(json: JSONObject): List<InboundTube> {
    val tubes = json.optJSONArray("tubes") ?: JSONArray()
    return (0 until tubes.length()).map { i ->
        val t = tubes.getJSONObject(i)
        InboundTube(
            tokenId = t.optLong("token_id"),
            code = t.optString("tube_code"),
            fromSite = t.optString("from_site"),
            volumeUl = t.optLong("volume_ul"),
        )
    }
}

fun parsePreflight(httpStatus: Int, json: JSONObject): Preflight {
    val problems = json.strings("problems")
    val ok = httpStatus == 200 && json.optBoolean("ok") && problems.isEmpty()
    return Preflight(ok, json.optLong("fee_mutez"), problems)
}

fun parseSubmit(httpStatus: Int, json: JSONObject): SubmitResult = when (httpStatus) {
    200 -> SubmitResult.Injected(json.getString("op_hash"))
    202 -> SubmitResult.Review(json.strings("reasons"))
    in 400..499 -> SubmitResult.Failed(json.optString("error", "The service refused this request."), false)
    else -> SubmitResult.Failed("The signing service had a problem.", true)
}

fun JSONObject.strings(key: String): List<String> =
    optJSONArray(key)?.let { a -> (0 until a.length()).map { a.getString(it) } } ?: emptyList()
