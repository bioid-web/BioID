package org.bioid.tubecheck.model

/** A read-only Tezos network + contract the app can query through TzKT. */
data class Network(
    val id: String,
    val label: String,
    val api: String,
    val explorer: String,
    val contract: String,
    val trial: Boolean,
    val caption: String,
)

sealed class Lookup {
    data object Empty : Lookup()
    data class Code(val code: String) : Lookup()
    data class Token(val tokenId: String) : Lookup()
    data class Unknown(val raw: String) : Lookup()
}

data class TokenRecord(
    val id: String,
    val code: String,
    val status: String,
    val balanceUl: Long,
    val wallet: String,
    val parentId: String?,
    val rootId: String,
    val sampleType: String,
    val createdBy: String,
    val destroyed: Boolean,
) {
    val isEmpty: Boolean get() = balanceUl == 0L
}

data class WalletInfo(
    val address: String,
    val label: String,
    val type: String,
    val site: String,
    val process: String,
    val active: Boolean,
    val known: Boolean,
)

data class ChainEvent(
    val id: Long,
    val tag: String,
    val timestamp: String,
    val payload: Map<String, String?>,
    val transactionId: String?,
)

data class Transaction(
    val id: String,
    val hash: String,
    val timestamp: String,
)

data class Attachment(
    val uri: String,
    val type: String,
    val step: String,
    val sha256: String,
    val licence: String,
)

data class Dataset(
    val uri: String,
    val type: String,
    val step: String,
    val sha256: String,
    val licence: String,
    val inherited: Boolean,
    val fromId: String,
    val fromCode: String,
)

data class Datasets(
    val own: List<Dataset>,
    val inherited: List<Dataset>,
)

data class TimelineEvent(
    val id: Long,
    val tag: String,
    val label: String,
    val timestamp: String,
    val summary: String,
    val hash: String,
    val explorer: String,
)

data class Indexes(
    val codeIndex: Map<String, String>,
    val tokens: Map<String, TokenRecord>,
    val wallets: Map<String, WalletInfo>,
    val attachments: Map<String, List<Attachment>>,
    val transactions: Map<String, Transaction>,
    val events: List<ChainEvent>,
    val explorer: String,
)

data class TubeView(
    val token: TokenRecord,
    val wallet: WalletInfo,
    val parents: List<TokenRecord>,
    val children: List<TokenRecord>,
    val rootCode: String,
    val datasets: Datasets,
    val timeline: List<TimelineEvent>,
)
