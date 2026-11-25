"""Shadownet-only HTTP front for ship and receive.

The phone holds no key. This service checks a bearer token, simulates the
call, signs with a testnet octez alias, and injects on Shadownet only.
It refuses any other network, any mainnet RPC, and a chain id that is not
Shadownet. Configuration and bearer tokens live outside the git tree.
"""

from __future__ import annotations

import json
import os
import sys
import re
import secrets
import subprocess
import threading
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from bioid_bridge.model import ConfigError, MainnetRefused

SHADOW_RPC = "https://rpc.shadownet.teztnets.com"
SHADOW_CHAIN = "NetXsqzbfFenSTS"
SHADOW_TZKT = "https://api.shadownet.tzkt.io/v1"
_MAINNET_MARKERS = ("mainnet", "rpc.tzbeta.net", "mainnet.api.tez.ie")
_SECRET_RE = re.compile(r"(edsk|spsk|p2sk|edesk|encrypted:)\S*", re.I)
_RECEIVE_TYPES = {"STORAGE", "INTAKE", "QUARANTINE"}

Injector = Callable[[str, str, str, bool], dict[str, Any]]


class SigningConfigError(ConfigError):
    pass


def _require_shadownet(network: str, rpc_url: str, chain_id: str) -> None:
    network = (network or "").strip().lower()
    rpc = (rpc_url or "").strip().lower()
    if network == "mainnet" or any(marker in rpc for marker in _MAINNET_MARKERS):
        raise MainnetRefused(
            "The signing service refuses mainnet. Set network=shadownet "
            f"and rpc_url={SHADOW_RPC}."
        )
    if network == "ghostnet" or "ghostnet" in rpc:
        raise SigningConfigError("Ghostnet has been removed. Use Shadownet.")
    if network != "shadownet" or "shadownet" not in rpc:
        raise SigningConfigError(
            f"network must be shadownet and rpc_url must be a Shadownet endpoint, for example {SHADOW_RPC}."
        )
    if chain_id and chain_id != SHADOW_CHAIN:
        raise SigningConfigError(f"chain_id must be Shadownet {SHADOW_CHAIN}")


def fetch_chain_id(rpc_url: str, opener=None) -> str:
    url = rpc_url.rstrip("/") + "/chains/main/chain_id"
    read = opener or (lambda u: urllib.request.urlopen(u, timeout=20).read().decode())
    raw = read(url).strip().strip('"')
    return raw


@dataclass
class Wallet:
    address: str
    label: str
    type: str
    site: str
    custodian: str


@dataclass
class Session:
    key: str
    name: str
    org: str
    alias: str
    token: str
    wallets: list[Wallet]


@dataclass
class ServiceConfig:
    network: str
    rpc_url: str
    chain_id: str
    tzkt_api: str
    contract: str
    client_dir: str
    bind: str
    port: int
    wallets: list[Wallet]
    sessions: list[Session]
    idempotency_path: Path
    confirmations: int = 1

    def wallet_by_address(self, address: str) -> Wallet | None:
        for wallet in self.wallets:
            if wallet.address == address:
                return wallet
        return None

    def session_for_token(self, token: str) -> Session | None:
        for session in self.sessions:
            if secrets.compare_digest(session.token, token):
                return session
        return None


