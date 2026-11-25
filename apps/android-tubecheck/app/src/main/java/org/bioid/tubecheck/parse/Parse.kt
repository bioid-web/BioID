package org.bioid.tubecheck.parse

import org.bioid.tubecheck.BioIdConfig
import org.bioid.tubecheck.model.Attachment
import org.bioid.tubecheck.model.ChainEvent
import org.bioid.tubecheck.model.Dataset
import org.bioid.tubecheck.model.Datasets
import org.bioid.tubecheck.model.Indexes
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.model.TimelineEvent
import org.bioid.tubecheck.model.TokenRecord
import org.bioid.tubecheck.model.Transaction
import org.bioid.tubecheck.model.TubeView
import org.bioid.tubecheck.model.WalletInfo
import org.json.JSONArray
import org.json.JSONObject
import java.net.URI

/** Event labels, matching app/src/parse.js. */
val EVENT_LABELS = mapOf(
    "MINT" to "Mint",
    "MOVE" to "Move",
    "TRANSFORM" to "Transform",
    "SHIP" to "Ship",
    "RECEIVE" to "Receive",
    "CONSUME" to "Consume",
    "DATA_ATTACHED" to "Dataset attached",
    "ACCESS_REQUEST" to "Access request",
    "ACCESS_APPROVED" to "Access approval",
    "USE_REPORTED" to "Use reported",
    "ADJUST" to "Volume adjusted",
    "WITHDRAW" to "Withdrawal",
    "DESTROYED" to "Destroyed",
    "UNFREEZE" to "Unfrozen",
)

private val LINEAGE_TAGS = setOf("WITHDRAW", "UNFREEZE")

/**
 * Effective status, matching the web viewer.
 *
 * A v0.4 withdrawal is written once on the root; descendants may keep their
 * stored status. The status shown comes from the root's WITHDRAW and UNFREEZE
 * events. On the deployed v0.3 contract, stored statuses already say "frozen",
 * so the result is the same.
 */
fun effectiveStatus(token: TokenRecord, rootCode: String, events: List<ChainEvent>): String {
    if (token.destroyed || token.status == "destroyed") return "destroyed"
    var outcome: String? = null
    for (event in events) {
        val payload = event.payload
        if (payload["root"] != rootCode) continue
        if (event.tag == "WITHDRAW") payload["outcome"]?.let { outcome = it }
        if (event.tag == "UNFREEZE") outcome = "anonymised"
    }
    return when (outcome) {
        "stop_use" -> "stopped"
        "destroy", "anonymise" -> "frozen"
        "anonymised" -> "anonymised"
        else -> token.status
    }
}

fun humanStatus(status: String): String = status.replace("_", " ")

fun shortAddress(address: String?): String {
    val text = address ?: return "none"
    if (text.length < 12) return text
    return text.take(6) + "…" + text.takeLast(4)
}

/**
 * Parse a typed or scanned value. URLs use ?tube= / ?code= / ?token=, the last
 * path segment otherwise. SY######## codes and other bare codes look up
 * `code_index`. A string of digits is a token id. The SY form matches the web
 * viewer; accepting any other bare code is so a Data Matrix that is not SY-
 * prefixed still reaches the index.
 */
fun parseScan(raw: String?): Lookup {
    val text = raw?.trim().orEmpty()
    if (text.isEmpty()) return Lookup.Empty
    parseFromUrl(text)?.let { return it }
    if (SY_CODE.matches(text)) return Lookup.Code(text.uppercase())
    if (DIGITS.matches(text)) return Lookup.Token(text)
    if (!text.contains("://")) return Lookup.Code(text)
    return Lookup.Unknown(text)
}

private val SY_CODE = Regex("^SY\\d+$", RegexOption.IGNORE_CASE)
private val DIGITS = Regex("^\\d+$")

private fun parseFromUrl(text: String): Lookup? {
    val uri = try {
        URI(text)
    } catch (_: Exception) {
        return null
    }
    val scheme = uri.scheme?.lowercase() ?: return null
    if (scheme != "http" && scheme != "https") return null
    val query = parseQuery(uri.query)
    val tube = query["tube"]?.trim().orEmpty()
    if (tube.isNotEmpty()) return Lookup.Code(tube.uppercase())
    val code = query["code"]?.trim().orEmpty()
    if (code.isNotEmpty()) return Lookup.Code(if (SY_CODE.matches(code)) code.uppercase() else code)
    val token = query["token"]?.trim().orEmpty()
    if (token.isNotEmpty()) {
        return if (DIGITS.matches(token)) Lookup.Token(token) else Lookup.Unknown(token)
    }
    val segment = uri.path?.substringAfterLast('/')?.trim().orEmpty()
    return if (segment.isNotEmpty()) parseScan(segment) else Lookup.Empty
}

