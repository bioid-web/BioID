package org.bioid.tubecheck.custody

import org.bioid.tubecheck.BioIdConfig
import org.bioid.tubecheck.settings.normalizeSigningUrl
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CustodyApiTest {
    @Test
    fun defaultNetworkIsShadownetCustodyPrototype() {
        assertEquals("shadownet", BioIdConfig.DEFAULT.id)
        assertEquals("KT1B2i1w9CjbcUHrGJSPqYRmFiLJa8pXneJ5", BioIdConfig.DEFAULT.contract)
        assertEquals("KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix", BioIdConfig.SHADOWNET_PUBLIC_DEMO.contract)
        assertTrue(BioIdConfig.NETWORKS.contains(BioIdConfig.SHADOWNET_PUBLIC_DEMO))
    }

    @Test
    fun intentJsonIsStable() {
        val json = CustodyIntent(
            clientRequestId = "req-1",
            mode = "ship",
            tokenId = 1,
            tubeCode = "SY00000401",
            toWallet = "tz1ew1YTaVQpQv9M2Pj2cgj729z8QqFzJCWT",
            registeredVia = "android-tubecheck",
        ).toJson()
        assertEquals("req-1", json.getString("client_request_id"))
        assertEquals("SY00000401", json.getString("tube_code"))
        assertEquals("tz1ew1YTaVQpQv9M2Pj2cgj729z8QqFzJCWT", json.getString("to_wallet"))
        assertEquals(1, json.getLong("token_id"))
        assertEquals("android-tubecheck", json.getString("registered_via"))
        assertFalse(json.has("mode"))
    }

    @Test
    fun parseSessionReadsDestinations() {
        val json = JSONObject(
            """
            {
              "name": "Field operator (synthetic)",
              "org": "Demo field site",
              "wallets": [{"address":"tz1TCvD465fjpgL7T6dG1nWqxUQntCUipG3F","label":"Field intake (synthetic)","type":"INTAKE","site":"field"}],
              "ship_destinations": [{"address":"tz1ew1YTaVQpQv9M2Pj2cgj729z8QqFzJCWT","label":"Courier (synthetic)","type":"TRANSIT","site":"courier"}],
              "receive_destinations": []
            }
            """.trimIndent(),
        )
        val session = parseSession(json)
        assertEquals("Field operator (synthetic)", session.name)
        assertEquals(WalletType.INTAKE, session.wallets[0].type)
        assertEquals(WalletType.TRANSIT, session.shipDestinations[0].type)
        assertTrue(session.receiveDestinations.isEmpty())
    }

    @Test
    fun parseSubmitAndPreflight() {
        val injected = parseSubmit(200, JSONObject("""{"op_hash":"ooSyntheticHash"}"""))
        assertTrue(injected is SubmitResult.Injected)
        assertEquals("ooSyntheticHash", (injected as SubmitResult.Injected).opHash)

        val review = parseSubmit(202, JSONObject("""{"reasons":["The destination wallet is not in the registry."]}"""))
        assertTrue(review is SubmitResult.Review)
        assertEquals(1, (review as SubmitResult.Review).reasons.size)

        val failed = parseSubmit(400, JSONObject("""{"error":"client_request_id, tube_code and to_wallet are required."}"""))
        assertTrue(failed is SubmitResult.Failed)
        assertFalse((failed as SubmitResult.Failed).retryable)

        val pre = parsePreflight(200, JSONObject("""{"ok":true,"fee_mutez":1500,"problems":[]}"""))
        assertTrue(pre.ok)
        assertEquals(1500, pre.feeMutez)
    }

    @Test
    fun signingUrlIsTrimmed() {
        assertEquals("http://127.0.0.1:8787", normalizeSigningUrl(" http://127.0.0.1:8787/ "))
    }
}