def load_config(path: str | Path) -> ServiceConfig:
    data = json.loads(Path(path).read_text())
    network = data.get("network", "")
    rpc_url = data.get("rpc_url", "")
    chain_id = data.get("chain_id", "") or SHADOW_CHAIN
    _require_shadownet(network, rpc_url, chain_id)
    if not data.get("contract"):
        raise SigningConfigError("contract is required")
    sessions_path = Path(data["sessions_file"])
    sessions_data = json.loads(sessions_path.read_text())
    wallets = [
        Wallet(
            address=row["address"],
            label=row["label"],
            type=row["type"],
            site=row["site"],
            custodian=row["custodian"],
        )
        for row in data.get("wallets", [])
    ]
    by_addr = {w.address: w for w in wallets}
    sessions: list[Session] = []
    for key, row in sessions_data.items():
        token = row["token"]
        if not token or token.startswith("edsk"):
            raise SigningConfigError("invalid bearer token")
        session_wallets = [by_addr[addr] for addr in row["wallet_addresses"] if addr in by_addr]
        sessions.append(
            Session(
                key=key,
                name=row["name"],
                org=row["org"],
                alias=row["alias"],
                token=token,
                wallets=session_wallets,
            )
        )
    bind = data.get("bind", "127.0.0.1")
    if bind not in {"127.0.0.1", "localhost", "::1"} and os.environ.get("BIOID_SIGNING_BIND_PUBLIC") != "1":
        # Default is loopback only. A public bind needs an explicit opt-in.
        bind = "127.0.0.1"
    return ServiceConfig(
        network="shadownet",
        rpc_url=rpc_url,
        chain_id=chain_id,
        tzkt_api=data.get("tzkt_api", SHADOW_TZKT).rstrip("/"),
        contract=data["contract"],
        client_dir=data["client_dir"],
        bind=bind,
        port=int(data.get("port", 8787)),
        wallets=wallets,
        sessions=sessions,
        idempotency_path=Path(data.get("idempotency_path", Path(path).parent / "idempotency.json")),
        confirmations=int(data.get("confirmations", 1)),
    )


def michelson_ship_or_receive(code: str, to_wallet: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", code):
        raise SigningConfigError("tube code has unexpected characters")
    if not re.fullmatch(r"tz[1-3][0-9a-zA-Z]{33}", to_wallet):
        raise SigningConfigError("to_wallet is not a tz address")
    return f'(Pair "{code}" (Pair None "{to_wallet}"))'


class IdempotencyStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._data: dict[str, dict[str, Any]] = {}
        if path.exists():
            self._data = json.loads(path.read_text() or "{}")

    def get(self, request_id: str) -> dict[str, Any] | None:
        with self._lock:
            return self._data.get(request_id)

    def put(self, request_id: str, record: dict[str, Any]) -> None:
        with self._lock:
            self._data[request_id] = record
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._data, indent=2) + "\n")
            tmp.replace(self.path)


