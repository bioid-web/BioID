package org.bioid.tubecheck

import org.bioid.tubecheck.model.Network

/** Network and contract settings for the Tube Check prototype. */
object BioIdConfig {
    const val MAX_GENERATIONS = 8

    val SHADOWNET = Network(
        id = "shadownet",
        label = "Shadownet",
        api = "https://api.shadownet.tzkt.io/v1",
        explorer = "https://shadownet.tzkt.io",
        contract = "KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix",
        trial = true,
        caption = "Shadownet testnet demo, synthetic data",
    )

    /**
     * Public mainnet trial contract (synthetic data). Opt-in only; Shadownet
     * is the default, matching the web viewer.
     */
    val MAINNET_TRIAL = Network(
        id = "mainnet",
        label = "Mainnet trial",
        api = "https://api.tzkt.io/v1",
        explorer = "https://tzkt.io",
        contract = "KT1DgrZrWrdTjf7sENXVctihhpDHfU4RTpdy",
        trial = true,
        caption = "Mainnet trial contract, synthetic data (opt-in)",
    )

    val DEFAULT: Network = SHADOWNET
    val NETWORKS: List<Network> = listOf(SHADOWNET, MAINNET_TRIAL)
}
