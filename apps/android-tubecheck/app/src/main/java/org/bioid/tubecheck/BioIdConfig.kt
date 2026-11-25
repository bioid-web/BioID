package org.bioid.tubecheck

import org.bioid.tubecheck.model.Network

/** Network and contract settings for the Tube Check prototype. */
object BioIdConfig {
    const val MAX_GENERATIONS = 8

    /** Shadownet custody prototype originated for this work (synthetic data). */
    val SHADOWNET = Network(
        id = "shadownet",
        label = "Shadownet",
        api = "https://api.shadownet.tzkt.io/v1",
        explorer = "https://shadownet.tzkt.io",
        contract = "KT1B2i1w9CjbcUHrGJSPqYRmFiLJa8pXneJ5",
        trial = true,
        caption = "Shadownet custody prototype, synthetic data",
    )

    /** Earlier public Shadownet demo. Read-only; not used by the signing service. */
    val SHADOWNET_PUBLIC_DEMO = Network(
        id = "shadownet-demo",
        label = "Shadownet public demo",
        api = "https://api.shadownet.tzkt.io/v1",
        explorer = "https://shadownet.tzkt.io",
        contract = "KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix",
        trial = true,
        caption = "Shadownet public demo, synthetic data (read-only)",
    )

    /**
     * Public mainnet trial contract (synthetic data). Opt-in only. The
     * signing service refuses mainnet and will not send operations here.
     */
    val MAINNET_TRIAL = Network(
        id = "mainnet",
        label = "Mainnet trial",
        api = "https://api.tzkt.io/v1",
        explorer = "https://tzkt.io",
        contract = "KT1DgrZrWrdTjf7sENXVctihhpDHfU4RTpdy",
        trial = true,
        caption = "Mainnet trial contract, synthetic data (opt-in, verify only)",
    )

    val DEFAULT: Network = SHADOWNET
    val NETWORKS: List<Network> = listOf(SHADOWNET, SHADOWNET_PUBLIC_DEMO, MAINNET_TRIAL)
}