private fun parseQuery(query: String?): Map<String, String> {
    if (query.isNullOrEmpty()) return emptyMap()
    return query.split("&").mapNotNull { part ->
        if (part.isEmpty()) return@mapNotNull null
        val eq = part.indexOf('=')
        val key = if (eq < 0) part else part.substring(0, eq)
        val value = if (eq < 0) "" else part.substring(eq + 1)
        decode(key) to decode(value)
    }.toMap()
}

private fun decode(value: String): String = try {
    java.net.URLDecoder.decode(value, Charsets.UTF_8.name())
} catch (_: Exception) {
    value
}

fun bigmapPointer(storage: JSONObject?, name: String): String? {
    if (storage == null || !storage.has(name) || storage.isNull(name)) return null
    val value = storage.get(name)
    return when (value) {
        is Number -> value.toLong().toString()
        is String -> value
        is JSONObject -> if (value.has("id") && !value.isNull("id")) value.get("id").toString() else null
        else -> null
    }
}

fun describeWallet(address: String?, registry: Map<String, WalletInfo>): WalletInfo {
    val row = address?.let { registry[it] }
    return WalletInfo(
        address = address.orEmpty(),
        label = row?.label ?: address?.let { shortAddress(it) } ?: "Unknown wallet",
        type = row?.type.orEmpty(),
        site = row?.site.orEmpty(),
        process = row?.process.orEmpty(),
        active = row?.active ?: false,
        known = row != null,
    )
}

fun eventTouches(event: ChainEvent, token: TokenRecord, rootCode: String): Boolean {
    val payload = event.payload
    if (payload["token_id"] != null && payload["token_id"] == token.id) return true
    if (payload["code"] != null && payload["code"] == token.code) return true
    if (event.tag in LINEAGE_TAGS && payload["root"] != null && payload["root"] == rootCode) return true
    return false
}

fun summarizeEvent(event: ChainEvent, wallets: Map<String, WalletInfo>): String {
    val payload = event.payload
    val parts = mutableListOf<String>()
    payload["reason"]?.let { parts += it.replace("-", " ") }
    payload["outcome"]?.let { parts += it.replace("_", " ") }
    payload["volume"]?.let { parts += "$it µL" }
    payload["amount"]?.let { parts += "$it µL" }
    payload["burned"]?.let { parts += "burned $it µL" }
    payload["added"]?.let { if (it.isNotEmpty()) parts += "added $it µL" }
    if (event.tag == "WITHDRAW") payload["previous"]?.let { parts += "was ${it.replace("_", " ")}" }
    payload["balance"]?.let { parts += "balance $it µL" }
    payload["to_"]?.let { parts += "to ${walletName(it, wallets)}" }
    if (event.tag == "MINT") payload["parent"]?.let { parts += "from $it" }
    if (event.tag == "DATA_ATTACHED") {
        payload["data_type"]?.let { parts += it }
        payload["step"]?.let { parts += it }
    }
    if (event.tag == "ACCESS_REQUEST" || event.tag == "ACCESS_APPROVED") {
        payload["request_id"]?.let { parts += "request $it" }
    }
    return parts.joinToString(" · ")
}

private fun walletName(address: String, wallets: Map<String, WalletInfo>): String =
    wallets[address]?.label ?: shortAddress(address)

fun timelineFor(
    token: TokenRecord,
    rootCode: String,
    events: List<ChainEvent>,
    transactions: Map<String, Transaction>,
    wallets: Map<String, WalletInfo>,
    explorer: String,
): List<TimelineEvent> {
    val rows = events.filter { eventTouches(it, token, rootCode) }.map { event ->
        val hash = event.transactionId?.let { transactions[it]?.hash }.orEmpty()
        val base = explorer.trimEnd('/')
        TimelineEvent(
            id = event.id,
            tag = event.tag,
            label = EVENT_LABELS[event.tag] ?: event.tag,
            timestamp = event.timestamp,
            summary = summarizeEvent(event, wallets),
            hash = hash,
            explorer = if (hash.isNotEmpty() && base.isNotEmpty()) "$base/$hash" else "",
        )
    }
    return rows.sortedWith(compareBy<TimelineEvent> { it.timestamp }.thenBy { it.id })
}