@dataclass
class SigningService:
    config: ServiceConfig
    injector: Injector | None = None
    tzkt_get: Callable[[str], Any] | None = None
    chain_id_fn: Callable[[str], str] = fetch_chain_id
    store: IdempotencyStore = field(init=False)

    def __post_init__(self) -> None:
        self.store = IdempotencyStore(self.config.idempotency_path)

    def assert_live_chain(self) -> None:
        live = self.chain_id_fn(self.config.rpc_url)
        if live != SHADOW_CHAIN:
            raise MainnetRefused(f"RPC chain id {live} is not Shadownet")

    def handle(self, method: str, path: str, headers: dict[str, str], body: bytes) -> tuple[int, dict[str, Any]]:
        route = path.split("?", 1)[0]
        try:
            if method == "GET" and route == "/health":
                return 200, {
                    "network": "shadownet",
                    "contract": self.config.contract,
                    "chain_id": self.config.chain_id,
                }
            session, error = self._auth(headers)
            if error:
                return error
            assert session is not None
            if method == "GET" and route == "/me":
                return 200, self._me(session)
            if method == "GET" and route == "/custody/inbound":
                return 200, {"tubes": self._inbound(session)}
            if method == "POST" and route in {
                "/custody/ship",
                "/custody/receive",
                "/custody/ship/preflight",
                "/custody/receive/preflight",
            }:
                payload = json.loads(body.decode() or "{}") if body else {}
                preflight = route.endswith("/preflight")
                mode = "ship" if "/ship" in route else "receive"
                return self._custody(session, mode, payload, preflight=preflight)
            return 404, {"error": "Not found."}
        except MainnetRefused as exc:
            return 403, {"error": str(exc)}
        except SigningConfigError as exc:
            return 400, {"error": str(exc)}
        except json.JSONDecodeError:
            return 400, {"error": "The body was not valid JSON."}

    def _auth(self, headers: dict[str, str]) -> tuple[Session | None, tuple[int, dict[str, Any]] | None]:
        raw = headers.get("Authorization") or headers.get("authorization") or ""
        if not raw.lower().startswith("bearer "):
            return None, (401, {"error": "Sign in with a bearer token from the signing service."})
        token = raw.split(" ", 1)[1].strip()
        session = self.config.session_for_token(token)
        if session is None:
            return None, (401, {"error": "The bearer token was not recognised."})
        return session, None

    def _wallet(self, wallet: Wallet) -> dict[str, Any]:
        return {"address": wallet.address, "label": wallet.label, "type": wallet.type, "site": wallet.site}

    def _me(self, session: Session) -> dict[str, Any]:
        return {
            "name": session.name,
            "org": session.org,
            "role": session.key,
            "wallets": [self._wallet(w) for w in session.wallets],
            "ship_destinations": [self._wallet(w) for w in self.config.wallets if w.type == "TRANSIT"],
            "receive_destinations": [self._wallet(w) for w in session.wallets if w.type in _RECEIVE_TYPES],
        }

    def _inbound(self, session: Session) -> list[dict[str, Any]]:
        transit = [w for w in self.config.wallets if w.type == "TRANSIT"]
        receive_sites = {w.site for w in session.wallets if w.type in _RECEIVE_TYPES}
        if not receive_sites:
            return []
        tubes: list[dict[str, Any]] = []
        for wallet in transit:
            for row in self._tzkt_balances(wallet.address):
                tubes.append(row)
        return tubes

    def _tzkt(self, path: str) -> Any:
        url = self.config.tzkt_api + path
        if self.tzkt_get is not None:
            return self.tzkt_get(url)
        with urllib.request.urlopen(url, timeout=20) as response:
            if response.status == 204:
                return None
            raw = response.read().decode()
            if not raw:
                return None
            return json.loads(raw)

    def _tzkt_balances(self, address: str) -> list[dict[str, Any]]:
        path = (
            f"/tokens/balances?token.contract={urllib.parse.quote(self.config.contract)}"
            f"&account={urllib.parse.quote(address)}&balance.gt=0&limit=100"
        )
        try:
            rows = self._tzkt(path) or []
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            return []
        out = []
        for row in rows:
            token = row.get("token") or {}
            meta = token.get("metadata") or {}
            code = meta.get("name") or ""
            try:
                volume = int(row.get("balance") or 0)
            except (TypeError, ValueError):
                volume = 0
            token_id = token.get("tokenId")
            try:
                token_id_n = int(token_id)
            except (TypeError, ValueError):
                token_id_n = 0
            out.append(
                {
                    "token_id": token_id_n,
                    "tube_code": code,
                    "from_site": "transit",
                    "volume_ul": volume,
                    "holder": address,
                }
            )
        return out

    def _custody(self, session: Session, mode: str, payload: dict[str, Any], *, preflight: bool) -> tuple[int, dict[str, Any]]:
        self.assert_live_chain()
        request_id = str(payload.get("client_request_id") or "").strip()
        code = str(payload.get("tube_code") or "").strip()
        to_wallet = str(payload.get("to_wallet") or "").strip()
        if not request_id or not code or not to_wallet:
            return 400, {"error": "client_request_id, tube_code and to_wallet are required."}

        fingerprint = f"{mode}:{code}:{to_wallet}"
        existing = self.store.get(request_id)
        if existing and not preflight:
            if existing.get("fingerprint") != fingerprint:
                return 409, {"error": "This request id was already used for a different operation."}
            if existing.get("op_hash"):
                return 200, {"op_hash": existing["op_hash"]}

        dest = self.config.wallet_by_address(to_wallet)
        problems: list[str] = []
        if dest is None:
            problems.append("The destination wallet is not in the registry.")
        elif mode == "ship" and dest.type != "TRANSIT":
            problems.append("A tube can only be shipped into a TRANSIT wallet.")
        elif mode == "receive" and dest.type not in _RECEIVE_TYPES:
            problems.append("A tube can only be received into STORAGE, INTAKE or QUARANTINE.")
        elif mode == "receive" and dest.address not in {w.address for w in session.wallets}:
            problems.append("That wallet is not one of yours.")

        if problems:
            if preflight:
                return 200, {"ok": False, "fee_mutez": 0, "problems": problems}
            return 202, {"reasons": problems}

        arg = michelson_ship_or_receive(code, to_wallet)
        try:
            result = self._inject(session.alias, mode, arg, dry_run=preflight)
        except SigningConfigError as exc:
            if preflight:
                return 200, {"ok": False, "fee_mutez": 0, "problems": [str(exc)]}
            return 400, {"error": str(exc)}

        if preflight:
            return 200, {
                "ok": True,
                "fee_mutez": int(result.get("fee_mutez") or 0),
                "problems": [],
            }
        op_hash = result["op_hash"]
        self.store.put(request_id, {"fingerprint": fingerprint, "op_hash": op_hash, "mode": mode})
        return 200, {"op_hash": op_hash}

    def _inject(self, alias: str, entrypoint: str, arg: str, *, dry_run: bool) -> dict[str, Any]:
        if self.injector is not None:
            return self.injector(alias, entrypoint, arg, dry_run)
        return octez_transfer(
            client_dir=self.config.client_dir,
            rpc_url=self.config.rpc_url,
            alias=alias,
            contract=self.config.contract,
            entrypoint=entrypoint,
            arg=arg,
            dry_run=dry_run,
            confirmations=self.config.confirmations,
        )


