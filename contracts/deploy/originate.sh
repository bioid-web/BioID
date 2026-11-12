#!/usr/bin/env bash
# Compile the bioid FA2 contract and, only when BIOID_ORIGINATE=1, originate
# it on Shadownet. This script never creates a key, never calls a faucet,
# and never targets mainnet.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NETWORK="${TEZOS_NETWORK:-}"
RPC="${TEZOS_RPC_URL:-}"
KEY="${TEZOS_KEY_REF:-}"
ADMIN="${TEZOS_ADMIN:-}"

refuse() {
  echo "refused: $*" >&2
  exit 2
}

case "$(printf '%s' "$NETWORK" | tr '[:upper:]' '[:lower:]')" in
  shadownet) ;;
  mainnet) refuse "mainnet is not a target. Set TEZOS_NETWORK=shadownet" ;;
  ghostnet) refuse "Ghostnet has been removed. Set TEZOS_NETWORK=shadownet" ;;
  *) refuse "TEZOS_NETWORK must be shadownet" ;;
esac

rpc_lower="$(printf '%s' "$RPC" | tr '[:upper:]' '[:lower:]')"
if [[ "$rpc_lower" == *mainnet* || "$rpc_lower" == *tzbeta* || "$rpc_lower" == *mainnet.api.tez.ie* ]]; then
  refuse "TEZOS_RPC_URL looks like mainnet"
fi
if [[ "$rpc_lower" == *ghostnet* ]]; then
  refuse "TEZOS_RPC_URL points at retired Ghostnet. Use https://rpc.shadownet.teztnets.com"
fi
if [[ "$rpc_lower" != *shadownet* ]]; then
  refuse "TEZOS_RPC_URL must be a shadownet endpoint, for example https://rpc.shadownet.teztnets.com"
fi
if [[ -z "$KEY" ]]; then
  refuse "TEZOS_KEY_REF is required (a KMS alias or an octez alias that already exists)"
fi
key_lower="$(printf '%s' "$KEY" | tr '[:upper:]' '[:lower:]')"
case "$key_lower" in
  edsk*|spsk*|p2sk*|edesk*|*"edsk"*) refuse "TEZOS_KEY_REF looks like a raw secret key" ;;
esac
if [[ -z "$ADMIN" ]]; then
  refuse "TEZOS_ADMIN is required (the address that may register wallets)"
fi

echo "network: shadownet"
echo "rpc: $RPC"
echo "key ref: $KEY"
echo "admin: $ADMIN"

cd "$ROOT/contracts"
python3 bioid_fa2.py >/tmp/bioid-contract-scenarios.log
CODE_TZ="$(find bioid_happy -name 'step_001*_contract.tz' | head -n 1)"
if [[ -z "$CODE_TZ" || ! -s "$CODE_TZ" ]]; then
  refuse "compilation did not write a contract .tz file"
fi
echo "michelson: $ROOT/contracts/$CODE_TZ"

if [[ "${BIOID_ORIGINATE:-}" != "1" ]]; then
  cat <<EOF

Compile only. Nothing was originated.

To originate on Shadownet later, with a key alias you already control:

  export TEZOS_NETWORK=shadownet
  export TEZOS_RPC_URL=https://rpc.shadownet.teztnets.com
  export TEZOS_KEY_REF=<kms alias or existing octez alias>
  export TEZOS_ADMIN=<your shadownet admin address>
  export BIOID_ORIGINATE=1
  bash contracts/deploy/originate.sh

That run builds storage for TEZOS_ADMIN and, if octez-client is on PATH,
asks it to originate. It still does not generate a key and does not call a faucet.
Fund the admin account yourself before you run it.
EOF
  exit 0
fi

python3 "$ROOT/contracts/deploy/build_storage.py"
STORAGE_TZ="$ROOT/contracts/bioid_storage/step_001_cont_0_storage.tz"
if [[ ! -s "$STORAGE_TZ" ]]; then
  refuse "storage compilation failed"
fi

CHAIN_ID="$(curl -fsS "${RPC%/}/chains/main/chain_id" | tr -d '"[:space:]' || true)"
if [[ "$CHAIN_ID" != "NetXsqzbfFenSTS" ]]; then
  refuse "RPC chain id is '${CHAIN_ID}', expected Shadownet NetXsqzbfFenSTS"
fi

if ! command -v octez-client >/dev/null 2>&1; then
  refuse "octez-client is not on PATH. Install the Octez client that matches Shadownet, then re-run with BIOID_ORIGINATE=1. Code: $CODE_TZ Storage: $STORAGE_TZ"
fi

octez-client --endpoint "$RPC" originate contract bioid_fa2 \
  transferring 0 from "$KEY" \
  running "$ROOT/contracts/$CODE_TZ" \
  --init "$(cat "$STORAGE_TZ")" \
  --burn-cap "${BIOID_BURN_CAP:-12}"
echo "If origination succeeded, put the printed KT1 in TEZOS_CONTRACT. Do not commit the key."
