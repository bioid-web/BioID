package org.bioid.tubecheck.tzkt

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.bioid.tubecheck.BioIdConfig
import org.bioid.tubecheck.model.Indexes
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.model.Network
import org.bioid.tubecheck.model.TubeView
import org.bioid.tubecheck.parse.bigmapPointer
import org.bioid.tubecheck.parse.jsonArrayOrEmpty
import org.bioid.tubecheck.parse.loadIndexes
import org.bioid.tubecheck.parse.viewToken
import org.json.JSONArray
import org.json.JSONObject
import java.io.IOException
import java.net.URLEncoder
import java.nio.charset.StandardCharsets
import java.util.concurrent.TimeUnit

/**
 * Per-tube TzKT reads, matching app/src/tzkt.js.
 *
 * A lookup asks only for that tube: code_index, the tokens row, ancestors
 * (at most eight generations), children, attachments, wallet_registry rows,
 * and contract events that name the tube or its root. It does not use
 * /tokens/transfers or a parents big map.
 */
class TzktClient(
    private val http: OkHttpClient = defaultClient(),
) {
    suspend fun loadTube(network: Network, lookup: Lookup): TubeResult = withContext(Dispatchers.IO) {
        if (network.contract.isBlank()) {
            return@withContext TubeResult.Failed("No contract is configured for this network.")
        }
        when (lookup) {
            is Lookup.Empty -> TubeResult.Empty
            is Lookup.Unknown -> TubeResult.Invalid(lookup.raw)
            is Lookup.Code, is Lookup.Token -> try {
                val view = fetchView(network, lookup)
                if (view == null) TubeResult.NotFound(lookup) else TubeResult.Found(view)
            } catch (e: Exception) {
                TubeResult.Failed("Could not reach the indexer. Check your connection and try again.")
            }
        }
    }

    private suspend fun fetchView(network: Network, lookup: Lookup): TubeView? {
        val api = network.api.trimEnd('/')
        val storage = getJson("$api/contracts/${network.contract}/storage")
            ?: throw IOException("No contract storage")
        fun pointer(name: String): String {
            return bigmapPointer(storage, name)
                ?: throw IOException("Contract storage has no $name bigmap")
        }
        val codeIndexPtr = pointer("code_index")
        val tokensPtr = pointer("tokens")

        var tokenId: String? = null
        val codeIndexRows = JSONArray()
        when (lookup) {
            is Lookup.Code -> {
                val row = getJson("$api/bigmaps/$codeIndexPtr/keys/${enc(lookup.code)}")
                if (row == null || !row.optBoolean("active", true)) return null
                codeIndexRows.put(row)
                tokenId = row.get("value").toString()
            }
            is Lookup.Token -> tokenId = lookup.tokenId
            else -> return null
        }
        val id = tokenId ?: return null

        val self = getJson("$api/bigmaps/$tokensPtr/keys/${enc(id)}")
        if (self == null || !self.optBoolean("active", true)) return null
        val tokens = JSONArray().put(self)

        val ancestors = mutableListOf<JSONObject>()
        val seen = mutableSetOf(id)
        var cursor = optionalParent(self)
        while (cursor != null && cursor !in seen && ancestors.size < BioIdConfig.MAX_GENERATIONS) {
            seen += cursor
            val row = getJson("$api/bigmaps/$tokensPtr/keys/${enc(cursor)}") ?: break
            tokens.put(row)
            ancestors.add(row)
            cursor = optionalParent(row)
        }
        val children = getList("$api/bigmaps/$tokensPtr/keys?active=true&value.parent_id=${enc(id)}&limit=1000")
        for (child in children) tokens.put(child)

        val selfValue = self.optJSONObject("value") ?: JSONObject()
        val rootId = optionalId(selfValue, "root_id") ?: id
        val rootAlready = (0 until tokens.length()).any { tokens.getJSONObject(it).get("key").toString() == rootId }
        val rootRow = if (rootAlready) {
            (0 until tokens.length()).map { tokens.getJSONObject(it) }.first { it.get("key").toString() == rootId }
        } else {
            getJson("$api/bigmaps/$tokensPtr/keys/${enc(rootId)}")?.also { tokens.put(it) }
        }
        val code = selfValue.optString("code")
        val rootCode = rootRow?.optJSONObject("value")?.optString("code")?.ifBlank { null } ?: code

        val lineageIds = listOf(id) + ancestors.map { it.get("key").toString() }
        val attachPtr = pointer("attachments")
        val walletPtr = pointer("wallet_registry")
        val addresses = linkedSetOf<String>()
        for (i in 0 until tokens.length()) {
            val wallet = tokens.getJSONObject(i).optJSONObject("value")?.optString("wallet").orEmpty()
            if (wallet.isNotEmpty()) addresses += wallet
        }
        val attachRows = JSONArray()
        val walletRows = JSONArray()
        val byId = getList("$api/contracts/events?contract=${network.contract}&payload.token_id=${enc(id)}&sort.asc=id&limit=1000")
        val byCode = if (code.isNotEmpty()) {
            getList("$api/contracts/events?contract=${network.contract}&payload.code=${enc(code)}&sort.asc=id&limit=1000")
        } else emptyList()
        val byRoot = if (rootCode.isNotEmpty()) {
            getList("$api/contracts/events?contract=${network.contract}&payload.root=${enc(rootCode)}&sort.asc=id&limit=1000")
        } else emptyList()
        for (lineageId in lineageIds) {
            getJson("$api/bigmaps/$attachPtr/keys/${enc(lineageId)}")?.let { attachRows.put(it) }
        }
        for (address in addresses) {
            getJson("$api/bigmaps/$walletPtr/keys/${enc(address)}")?.let { walletRows.put(it) }
        }

        val events = LinkedHashMap<Long, JSONObject>()
        for (event in byId + byCode + byRoot) {
            val eventId = event.optLong("id", -1L)
            if (eventId >= 0) events[eventId] = event
        }
        val eventList = events.values.sortedBy { it.optLong("id") }

        val fetched = addresses.toMutableSet()
        for (event in eventList) {
            val to = event.optJSONObject("payload")?.optString("to_").orEmpty()
            if (to.isNotEmpty() && to !in fetched) {
                fetched += to
                getJson("$api/bigmaps/$walletPtr/keys/${enc(to)}")?.let { walletRows.put(it) }
            }
        }

        val txIds = eventList.mapNotNull { optionalId(it, "transactionId") }.distinct()
        val transactions = JSONArray()
        for (chunk in txIds.chunked(50)) {
            val joined = chunk.joinToString(",")
            for (tx in getList("$api/operations/transactions?id.in=$joined&select=id,hash,timestamp&limit=50")) {
                transactions.put(tx)
            }
        }

        val fixture = JSONObject()
            .put("codeIndex", codeIndexRows)
            .put("tokens", tokens)
            .put("wallets", walletRows)
            .put("attachments", attachRows)
            .put("events", JSONArray(eventList))
            .put("transactions", transactions)
            .put("explorer", network.explorer)
        val indexes: Indexes = loadIndexes(fixture, network.explorer)
        return viewToken(id, indexes)
    }

    /** GET with retry and backoff: retry network failures, timeouts, 429 and 5xx. A 404 or other 4xx is a real answer. 204 is a missing bigmap key. */
    internal suspend fun getJson(url: String, attempts: Int = 4): JSONObject? {
        var last: Exception? = null
        var delayMs = 400L
        repeat(attempts) { i ->
            try {
                http.newCall(Request.Builder().url(url).build()).execute().use { response ->
                    if (response.code == 204) return null
                    if (response.isSuccessful) {
                        val body = response.body?.string().orEmpty()
                        if (body.isBlank()) return null
                        return JSONObject(body)
                    }
                    val error = HttpStatusException(response.code, "HTTP ${response.code}")
                    if (response.code !in RETRYABLE) throw error
                    last = error
                }
            } catch (e: HttpStatusException) {
                if (e.code !in RETRYABLE) throw e
                last = e
            } catch (e: IOException) {
                last = e
            }
            if (i < attempts - 1) {
                delay(delayMs)
                delayMs *= 2
            }
        }
        throw last ?: IOException("Request failed")
    }

    private suspend fun getList(url: String): List<JSONObject> {
        val raw = getRaw(url) ?: return emptyList()
        if (raw.isBlank() || raw == "null") return emptyList()
        val arr = JSONArray(raw)
        return jsonArrayOrEmpty(arr)
    }

    private suspend fun getRaw(url: String, attempts: Int = 4): String? {
        var last: Exception? = null
        var delayMs = 400L
        repeat(attempts) { i ->
            try {
                http.newCall(Request.Builder().url(url).build()).execute().use { response ->
                    if (response.code == 204) return null
                    if (response.isSuccessful) return response.body?.string().orEmpty()
                    val error = HttpStatusException(response.code, "HTTP ${response.code}")
                    if (response.code !in RETRYABLE) throw error
                    last = error
                }
            } catch (e: HttpStatusException) {
                if (e.code !in RETRYABLE) throw e
                last = e
            } catch (e: IOException) {
                last = e
            }
            if (i < attempts - 1) {
                delay(delayMs)
                delayMs *= 2
            }
        }
        throw last ?: IOException("Request failed")
    }

    private fun optionalParent(row: JSONObject): String? {
        val value = row.optJSONObject("value") ?: return null
        return optionalId(value, "parent_id")
    }

    private fun optionalId(obj: JSONObject, key: String): String? {
        if (!obj.has(key) || obj.isNull(key)) return null
        val text = obj.get(key).toString()
        return text.ifBlank { null }
    }

    private fun enc(value: String): String = URLEncoder.encode(value, StandardCharsets.UTF_8.name())

    companion object {
        private val RETRYABLE = setOf(408, 425, 429, 500, 502, 503, 504)

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .build()
    }
}

class HttpStatusException(val code: Int, message: String) : IOException(message)

sealed class TubeResult {
    data object Empty : TubeResult()
    data class Invalid(val raw: String) : TubeResult()
    data class NotFound(val lookup: Lookup) : TubeResult()
    data class Found(val tube: TubeView) : TubeResult()
    data class Failed(val message: String) : TubeResult()
}
