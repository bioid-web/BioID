# BioID Tube Check (Android prototype)

A native Android prototype that scans a tube's Data Matrix or QR code, or takes a typed code, and reads the public custody record through TzKT. It is a companion to the supported [web phone viewer](../../app/README.md), not a replacement.

**Status: untested prototype.** Verify mode talks to the public indexer. Ship and receive can be signed on Shadownet through a local HTTP service when a URL and bearer token are entered in Settings; the phone holds no key. Without those settings the tabs stay a labelled preview. All examples are synthetic.

The first screen layouts started from an AI-assisted draft. The lookup, data model and timeline were then rewritten to match the web viewer in `app/`.

## What works

- **Verify (read-only).** Looks up a tube the same way the web viewer does: `code_index`, the `tokens` and `wallet_registry` big maps, attachments, and **contract events** (`MINT`, `SHIP`, `RECEIVE`, `MOVE`, `TRANSFORM`, `WITHDRAW`, and the rest). The status shown is the effective one, including a withdrawal written on the root. Parent and child links come from `parent_id` on the token. The sample type comes from the token row (the same field as token metadata).
- **Network.** The default is the Shadownet custody prototype (`KT1B2i1w9CjbcUHrGJSPqYRmFiLJa8pXneJ5`). The earlier public demo (`KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix`) stays selectable. The mainnet trial contract `KT1DgrZrWrdTjf7sENXVctihhpDHfU4RTpdy` is an explicit opt-in; it also holds only synthetic data. The signing service refuses mainnet.
- **Ship / Receive tabs.** When Settings hold a signing URL and bearer token, the app calls the Shadownet-only HTTP front and shows the operation hash. Until then the tabs are a labelled preview.
- **Settings.** The service base URL and bearer token are entered on the phone and stored in app preferences. They are not hard-coded. A physical phone cannot reach `127.0.0.1` on another computer; a tunnel or VPN is needed, and only with the operator's approval.

The signing HTTP front (a thin layer over the existing Python bridge, still with no keys on the phone) is described in [docs/android-tubecheck.md](../../docs/android-tubecheck.md).

## Build

You need JDK 17 or 21 and the Android SDK (platform 35, build-tools 35). From this directory:

```bash
# optional, if the SDK is not already configured
echo "sdk.dir=/path/to/android-sdk" > local.properties

./gradlew test
./gradlew assembleDebug
```

`local.properties` is gitignored. The APK is written under `app/build/`, which is also gitignored and can be rebuilt.

Open the project in Android Studio (this folder as the Gradle root) to run it on a device or emulator. The app needs camera permission to scan; typing a code works without it.

## Layout

| Path | What it holds |
|---|---|
| `app/src/main/java/org/bioid/tubecheck/parse/` | Pure Kotlin port of `app/src/parse.js` (status, scan, timeline) |
| `app/src/main/java/org/bioid/tubecheck/tzkt/` | Per-tube TzKT client, matching `app/src/tzkt.js` |
| `app/src/main/java/org/bioid/tubecheck/ui/` | Compose screens and the camera scanner |
| `app/src/main/java/org/bioid/tubecheck/custody/` | HTTP client and JSON for the signing front |
| `app/src/test/` | JVM unit tests for parsing, status, and custody request JSON, with synthetic fixture JSON |

## Limits

- The chain proves a record was made, by which key, when and in what order. It does not prove a tube is physically where the record says.
- Only non-personal tube ids, events and hashes belong on-chain. Donors never hold wallets.
- The app does not decrypt hidden metadata (white paper §3.11) and does not verify salted fingerprints. A dataset line can show that a fingerprint was recorded.
- This prototype does not claim regulatory compliance.
