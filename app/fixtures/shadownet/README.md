# Recorded Shadownet responses

These JSON files are copies of public TzKT responses for the synthetic pilot contract `KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix`, read on 19 October 2026 from `https://api.shadownet.tzkt.io/v1`.

Bigmap files are the key lists for `code_index`, `tokens`, `wallet_registry`, and `attachments`. `events.json` is `GET /v1/contracts/events?contract=KT1HpDatoa5tHDctAQDY7wQgVEnrWJ9S3vix`. `transactions.json` keeps `id`, `hash`, `timestamp`, `entrypoint`, and `status` from `GET /v1/operations/transactions?target=…&status=applied`, which is enough to join `events[].transactionId` to an explorer operation hash. `storage.json` keeps the bigmap pointers used by that join.

The tube codes, volumes, and wallet labels are synthetic. Unit tests read these files and do not call the network.