def octez_transfer(
    *,
    client_dir: str,
    rpc_url: str,
    alias: str,
    contract: str,
    entrypoint: str,
    arg: str,
    dry_run: bool,
    confirmations: int,
    runner: Callable[..., subprocess.CompletedProcess] | None = None,
) -> dict[str, Any]:
    live = fetch_chain_id(rpc_url)
    if live != SHADOW_CHAIN:
        raise MainnetRefused(f"RPC chain id {live} is not Shadownet")
    if "shadownet" not in rpc_url.lower():
        raise MainnetRefused("RPC URL is not a Shadownet endpoint")
    cmd = [
        "octez-client",
        "-d",
        client_dir,
        "--endpoint",
        rpc_url,
        "-w",
        str(confirmations),
        "transfer",
        "0",
        "from",
        alias,
        "to",
        contract,
        "--entrypoint",
        entrypoint,
        "--arg",
        arg,
        "--burn-cap",
        "1",
    ]
    if dry_run:
        cmd.append("--dry-run")
    run = runner or (lambda c: subprocess.run(c, text=True, capture_output=True))
    proc = run(cmd)
    log = _SECRET_RE.sub("[redacted]", (proc.stdout or "") + "\n" + (proc.stderr or ""))
    if proc.returncode != 0:
        tail = "\n".join(log.splitlines()[-20:])
        raise SigningConfigError(tail.strip() or "octez-client refused the operation.")
    fee_mutez = 0
    m_fee = re.search(r"Fee to the baker:\s*ꜩ([0-9.]+)", log)
    if m_fee:
        fee_mutez = int(round(float(m_fee.group(1)) * 1_000_000))
    if dry_run:
        return {"fee_mutez": fee_mutez}
    m_hash = re.search(r"Operation hash is '([^']+)'", log)
    if not m_hash:
        raise SigningConfigError("octez-client did not return an operation hash.")
    return {"op_hash": m_hash.group(1), "fee_mutez": fee_mutez}


def make_handler(service: SigningService):
    class Handler(BaseHTTPRequestHandler):
        def _dispatch(self, method: str) -> None:
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length) if length else b""
            headers = {k: v for k, v in self.headers.items()}
            status, payload = service.handle(method, self.path, headers, body)
            raw = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802
            self._dispatch("POST")

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
            return

    return Handler


def serve(config_path: str) -> None:
    service = SigningService(load_config(config_path))
    service.assert_live_chain()
    handler = make_handler(service)
    httpd = ThreadingHTTPServer((service.config.bind, service.config.port), handler)
    print(
        f"BioID signing service on http://{service.config.bind}:{service.config.port} "
        f"(shadownet {service.config.contract})",
        flush=True,
    )
    httpd.serve_forever()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Shadownet-only BioID signing HTTP front")
    parser.add_argument(
        "--config",
        default=os.environ.get("BIOID_SIGNING_CONFIG", ""),
        help="path to the service config (outside the repository)",
    )
    args = parser.parse_args(argv)
    if not args.config:
        print("BIOID_SIGNING_CONFIG or --config is required", file=sys.stderr)
        return 2
    try:
        serve(args.config)
    except (MainnetRefused, SigningConfigError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