fun viewToken(tokenId: String, indexes: Indexes): TubeView? {
    val token = indexes.tokens[tokenId] ?: return null
    val parents = mutableListOf<TokenRecord>()
    val seen = mutableSetOf(token.id)
    var cursor = token.parentId
    var depth = 0
    while (cursor != null && cursor !in seen && depth < BioIdConfig.MAX_GENERATIONS) {
        seen += cursor
        val parent = indexes.tokens[cursor] ?: break
        parents += parent
        cursor = parent.parentId
        depth += 1
    }
    val children = indexes.tokens.values
        .filter { it.parentId == token.id }
        .sortedBy { it.id.toLongOrNull() ?: 0L }
    val rootRow = indexes.tokens[token.rootId]
    val rootCode = rootRow?.code ?: token.code
    val effective = token.copy(status = effectiveStatus(token, rootCode, indexes.events))
    return TubeView(
        token = effective,
        wallet = describeWallet(token.wallet, indexes.wallets),
        parents = parents,
        children = children,
        rootCode = rootCode,
        datasets = datasetsFor(token, parents, indexes.attachments),
        timeline = timelineFor(
            effective,
            rootCode,
            indexes.events,
            indexes.transactions,
            indexes.wallets,
            indexes.explorer,
        ),
    )
}

fun datasetsFor(
    token: TokenRecord,
    parents: List<TokenRecord>,
    attachments: Map<String, List<Attachment>>,
): Datasets {
    val own = (attachments[token.id] ?: emptyList()).map { asDataset(it, inherited = false, token.id, token.code) }
    val inherited = parents.flatMap { ancestor ->
        (attachments[ancestor.id] ?: emptyList()).map {
            asDataset(it, inherited = true, ancestor.id, ancestor.code)
        }
    }
    return Datasets(own = own, inherited = inherited)
}

private fun asDataset(item: Attachment, inherited: Boolean, fromId: String, fromCode: String) = Dataset(
    uri = item.uri,
    type = item.type,
    step = item.step,
    sha256 = item.sha256,
    licence = item.licence,
    inherited = inherited,
    fromId = fromId,
    fromCode = fromCode,
)

fun statusKind(status: String): StatusKind = when (status) {
    "frozen", "stopped", "destroyed", "anonymised" -> StatusKind.WITHDRAWN
    "in_transit" -> StatusKind.TRANSIT
    "in_process" -> StatusKind.PROCESS
    else -> StatusKind.OK
}

enum class StatusKind { OK, TRANSIT, PROCESS, WITHDRAWN }

/** Flatten a TzKT or fixture JSON object into string fields (nulls dropped). */
fun stringMap(obj: JSONObject?): Map<String, String?> {
    if (obj == null) return emptyMap()
    val out = mutableMapOf<String, String?>()
    val keys = obj.keys()
    while (keys.hasNext()) {
        val key = keys.next()
        if (obj.isNull(key)) {
            out[key] = null
            continue
        }
        val value = obj.get(key)
        out[key] = when (value) {
            is JSONObject, is JSONArray -> value.toString()
            else -> value.toString()
        }
    }
    return out
}

fun longOrZero(value: Any?): Long = when (value) {
    null, JSONObject.NULL -> 0L
    is Number -> value.toLong()
    is String -> value.toLongOrNull() ?: 0L
    else -> value.toString().toLongOrNull() ?: 0L
}

fun optionalId(value: Any?): String? = when (value) {
    null, JSONObject.NULL, "" -> null
    else -> value.toString()
}

fun tokenFromValue(id: String, value: JSONObject): TokenRecord {
    val parent = optionalId(if (value.has("parent_id")) value.get("parent_id") else null)
    val root = optionalId(if (value.has("root_id")) value.get("root_id") else null) ?: id
    return TokenRecord(
        id = id,
        code = value.optString("code"),
        status = value.optString("status"),
        balanceUl = longOrZero(if (value.has("balance")) value.get("balance") else null),
        wallet = value.optString("wallet"),
        parentId = parent,
        rootId = root,
        sampleType = value.optString("sample_type"),
        createdBy = value.optString("created_by"),
        destroyed = value.optBoolean("destroyed", false),
    )
}

