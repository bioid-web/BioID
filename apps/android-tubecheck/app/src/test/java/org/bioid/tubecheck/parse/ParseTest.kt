package org.bioid.tubecheck.parse

import org.bioid.tubecheck.model.ChainEvent
import org.bioid.tubecheck.model.Lookup
import org.bioid.tubecheck.model.TokenRecord
import org.json.JSONObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ParseTest {

    private val fixture: JSONObject by lazy {
        val text = javaClass.classLoader!!
            .getResourceAsStream("fixtures/tube_fixture.json")!!
            .bufferedReader()
            .readText()
        JSONObject(text)
    }

    private val indexes by lazy { loadIndexes(fixture) }

    private fun token(
        id: String = "0",
        status: String = "active",
        destroyed: Boolean = false,
        code: String = "SY00000301",
    ) = TokenRecord(
        id = id,
        code = code,
        status = status,
        balanceUl = 1000,
        wallet = "tz1DemoStorage000000000000000000001",
        parentId = null,
        rootId = id,
        sampleType = "blood",
        createdBy = "collected",
        destroyed = destroyed,
    )

    private fun withdraw(root: String, outcome: String, tag: String = "WITHDRAW") = ChainEvent(
        id = 1,
        tag = tag,
        timestamp = "2026-10-19T17:28:00Z",
        payload = mapOf("root" to root, "outcome" to outcome),
        transactionId = "1005",
    )

    @Test
    fun parseScanAcceptsSyCodeAndViewerUrl() {
        assertEquals(Lookup.Code("SY00000301"), parseScan("sy00000301"))
        assertEquals(Lookup.Code("SY00000301"), parseScan("  SY00000301  "))
        assertEquals(Lookup.Code("SY00000301"), parseScan("https://example.org/bioid/app/?tube=SY00000301"))
        assertEquals(Lookup.Code("SY00000301"), parseScan("https://example.org/app/?code=SY00000301"))
        assertEquals(Lookup.Token("8"), parseScan("8"))
        assertEquals(Lookup.Token("8"), parseScan("https://example.org/app/?token=8"))
        assertEquals(Lookup.Empty, parseScan(" "))
        assertTrue(parseScan("https://example.org/app/") is Lookup.Empty || parseScan("https://example.org/app/") is Lookup.Unknown)
    }

    @Test
    fun parseScanAcceptsBareNonSyCodeForTheIndex() {
        val result = parseScan("DEMO-TUBE-01")
        assertEquals(Lookup.Code("DEMO-TUBE-01"), result)
    }

    @Test
    fun bigmapPointerReadsNumberOrObject() {
        val storage = JSONObject("""{"code_index": 40752, "tokens": {"id": 40761}, "missing": null}""")
        assertEquals("40752", bigmapPointer(storage, "code_index"))
        assertEquals("40761", bigmapPointer(storage, "tokens"))
        assertNull(bigmapPointer(storage, "missing"))
        assertNull(bigmapPointer(storage, "nope"))
        assertNull(bigmapPointer(null, "code_index"))
    }

    @Test
    fun effectiveStatusDestroyedWins() {
        val destroyed = token(status = "frozen", destroyed = true)
        assertEquals("destroyed", effectiveStatus(destroyed, "SY00000301", listOf(withdraw("SY00000301", "destroy"))))
        assertEquals("destroyed", effectiveStatus(token(status = "destroyed"), "SY00000301", emptyList()))
    }

    @Test
    fun effectiveStatusFollowsRootWithdrawal() {
        val child = token(id = "1", status = "in_transit", code = "SY00000302").copy(rootId = "0")
        val events = listOf(withdraw("SY00000301", "destroy"))
        assertEquals("frozen", effectiveStatus(child, "SY00000301", events))
        assertEquals("stopped", effectiveStatus(token(status = "active"), "SY00000303", listOf(withdraw("SY00000303", "stop_use"))))
        assertEquals("frozen", effectiveStatus(token(), "SY00000301", listOf(withdraw("SY00000301", "anonymise"))))
        assertEquals("anonymised", effectiveStatus(token(), "SY00000301", listOf(
            withdraw("SY00000301", "anonymise"),
            withdraw("SY00000301", "", tag = "UNFREEZE"),
        )))
        assertEquals("active", effectiveStatus(token(), "SY00000301", emptyList()))
        assertEquals("active", effectiveStatus(token(), "SY00000301", listOf(withdraw("SY00000999", "destroy"))))
    }

    @Test
    fun fixtureChildInheritsFrozenStatusAndParentLink() {
        val child = viewToken("1", indexes)
        assertNotNull(child)
        assertEquals("SY00000302", child!!.token.code)
        assertEquals("aliquot", child.token.sampleType)
        assertEquals("frozen", child.token.status)
        assertEquals("in_transit", indexes.tokens.getValue("1").status)
        assertEquals(listOf("SY00000301"), child.parents.map { it.code })
        assertEquals("SY00000301", child.rootCode)
        assertEquals("Courier (synthetic)", child.wallet.label)
        assertEquals("TRANSIT", child.wallet.type)
        assertEquals(500L, child.token.balanceUl)
        val tags = child.timeline.map { it.tag }
        assertTrue(tags.contains("MINT"))
        assertTrue(tags.contains("SHIP"))
        assertTrue(tags.contains("WITHDRAW"))
        assertFalse(tags.contains("TRANSFORM"))
        val ship = child.timeline.first { it.tag == "SHIP" }
        assertTrue(ship.summary.contains("shipped"))
        assertTrue(ship.summary.contains("Courier (synthetic)"))
        assertTrue(ship.explorer.contains("ooDemoShip"))
        val withdraw = child.timeline.first { it.tag == "WITHDRAW" }
        assertTrue(withdraw.summary.contains("destroy"))
        assertTrue(withdraw.summary.contains("was active"))
    }

    @Test
    fun fixtureRootShowsSampleTypeChildrenAndDataset() {
        val root = viewToken("0", indexes)!!
        assertEquals("blood", root.token.sampleType)
        assertEquals("frozen", root.token.status)
        assertEquals("Freezer A (synthetic)", root.wallet.label)
        assertEquals("STORAGE", root.wallet.type)
        assertEquals(listOf("SY00000302"), root.children.map { it.code })
        assertTrue(root.parents.isEmpty())
        assertEquals(1, root.datasets.own.size)
        assertEquals("qc", root.datasets.own[0].type)
        assertEquals("reception", root.datasets.own[0].step)
        assertTrue(root.datasets.own[0].sha256.startsWith("aaaa"))
        val tags = root.timeline.map { it.tag }
        assertTrue(tags.contains("TRANSFORM"))
        assertTrue(tags.contains("DATA_ATTACHED"))
        assertFalse(tags.contains("SHIP"))
        val transform = root.timeline.first { it.tag == "TRANSFORM" }
        assertTrue(transform.summary.contains("aliquoted"))
        assertTrue(transform.summary.contains("burned 1000"))
    }

    @Test
    fun stopUseRootIsStoppedAndDoesNotAffectOtherLineage() {
        val stopped = viewToken("2", indexes)!!
        assertEquals("stopped", stopped.token.status)
        assertEquals("SY00000303", stopped.token.code)
        assertFalse(stopped.timeline.any { it.tag == "SHIP" })
        val other = viewToken("0", indexes)!!
        assertEquals("frozen", other.token.status)
    }

    @Test
    fun humanStatusReplacesUnderscores() {
        assertEquals("in transit", humanStatus("in_transit"))
        assertEquals("stop use", humanStatus("stop_use"))
    }
}