fun walletFromValue(address: String, value: JSONObject): WalletInfo = WalletInfo(
    address = address,
    label = value.optString("label").ifBlank { shortAddress(address) },
    type = value.optString("type"),
    site = value.optString("site"),
    process = value.optString("process"),
    active = value.optBoolean("active", true),
    known = true,
)

fun attachmentFromValue(value: JSONObject): Attachment = Attachment(
    uri = value.optString("data_uri"),
    type = value.optString("data_type"),
    step = value.optString("step"),
    sha256 = value.optString("content_hash"),
    licence = value.optString("licence"),
)

fun eventFromJson(obj: JSONObject): ChainEvent = ChainEvent(
    id = longOrZero(if (obj.has("id")) obj.get("id") else null),
    tag = obj.optString("tag"),
    timestamp = obj.optString("timestamp"),
    payload = stringMap(obj.optJSONObject("payload")),
    transactionId = optionalId(if (obj.has("transactionId")) obj.get("transactionId") else null),
)

fun transactionFromJson(obj: JSONObject): Transaction = Transaction(
    id = obj.get("id").toString(),
    hash = obj.optString("hash"),
    timestamp = obj.optString("timestamp"),
)

/**
 * Build indexes from a fixture or from the rows a per-tube TzKT read returns.
 * Inactive bigmap keys are skipped, as in the web viewer.
 */
fun loadIndexes(fixture: JSONObject, explorer: String = fixture.optString("explorer")): Indexes {
    return Indexes(
        codeIndex = indexScalar(fixture.optJSONArray("codeIndex") ?: fixture.optJSONArray("code_index")),
        tokens = indexTokens(fixture.optJSONArray("tokens")),
        wallets = indexWallets(fixture.optJSONArray("wallets")),
        attachments = indexAttachments(fixture.optJSONArray("attachments")),
        transactions = indexTransactions(fixture.optJSONArray("transactions")),
        events = jsonArrayOrEmpty(fixture.optJSONArray("events")).map { eventFromJson(it) },
        explorer = explorer,
    )
}

fun indexScalar(rows: JSONArray?): Map<String, String> {
    val map = mutableMapOf<String, String>()
    for (row in jsonArrayOrEmpty(rows)) {
        if (!row.optBoolean("active", true)) continue
        if (!row.has("key") || row.isNull("key") || !row.has("value") || row.isNull("value")) continue
        map[row.get("key").toString()] = row.get("value").toString()
    }
    return map
}

fun indexTokens(rows: JSONArray?): Map<String, TokenRecord> {
    val map = mutableMapOf<String, TokenRecord>()
    for (row in jsonArrayOrEmpty(rows)) {
        if (!row.optBoolean("active", true)) continue
        val id = row.get("key").toString()
        val value = row.optJSONObject("value") ?: continue
        map[id] = tokenFromValue(id, value)
    }
    return map
}

fun indexWallets(rows: JSONArray?): Map<String, WalletInfo> {
    val map = mutableMapOf<String, WalletInfo>()
    for (row in jsonArrayOrEmpty(rows)) {
        if (!row.optBoolean("active", true)) continue
        val address = row.get("key").toString()
        val value = row.optJSONObject("value") ?: continue
        map[address] = walletFromValue(address, value)
    }
    return map
}

fun indexAttachments(rows: JSONArray?): Map<String, List<Attachment>> {
    val map = mutableMapOf<String, List<Attachment>>()
    for (row in jsonArrayOrEmpty(rows)) {
        if (!row.optBoolean("active", true)) continue
        val id = row.get("key").toString()
        val value = row.opt("value")
        val list = when (value) {
            is JSONArray -> (0 until value.length()).mapNotNull { i ->
                value.optJSONObject(i)?.let { attachmentFromValue(it) }
            }
            else -> emptyList()
        }
        map[id] = list
    }
    return map
}

fun indexTransactions(rows: JSONArray?): Map<String, Transaction> {
    val map = mutableMapOf<String, Transaction>()
    for (row in jsonArrayOrEmpty(rows)) {
        if (!row.has("id") || row.isNull("id")) continue
        val tx = transactionFromJson(row)
        map[tx.id] = tx
    }
    return map
}

fun jsonArrayOrEmpty(arr: JSONArray?): List<JSONObject> {
    if (arr == null) return emptyList()
    return (0 until arr.length()).mapNotNull { arr.optJSONObject(it) }
}
