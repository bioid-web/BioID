"""bioid FA2 contract.

One nat token id per tube, balance in microlitres, tube code stored beside it.
Standard FA2 ``transfer`` is disabled: custody moves go through ``move``,
``ship`` and ``receive`` so every one of them carries a reason.

Run the scenarios with ``python3 contracts/bioid_fa2.py``.
"""

import smartpy as sp


@sp.module
def bioid():
    data_t: type = sp.record(
        data_uri=sp.string,
        content_hash=sp.bytes,
        data_type=sp.string,
        licence=sp.option[sp.string],
        access_level=sp.option[sp.string],
        step=sp.string,
    )
    token_t: type = sp.record(
        code=sp.string,
        code_utf8=sp.bytes,
        parent_id=sp.option[sp.nat],
        root_id=sp.nat,
        sample_type=sp.string,
        sample_type_utf8=sp.bytes,
        created_by=sp.string,
        consent_ref=sp.string,
        wallet=sp.address,
        balance=sp.nat,
        status=sp.string,
        destroyed=sp.bool,
        meta_uri=sp.string,
        meta_hash=sp.bytes,
    )
    wallet_t: type = sp.record(
        type=sp.string,
        label=sp.string,
        site=sp.string,
        parent_location=sp.option[sp.address],
        custodian=sp.address,
        active=sp.bool,
        metadata_uri=sp.string,
        process=sp.string,
    )
    access_t: type = sp.record(
        token_id=sp.nat,
        requester=sp.address,
        agreement_ref=sp.string,
        agreement_hash=sp.bytes,
        duo_codes=sp.string,
        status=sp.string,
    )
    balance_of_args: type = sp.record(
        requests=sp.list[sp.record(owner=sp.address, token_id=sp.nat)],
        callback=sp.contract[
            sp.list[
                sp.record(
                    request=sp.record(owner=sp.address, token_id=sp.nat),
                    balance=sp.nat,
                ).layout(("request", "balance"))
            ]
        ],
    ).layout(("requests", "callback"))

    @sp.effects(with_storage="no-access")
    def assert_uri(uri):
        assert sp.len(uri) >= 8, "BIOID_DATA"
        head = sp.slice(0, 8, uri).unwrap_some()
        ipfs = False
        if sp.len(uri) >= 7:
            ipfs = sp.slice(0, 7, uri).unwrap_some() == "ipfs://"
        assert head == "https://" or ipfs, "BIOID_DATA"

    @sp.effects(with_storage="no-access")
    def assert_hash(digest):
        assert sp.len(digest) == 32, "BIOID_DATA"

    @sp.effects(with_storage="no-access")
    def status_for(kind):
        status = "active"
        if kind == "TRANSIT":
            status = "in_transit"
        if kind == "PROCESS":
            status = "in_process"
        return status

    @sp.effects(with_storage="no-access")
    def move_allowed(p):
        ok = False
        if p.src == "INTAKE" and p.dst == "STORAGE" and p.reason == "stored":
            ok = True
        if p.src == "INTAKE" and p.dst == "PROCESS" and p.reason == "to_process":
            ok = True
        if p.src == "INTAKE" and p.dst == "QUARANTINE" and p.reason == "qc_hold":
            ok = True
        if p.src == "STORAGE" and p.dst == "STORAGE" and (
            p.reason == "stored" or p.reason == "moved" or p.reason == "thawed"
        ):
            ok = True
        if p.src == "STORAGE" and p.dst == "PROCESS" and (
            p.reason == "to_process" or p.reason == "retrieval"
        ):
            ok = True
        if p.src == "STORAGE" and p.dst == "QUARANTINE" and p.reason == "qc_hold":
            ok = True
        if p.src == "PROCESS" and p.dst == "PROCESS" and p.reason == "moved":
            ok = True
        if p.src == "PROCESS" and p.dst == "STORAGE" and p.reason == "stored":
            ok = True
        if p.src == "PROCESS" and p.dst == "QUARANTINE" and p.reason == "qc_hold":
            ok = True
        if p.src == "QUARANTINE" and p.dst == "STORAGE" and p.reason == "released":
            ok = True
        if p.src == "QUARANTINE" and p.dst == "INTAKE" and p.reason == "released":
            ok = True
        return ok

    @sp.effects(with_storage="no-access")
    def ship_allowed(src):
        return (
            src == "INTAKE"
            or src == "STORAGE"
            or src == "QUARANTINE"
            or src == "EXTERNAL_USER"
        )

    class Bioid(sp.Contract):
        def __init__(self, admin, metadata):
            self.data.admin = admin
            self.data.metadata = metadata
            self.data.next_token_id = sp.nat(0)
            self.data.next_request_id = sp.nat(0)
            self.data.ledger = sp.cast(
                sp.big_map(), sp.big_map[sp.pair[sp.address, sp.nat], sp.nat]
            )
            self.data.operators = sp.cast(
                sp.big_map(),
                sp.big_map[
                    sp.record(
                        owner=sp.address, operator=sp.address, token_id=sp.nat
                    ).layout(("owner", ("operator", "token_id"))),
                    sp.unit,
                ],
            )
            self.data.token_metadata = sp.cast(
                sp.big_map(),
                sp.big_map[
                    sp.nat,
                    sp.record(token_id=sp.nat, token_info=sp.map[sp.string, sp.bytes]),
                ],
            )
            self.data.supply = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.nat])
            self.data.tokens = sp.cast(sp.big_map(), sp.big_map[sp.nat, token_t])
            self.data.code_index = sp.cast(
                sp.big_map(), sp.big_map[sp.string, sp.nat]
            )
            self.data.wallet_registry = sp.cast(
                sp.big_map(), sp.big_map[sp.address, wallet_t]
            )
            self.data.owners = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.address])
            self.data.by_root = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, sp.set[sp.nat]]
            )
            self.data.outcomes = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.string])
            self.data.access_requests = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, access_t]
            )
            self.data.approved = sp.cast(sp.big_map(), sp.big_map[sp.nat, sp.nat])
            self.data.held_by_external = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, sp.address]
            )
            self.data.attachments = sp.cast(
                sp.big_map(), sp.big_map[sp.nat, sp.list[data_t]]
            )

        @sp.private(with_storage="read-only")
        def p_wallet(self, address):
            assert address in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
            return self.data.wallet_registry[address]

        @sp.private(with_storage="read-only")
        def p_token_id_of(self, code):
            assert code in self.data.code_index, "BIOID_UNKNOWN_TUBE"
            return self.data.code_index[code]

        @sp.private(with_storage="read-only")
        def p_assert_operable(self, token_id):
            status = self.data.tokens[token_id].status
            assert status != "frozen", "BIOID_FROZEN"
            assert status != "stopped", "BIOID_FROZEN"
            assert status != "destroyed", "BIOID_DESTROYED"

        @sp.private(with_storage="read-write")
        def p_remember(self, p):
            if p.root_id in self.data.by_root:
                ids = self.data.by_root[p.root_id]
                ids.add(p.token_id)
                self.data.by_root[p.root_id] = ids
            else:
                self.data.by_root[p.root_id] = {p.token_id}

        @sp.private(with_storage="read-write")
        def p_write_metadata(self, p):
            self.data.token_metadata[p.token_id] = sp.record(
                token_id=p.token_id,
                token_info={
                    "name": p.name,
                    "symbol": sp.bytes("0x754c"),
                    "decimals": sp.bytes("0x30"),
                    "sample_type": p.sample_type,
                    "created_by": p.created_by,
                    "parent_id": p.parent,
                },
            )

        @sp.private(with_storage="read-write")
        def p_set_balance(self, p):
            if p.old_wallet != p.new_wallet:
                self.data.ledger[(p.old_wallet, p.token_id)] = 0
            self.data.ledger[(p.new_wallet, p.token_id)] = p.balance

        @sp.private(with_storage="read-write", with_operations=True)
        def p_maybe_attach(self, p):
            if p.data.is_some():
                d = p.data.unwrap_some()
                assert_uri(d.data_uri)
                assert_hash(d.content_hash)
                token = self.data.tokens[p.token_id]
                assert token.wallet in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
                holder = self.data.wallet_registry[token.wallet]
                allowed = sp.sender == holder.custodian
                if p.token_id in self.data.held_by_external:
                    if sp.sender == self.data.held_by_external[p.token_id]:
                        allowed = True
                assert allowed, "BIOID_NOT_CUSTODIAN"
                items = self.data.attachments[p.token_id]
                items.push(d)
                self.data.attachments[p.token_id] = items
                sp.emit(
                    sp.record(
                        token_id=p.token_id,
                        code=token.code,
                        data_uri=d.data_uri,
                        content_hash=d.content_hash,
                        data_type=d.data_type,
                        step=d.step,
                    ),
                    tag="DATA_ATTACHED",
                )

        @sp.private(with_storage="read-write")
        def p_do_ship(self, p):
            status = self.data.tokens[p.token_id].status
            assert status != "frozen", "BIOID_FROZEN"
            assert status != "stopped", "BIOID_FROZEN"
            assert status != "destroyed", "BIOID_DESTROYED"
            token = self.data.tokens[p.token_id]
            assert token.wallet in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
            source = self.data.wallet_registry[token.wallet]
            assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
            assert p.dest in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
            target = self.data.wallet_registry[p.dest]
            assert target.active, "BIOID_INACTIVE"
            assert target.type == "TRANSIT", "BIOID_BAD_TYPE"
            assert p.dest != token.wallet, "BIOID_SAME_WALLET"
            allowed = ship_allowed(source.type)
            if source.type == "PROCESS":
                assert source.process == "retrieval", "BIOID_PROCESS_SHIP"
                assert p.token_id in self.data.approved, "BIOID_NO_ACCESS"
                allowed = True
            assert allowed, "BIOID_BAD_TYPE"
            self.data.ledger[(token.wallet, p.token_id)] = 0
            self.data.ledger[(p.dest, p.token_id)] = token.balance
            with sp.modify_record(self.data.tokens[p.token_id]) as row:
                row.wallet = p.dest
                row.status = "in_transit"
            return sp.record(code=token.code, balance=token.balance)

        @sp.private(with_storage="read-write")
        def p_do_consume(self, p):
            status = self.data.tokens[p.token_id].status
            assert status != "frozen", "BIOID_FROZEN"
            assert status != "stopped", "BIOID_FROZEN"
            assert status != "destroyed", "BIOID_DESTROYED"
            assert p.amount > 0, "BIOID_BURN"
            token = self.data.tokens[p.token_id]
            assert token.wallet in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
            source = self.data.wallet_registry[token.wallet]
            assert source.active, "BIOID_INACTIVE"
            assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
            if p.external:
                assert source.type == "EXTERNAL_USER", "BIOID_NOT_PROCESS"
            else:
                assert source.type == "PROCESS", "BIOID_NOT_PROCESS"
            updated = sp.as_nat(token.balance - p.amount, error="BIOID_BURN")
            self.data.supply[p.token_id] = sp.as_nat(
                self.data.supply[p.token_id] - p.amount, error="BIOID_BURN"
            )
            self.data.ledger[(token.wallet, p.token_id)] = updated
            with sp.modify_record(self.data.tokens[p.token_id]) as row:
                row.balance = updated
            return sp.record(code=token.code, balance=updated)

        @sp.entrypoint
        def transfer(self, batch):
            sp.cast(
                batch,
                sp.list[
                    sp.record(
                        from_=sp.address,
                        txs=sp.list[
                            sp.record(
                                to_=sp.address, token_id=sp.nat, amount=sp.nat
                            ).layout(("to_", ("token_id", "amount")))
                        ],
                    ).layout(("from_", "txs"))
                ],
            )
            raise "BIOID_TRANSFER_DISABLED"

        @sp.entrypoint
        def update_operators(self, actions):
            for action in actions:
                match action:
                    case add_operator(operator):
                        assert operator.owner == sp.sender, "FA2_NOT_OWNER"
                        self.data.operators[operator] = ()
                    case remove_operator(operator):
                        assert operator.owner == sp.sender, "FA2_NOT_OWNER"
                        del self.data.operators[operator]

        @sp.entrypoint
        def balance_of(self, param):
            sp.cast(param, balance_of_args)
            balances = []
            for req in param.requests:
                assert req.token_id < self.data.next_token_id, "FA2_TOKEN_UNDEFINED"
                balances.push(
                    sp.record(
                        request=sp.record(owner=req.owner, token_id=req.token_id),
                        balance=self.data.ledger.get(
                            (req.owner, req.token_id), default=0
                        ),
                    )
                )
            sp.transfer(reversed(balances), sp.mutez(0), param.callback)

        @sp.entrypoint
        def register_wallet(self, param):
            assert sp.sender == self.data.admin, "BIOID_NOT_ADMIN"
            assert not (param.address in self.data.wallet_registry), "BIOID_WALLET_EXISTS"
            known = (
                param.type == "STORAGE"
                or param.type == "INTAKE"
                or param.type == "PROCESS"
                or param.type == "TRANSIT"
                or param.type == "QUARANTINE"
                or param.type == "EXTERNAL_USER"
            )
            assert known, "BIOID_BAD_TYPE"
            if param.parent_location.is_some():
                parent = self.p_wallet(param.parent_location.unwrap_some())
                assert parent.type == "STORAGE", "BIOID_BAD_TYPE"
            self.data.wallet_registry[param.address] = sp.record(
                type=param.type,
                label=param.label,
                site=param.site,
                parent_location=param.parent_location,
                custodian=param.custodian,
                active=param.active,
                metadata_uri=param.metadata_uri,
                process=param.process,
            )

        @sp.entrypoint
        def set_wallet_active(self, address, active):
            assert sp.sender == self.data.admin, "BIOID_NOT_ADMIN"
            assert address in self.data.wallet_registry, "BIOID_UNKNOWN_WALLET"
            with sp.modify_record(self.data.wallet_registry[address]) as row:
                row.active = active

        @sp.entrypoint
        def set_wallet_label(self, address, label, metadata_uri):
            row = self.p_wallet(address)
            assert sp.sender == row.custodian, "BIOID_NOT_CUSTODIAN"
            with sp.modify_record(self.data.wallet_registry[address]) as wallet_row:
                wallet_row.label = label
                wallet_row.metadata_uri = metadata_uri

        @sp.entrypoint
        def mint_primary(self, param):
            assert param.volume_ul > 0, "BIOID_MINT_DEST"
            assert not (param.code in self.data.code_index), "BIOID_EXISTS"
            assert sp.len(param.consent_ref) > 0, "BIOID_DATA"
            dest = self.p_wallet(param.to_wallet)
            assert dest.active, "BIOID_INACTIVE"
            assert sp.sender == dest.custodian, "BIOID_NOT_CUSTODIAN"
            assert dest.type == "INTAKE" or dest.type == "TRANSIT", "BIOID_MINT_DEST"
            token_id = self.data.next_token_id
            self.data.next_token_id += 1
            self.data.code_index[param.code] = token_id
            self.data.owners[token_id] = param.owner
            self.p_remember(sp.record(root_id=token_id, token_id=token_id))
            self.data.supply[token_id] = param.volume_ul
            self.data.ledger[(param.to_wallet, token_id)] = param.volume_ul
            self.data.attachments[token_id] = []
            self.data.tokens[token_id] = sp.record(
                code=param.code,
                code_utf8=param.code_utf8,
                parent_id=None,
                root_id=token_id,
                sample_type=param.sample_type,
                sample_type_utf8=param.sample_type_utf8,
                created_by="collected",
                consent_ref=param.consent_ref,
                wallet=param.to_wallet,
                balance=param.volume_ul,
                status=status_for(dest.type),
                destroyed=False,
                meta_uri=param.meta_uri,
                meta_hash=param.meta_hash,
            )
            self.p_write_metadata(
                sp.record(
                    token_id=token_id,
                    name=param.code_utf8,
                    sample_type=param.sample_type_utf8,
                    created_by=sp.bytes("0x636f6c6c6563746564"),
                    parent=sp.bytes("0x"),
                )
            )
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=param.code,
                    to_=param.to_wallet,
                    volume=param.volume_ul,
                    reason="collected",
                ),
                tag="MINT",
            )

        @sp.entrypoint
        def move(self, code, to_wallet, reason, data):
            token_id = self.p_token_id_of(code)
            self.p_assert_operable(token_id)
            token = self.data.tokens[token_id]
            source = self.p_wallet(token.wallet)
            assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
            dest = self.p_wallet(to_wallet)
            assert dest.active, "BIOID_INACTIVE"
            assert to_wallet != token.wallet, "BIOID_SAME_WALLET"
            assert reason != "shipped", "BIOID_BAD_REASON"
            assert move_allowed(
                sp.record(src=source.type, dst=dest.type, reason=reason)
            ), "BIOID_BAD_REASON"
            assert source.site == dest.site, "BIOID_CROSS_SITE"
            self.p_set_balance(
                sp.record(
                    token_id=token_id,
                    old_wallet=token.wallet,
                    new_wallet=to_wallet,
                    balance=token.balance,
                )
            )
            with sp.modify_record(self.data.tokens[token_id]) as row:
                row.wallet = to_wallet
                row.status = status_for(dest.type)
            self.p_maybe_attach(sp.record(token_id=token_id, data=data))
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=code,
                    to_=to_wallet,
                    reason=reason,
                    balance=token.balance,
                ),
                tag="MOVE",
            )

        @sp.entrypoint
        def ship(self, code, to_wallet, data):
            token_id = self.p_token_id_of(code)
            shipped = self.p_do_ship(sp.record(token_id=token_id, dest=to_wallet))
            self.p_maybe_attach(sp.record(token_id=token_id, data=data))
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=shipped.code,
                    to_=to_wallet,
                    reason="shipped",
                    balance=shipped.balance,
                ),
                tag="SHIP",
            )

        @sp.entrypoint
        def receive(self, code, to_wallet, data):
            token_id = self.p_token_id_of(code)
            self.p_assert_operable(token_id)
            token = self.data.tokens[token_id]
            source = self.p_wallet(token.wallet)
            assert source.type == "TRANSIT", "BIOID_NOT_TRANSIT"
            dest = self.p_wallet(to_wallet)
            assert dest.active, "BIOID_INACTIVE"
            assert sp.sender == dest.custodian, "BIOID_NOT_CUSTODIAN"
            assert (
                dest.type == "STORAGE"
                or dest.type == "INTAKE"
                or dest.type == "QUARANTINE"
                or dest.type == "EXTERNAL_USER"
            ), "BIOID_RECEIVE_DEST"
            if dest.type == "EXTERNAL_USER":
                assert token_id in self.data.approved, "BIOID_NO_ACCESS"
                request = self.data.access_requests[self.data.approved[token_id]]
                assert request.status == "approved", "BIOID_NO_ACCESS"
                assert request.requester == dest.custodian, "BIOID_NO_ACCESS"
                self.data.held_by_external[token_id] = dest.custodian
            self.p_set_balance(
                sp.record(
                    token_id=token_id,
                    old_wallet=token.wallet,
                    new_wallet=to_wallet,
                    balance=token.balance,
                )
            )
            with sp.modify_record(self.data.tokens[token_id]) as row:
                row.wallet = to_wallet
                row.status = "active"
            self.p_maybe_attach(sp.record(token_id=token_id, data=data))
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=code,
                    to_=to_wallet,
                    reason="received",
                    balance=token.balance,
                ),
                tag="RECEIVE",
            )

        @sp.entrypoint
        def transform(self, code, burn_ul, reason, reason_utf8, children, data):
            token_id = self.p_token_id_of(code)
            self.p_assert_operable(token_id)
            assert burn_ul > 0, "BIOID_BURN"
            known = (
                reason == "aliquoted"
                or reason == "split"
                or reason == "rna_isolation"
                or reason == "dna_isolation"
            )
            assert known, "BIOID_BAD_REASON"
            token = self.data.tokens[token_id]
            source = self.p_wallet(token.wallet)
            assert source.active, "BIOID_INACTIVE"
            assert source.type == "PROCESS", "BIOID_NOT_PROCESS"
            assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
            updated = sp.as_nat(token.balance - burn_ul, error="BIOID_BURN")
            self.data.supply[token_id] = sp.as_nat(
                self.data.supply[token_id] - burn_ul, error="BIOID_BURN"
            )
            self.p_set_balance(
                sp.record(
                    token_id=token_id,
                    old_wallet=token.wallet,
                    new_wallet=token.wallet,
                    balance=updated,
                )
            )
            with sp.modify_record(self.data.tokens[token_id]) as row:
                row.balance = updated
            for child in children:
                assert child.volume_ul > 0, "BIOID_MINT_DEST"
                assert not (child.code in self.data.code_index), "BIOID_EXISTS"
                dest = self.p_wallet(child.to_wallet)
                assert dest.active, "BIOID_INACTIVE"
                assert dest.type == "STORAGE" or dest.type == "PROCESS", "BIOID_BAD_TYPE"
                assert dest.site == source.site, "BIOID_CROSS_SITE"
                child_id = self.data.next_token_id
                self.data.next_token_id += 1
                self.data.code_index[child.code] = child_id
                self.data.supply[child_id] = child.volume_ul
                self.data.ledger[(child.to_wallet, child_id)] = child.volume_ul
                self.data.attachments[child_id] = []
                self.p_remember(sp.record(root_id=token.root_id, token_id=child_id))
                self.data.tokens[child_id] = sp.record(
                    code=child.code,
                    code_utf8=child.code_utf8,
                    parent_id=sp.Some(token_id),
                    root_id=token.root_id,
                    sample_type=child.sample_type,
                    sample_type_utf8=child.sample_type_utf8,
                    created_by=reason,
                    consent_ref=token.consent_ref,
                    wallet=child.to_wallet,
                    balance=child.volume_ul,
                    status=status_for(dest.type),
                    destroyed=False,
                    meta_uri=token.meta_uri,
                    meta_hash=token.meta_hash,
                )
                self.p_write_metadata(
                    sp.record(
                        token_id=child_id,
                        name=child.code_utf8,
                        sample_type=child.sample_type_utf8,
                        created_by=reason_utf8,
                        parent=token.code_utf8,
                    )
                )
                sp.emit(
                    sp.record(
                        token_id=child_id,
                        code=child.code,
                        parent=code,
                        volume=child.volume_ul,
                        reason=reason,
                    ),
                    tag="MINT",
                )
            self.p_maybe_attach(sp.record(token_id=token_id, data=data))
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=code,
                    burned=burn_ul,
                    balance=updated,
                    reason=reason,
                ),
                tag="TRANSFORM",
            )

        @sp.entrypoint
        def consume(self, code, amount, data):
            token_id = self.p_token_id_of(code)
            consumed = self.p_do_consume(sp.record(token_id=token_id, amount=amount, external=False))
            self.p_maybe_attach(sp.record(token_id=token_id, data=data))
            sp.emit(
                sp.record(
                    token_id=token_id,
                    code=consumed.code,
                    amount=amount,
                    balance=consumed.balance,
                    reason="consumed",
                ),
                tag="CONSUME",
            )

        @sp.entrypoint
        def adjust_volume(self, code, volume_ul, reason):
            token_id = self.p_token_id_of(code)
            self.p_assert_operable(token_id)
            known = reason == "measured" or reason == "evaporation" or reason == "dead_volume"
            assert known, "BIOID_BAD_REASON"
            token = self.data.tokens[token_id]
            source = self.p_wallet(token.wallet)
            assert source.active, "BIOID_INACTIVE"
            assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
            assert source.type == "INTAKE" or source.type == "STORAGE", "BIOID_ADJUST"
            self.data.supply[token_id] = volume_ul
            self.p_set_balance(
                sp.record(
                    token_id=token_id,
                    old_wallet=token.wallet,
                    new_wallet=token.wallet,
                    balance=volume_ul,
                )
            )
            with sp.modify_record(self.data.tokens[token_id]) as row:
                row.balance = volume_ul
            sp.emit(
                sp.record(token_id=token_id, code=code, volume=volume_ul, reason=reason),
                tag="ADJUST",
            )

        @sp.entrypoint
        def withdraw(self, code, outcome):
            token_id = self.p_token_id_of(code)
            token = self.data.tokens[token_id]
            assert token.parent_id.is_none(), "BIOID_NOT_ROOT"
            assert self.data.owners[token.root_id] == sp.sender, "BIOID_NOT_OWNER"
            assert not (token.root_id in self.data.outcomes), "BIOID_FROZEN"
            known = outcome == "destroy" or outcome == "anonymise" or outcome == "stop_use"
            assert known, "BIOID_BAD_REASON"
            self.data.outcomes[token.root_id] = outcome
            status = "frozen"
            if outcome == "stop_use":
                status = "stopped"
            for member in self.data.by_root[token.root_id].elements():
                with sp.modify_record(self.data.tokens[member]) as row:
                    row.status = status
            sp.emit(
                sp.record(root=code, outcome=outcome),
                tag="WITHDRAW",
            )

        @sp.entrypoint
        def confirm_destroyed(self, code):
            token_id = self.p_token_id_of(code)
            token = self.data.tokens[token_id]
            assert not token.destroyed, "BIOID_DESTROYED"
            assert token.status == "frozen", "BIOID_FROZEN"
            assert self.data.outcomes[token.root_id] == "destroy", "BIOID_BAD_REASON"
            source = self.p_wallet(token.wallet)
            assert sp.sender == source.custodian or sp.sender == self.data.owners[token.root_id], (
                "BIOID_NOT_CUSTODIAN"
            )
            if token.balance > 0:
                self.data.supply[token_id] = 0
                self.p_set_balance(
                    sp.record(
                        token_id=token_id,
                        old_wallet=token.wallet,
                        new_wallet=token.wallet,
                        balance=0,
                    )
                )
            with sp.modify_record(self.data.tokens[token_id]) as row:
                row.balance = 0
                row.destroyed = True
                row.status = "destroyed"
            sp.emit(
                sp.record(token_id=token_id, code=code, reason="withdrawn-destroyed"),
                tag="DESTROYED",
            )

        @sp.entrypoint
        def unfreeze_anonymised(self, code):
            token_id = self.p_token_id_of(code)
            token = self.data.tokens[token_id]
            assert token.parent_id.is_none(), "BIOID_NOT_ROOT"
            assert self.data.owners[token.root_id] == sp.sender, "BIOID_NOT_OWNER"
            assert self.data.outcomes[token.root_id] == "anonymise", "BIOID_BAD_REASON"
            for member in self.data.by_root[token.root_id].elements():
                with sp.modify_record(self.data.tokens[member]) as row:
                    row.status = "anonymised"
                    row.consent_ref = ""
            sp.emit(sp.record(root=code), tag="UNFREEZE")

        @sp.entrypoint
        def request_access(self, code, agreement_ref, agreement_hash, duo_codes):
            token_id = self.p_token_id_of(code)
            assert_hash(agreement_hash)
            assert sp.len(agreement_ref) > 0, "BIOID_ACCESS"
            assert sp.len(duo_codes) > 0, "BIOID_ACCESS"
            request_id = self.data.next_request_id
            self.data.next_request_id += 1
            self.data.access_requests[request_id] = sp.record(
                token_id=token_id,
                requester=sp.sender,
                agreement_ref=agreement_ref,
                agreement_hash=agreement_hash,
                duo_codes=duo_codes,
                status="pending",
            )
            sp.emit(
                sp.record(
                    request_id=request_id,
                    code=code,
                    agreement_ref=agreement_ref,
                    agreement_hash=agreement_hash,
                    duo_codes=duo_codes,
                ),
                tag="ACCESS_REQUEST",
            )

        @sp.entrypoint
        def approve_access(self, request_id):
            assert request_id in self.data.access_requests, "BIOID_ACCESS"
            request = self.data.access_requests[request_id]
            assert request.status == "pending", "BIOID_ACCESS"
            token = self.data.tokens[request.token_id]
            holder = self.p_wallet(token.wallet)
            assert sp.sender == holder.custodian or sp.sender == self.data.admin, (
                "BIOID_NOT_CUSTODIAN"
            )
            with sp.modify_record(self.data.access_requests[request_id]) as row:
                row.status = "approved"
            self.data.approved[request.token_id] = request_id
            sp.emit(
                sp.record(request_id=request_id, token_id=request.token_id),
                tag="ACCESS_APPROVED",
            )

        @sp.entrypoint
        def report_use(self, code, action, volume, to_transit, data):
            token_id = self.p_token_id_of(code)
            self.p_assert_operable(token_id)
            source = self.p_wallet(self.data.tokens[token_id].wallet)
            assert source.type == "EXTERNAL_USER", "BIOID_BAD_TYPE"
            if action == "consumed":
                consumed = self.p_do_consume(sp.record(token_id=token_id, amount=volume, external=True))
                self.p_maybe_attach(sp.record(token_id=token_id, data=data))
                sp.emit(
                    sp.record(
                        token_id=token_id,
                        code=consumed.code,
                        amount=volume,
                        balance=consumed.balance,
                        reason="consumed",
                    ),
                    tag="CONSUME",
                )
            else:
                if action == "destroyed":
                    token = self.data.tokens[token_id]
                    assert sp.sender == source.custodian, "BIOID_NOT_CUSTODIAN"
                    assert token.balance > 0, "BIOID_BURN"
                    self.data.supply[token_id] = 0
                    self.p_set_balance(
                        sp.record(
                            token_id=token_id,
                            old_wallet=token.wallet,
                            new_wallet=token.wallet,
                            balance=0,
                        )
                    )
                    with sp.modify_record(self.data.tokens[token_id]) as row:
                        row.balance = 0
                        row.destroyed = True
                        row.status = "destroyed"
                    self.p_maybe_attach(sp.record(token_id=token_id, data=data))
                    sp.emit(
                        sp.record(token_id=token_id, code=code, reason="discarded"),
                        tag="USE_REPORTED",
                    )
                else:
                    if action == "returned":
                        assert to_transit.is_some(), "BIOID_BAD_TYPE"
                        dest = to_transit.unwrap_some()
                        shipped = self.p_do_ship(sp.record(token_id=token_id, dest=dest))
                        self.p_maybe_attach(sp.record(token_id=token_id, data=data))
                        sp.emit(
                            sp.record(
                                token_id=token_id,
                                code=shipped.code,
                                to_=dest,
                                reason="shipped",
                                balance=shipped.balance,
                            ),
                            tag="SHIP",
                        )
                        sp.emit(
                            sp.record(token_id=token_id, code=code, reason="returned"),
                            tag="USE_REPORTED",
                        )
                    else:
                        raise "BIOID_BAD_REASON"

        @sp.entrypoint
        def attach_data(self, code, data):
            self.p_maybe_attach(sp.record(token_id=self.p_token_id_of(code), data=sp.Some(data)))

        @sp.offchain_view()
        def get_balance(self, params):
            assert params.token_id < self.data.next_token_id, "FA2_TOKEN_UNDEFINED"
            return self.data.ledger.get((params.owner, params.token_id), default=0)

        @sp.offchain_view()
        def total_supply(self, params):
            assert params.token_id < self.data.next_token_id, "FA2_TOKEN_UNDEFINED"
            return self.data.supply.get(params.token_id, default=0)

        @sp.offchain_view()
        def tube(self, code):
            token_id = self.p_token_id_of(code)
            token = self.data.tokens[token_id]
            return sp.record(
                token_id=token_id,
                balance=token.balance,
                wallet=token.wallet,
                parent_id=token.parent_id,
                root_id=token.root_id,
                status=token.status,
                sample_type=token.sample_type,
                consent_ref=token.consent_ref,
                destroyed=token.destroyed,
            )

        @sp.offchain_view()
        def attachment_count(self, code):
            token_id = self.p_token_id_of(code)
            return sp.len(self.data.attachments[token_id])

        @sp.offchain_view()
        def lineage_uris(self, code):
            token_id = self.p_token_id_of(code)
            uris = []
            current = token_id
            done = False
            for _step in range(0, 8):
                if not done:
                    for item in self.data.attachments[current]:
                        uris.push(item.data_uri)
                    parent = self.data.tokens[current].parent_id
                    if parent.is_some():
                        current = parent.unwrap_some()
                    else:
                        done = True
            return uris

        @sp.offchain_view()
        def lineage_has(self, param):
            token_id = self.p_token_id_of(param.code)
            found = False
            current = token_id
            done = False
            for _step in range(0, 8):
                if not done:
                    for item in self.data.attachments[current]:
                        if item.data_uri == param.uri:
                            found = True
                    parent = self.data.tokens[current].parent_id
                    if parent.is_some():
                        current = parent.unwrap_some()
                    else:
                        done = True
            return found


if __name__ == "__main__":

    def utf8(text):
        return sp.scenario_utils.bytes_of_string(text)

    def digest(text):
        import hashlib

        return sp.bytes("0x" + hashlib.sha256(text.encode()).hexdigest())

    def data_of(uri, step, kind):
        return sp.record(
            data_uri=uri,
            content_hash=digest(uri),
            data_type=kind,
            licence=sp.Some("CC-BY-4.0"),
            access_level=sp.Some("open"),
            step=step,
        )

    def child(code, volume, sample, wallet):
        return sp.record(
            code=code,
            code_utf8=utf8(code),
            volume_ul=volume,
            sample_type=sample,
            sample_type_utf8=utf8(sample),
            to_wallet=wallet,
        )

    admin = sp.test_account("Admin")
    lab = sp.test_account("Lab custodian")
    courier = sp.test_account("Courier custodian")
    external = sp.test_account("External custodian")
    owner = sp.test_account("Study owner")
    stranger = sp.test_account("Stranger")
    intake = sp.test_account("Intake wallet")
    freezer = sp.test_account("Freezer wallet")
    other_freezer = sp.test_account("Other site freezer")
    aliq = sp.test_account("Aliquot wallet")
    rna = sp.test_account("Rna wallet")
    retrieval = sp.test_account("Retrieval wallet")
    transit = sp.test_account("Transit wallet")
    external_wallet = sp.test_account("External wallet")
    quarantine = sp.test_account("Quarantine wallet")

    def metadata():
        return sp.scenario_utils.metadata_of_url(
            "https://example.org/synthetic/bioid/contract.json"
        )

    def wallet(
        address, kind, label, site, custodian, process="", parent=None, active=True
    ):
        return sp.record(
            address=address,
            type=kind,
            label=label,
            site=site,
            parent_location=parent,
            custodian=custodian,
            active=active,
            metadata_uri="https://example.org/synthetic/wallets/" + label,
            process=process,
        )

    def register_core(contract, sender):
        contract.register_wallet(
            wallet(intake.address, "INTAKE", "SYN-INTAKE", "lab-a", lab.address),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(freezer.address, "STORAGE", "SYN-FRZ", "lab-a", lab.address),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                other_freezer.address, "STORAGE", "SYN-FRZ-B", "lab-b", lab.address
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                aliq.address,
                "PROCESS",
                "SYN-ALIQ",
                "lab-a",
                lab.address,
                process="aliquoted",
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                rna.address,
                "PROCESS",
                "SYN-RNA",
                "lab-a",
                lab.address,
                process="rna_isolation",
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                retrieval.address,
                "PROCESS",
                "SYN-RETRIEVAL",
                "lab-a",
                lab.address,
                process="retrieval",
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                transit.address, "TRANSIT", "SYN-TRANSIT", "courier", courier.address
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                external_wallet.address,
                "EXTERNAL_USER",
                "SYN-EXT",
                "external",
                external.address,
            ),
            _sender=sender,
        )
        contract.register_wallet(
            wallet(
                quarantine.address, "QUARANTINE", "SYN-QC", "lab-a", lab.address
            ),
            _sender=sender,
        )

    def mint(contract, code, volume, dest, sender):
        contract.mint_primary(
            sp.record(
                code=code,
                code_utf8=utf8(code),
                owner=owner.address,
                to_wallet=dest,
                volume_ul=volume,
                sample_type="blood",
                sample_type_utf8=utf8("blood"),
                consent_ref="cref-a1b2c3",
                meta_uri="https://example.org/synthetic/tubes/" + code,
                meta_hash=digest(code),
            ),
            _sender=sender,
        )

    @sp.add_test()
    def test_happy_path():
        scenario = sp.test_scenario("bioid_happy")
        contract = bioid.Bioid(admin.address, metadata())
        scenario += contract
        register_core(contract, admin)
        mint(contract, "SY00000301", 2000, intake.address, lab)
        tube = sp.View(contract, "tube")
        scenario.verify(tube("SY00000301").balance == 2000)
        scenario.verify(tube("SY00000301").wallet == intake.address)
        scenario.verify(tube("SY00000301").parent_id.is_none())
        contract.transfer([], _sender=lab, _valid=False, _exception="BIOID_TRANSFER_DISABLED")
        contract.move(
            code="SY00000301",
            to_wallet=aliq.address,
            reason="to_process",
            data=None,
            _sender=lab,
        )
        contract.transform(
            code="SY00000301",
            burn_ul=500,
            reason="aliquoted",
            reason_utf8=utf8("aliquoted"),
            children=[child("SY00000311", 500, "aliquot", aliq.address)],
            data=sp.Some(
                data_of(
                    "https://example.org/synthetic/volume/SY00000301",
                    "aliquoted",
                    "qc",
                )
            ),
            _sender=lab,
        )
        scenario.verify(tube("SY00000301").balance == 1500)
        scenario.verify(tube("SY00000311").balance == 500)
        scenario.verify(tube("SY00000311").parent_id.is_some())
        scenario.verify(tube("SY00000311").root_id == tube("SY00000301").root_id)
        contract.attach_data(
            code="SY00000301",
            data=data_of("https://example.org/synthetic/qc/SY00000301", "collected", "qc"),
            _sender=lab,
        )
        scenario.verify(contract.attachment_count("SY00000301") == 2)
        mint(contract, "SY00000302", 3000, transit.address, courier)
        scenario.verify(tube("SY00000302").status == "in_transit")
        contract.receive(
            code="SY00000302", to_wallet=intake.address, data=None, _sender=lab
        )
        contract.move(
            code="SY00000302",
            to_wallet=aliq.address,
            reason="to_process",
            data=None,
            _sender=lab,
        )
        contract.transform(
            code="SY00000302",
            burn_ul=3000,
            reason="aliquoted",
            reason_utf8=utf8("aliquoted"),
            children=[
                child("SY00000321", 1000, "aliquot", aliq.address),
                child("SY00000322", 2000, "aliquot", aliq.address),
            ],
            data=None,
            _sender=lab,
        )
        scenario.verify(tube("SY00000302").balance == 0)
        scenario.verify(tube("SY00000302").destroyed == False)
        contract.move(
            code="SY00000321",
            to_wallet=freezer.address,
            reason="stored",
            data=sp.Some(
                data_of(
                    "https://example.org/synthetic/temperature/SY00000321",
                    "stored",
                    "temperature_log",
                )
            ),
            _sender=lab,
        )
        contract.move(
            code="SY00000322",
            to_wallet=rna.address,
            reason="moved",
            data=None,
            _sender=lab,
        )
        contract.transform(
            code="SY00000322",
            burn_ul=2000,
            reason="rna_isolation",
            reason_utf8=utf8("rna_isolation"),
            children=[child("SY00000341", 80, "RNA", freezer.address)],
            data=sp.Some(
                data_of(
                    "https://example.org/synthetic/rin/SY00000341",
                    "rna_isolation",
                    "rin",
                )
            ),
            _sender=lab,
        )
        scenario.verify(tube("SY00000341").balance == 80)
        scenario.verify(tube("SY00000341").wallet == freezer.address)
        scenario.verify(
            sp.View(contract, "get_balance")(
                sp.record(owner=freezer.address, token_id=tube("SY00000341").token_id)
            )
            == 80
        )
        scenario.verify(
            sp.View(contract, "lineage_has")(
                sp.record(
                    code="SY00000341",
                    uri="https://example.org/synthetic/rin/SY00000341",
                )
            )
        )
        contract.adjust_volume(
            code="SY00000321", volume_ul=990, reason="measured", _sender=lab
        )
        scenario.verify(tube("SY00000321").balance == 990)
        contract.request_access(
            code="SY00000321",
            agreement_ref="mta-syn-001",
            agreement_hash=digest("synthetic-mta-syn-001"),
            duo_codes="GRU",
            _sender=external,
        )
        contract.approve_access(0, _sender=lab)
        contract.move(
            code="SY00000321",
            to_wallet=retrieval.address,
            reason="retrieval",
            data=None,
            _sender=lab,
        )
        contract.ship(
            code="SY00000321", to_wallet=transit.address, data=None, _sender=lab
        )
        scenario.verify(tube("SY00000321").status == "in_transit")
        contract.receive(
            code="SY00000321",
            to_wallet=external_wallet.address,
            data=None,
            _sender=external,
        )
        contract.report_use(
            code="SY00000321",
            action="consumed",
            volume=100,
            to_transit=None,
            data=None,
            _sender=external,
        )
        scenario.verify(tube("SY00000321").balance == 890)
        contract.attach_data(
            code="SY00000321",
            data=data_of(
                "https://example.org/doi/10.5555/example.synthetic.use",
                "external_use",
                "analysis",
            ),
            _sender=external,
        )
        scenario.verify(
            sp.View(contract, "lineage_has")(
                sp.record(
                    code="SY00000321",
                    uri="https://example.org/synthetic/volume/SY00000301",
                )
            )
            == False
        )
        mint(contract, "SY00000303", 100, intake.address, lab)
        contract.move(
            code="SY00000303",
            to_wallet=freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
        )
        contract.withdraw(code="SY00000303", outcome="destroy", _sender=owner)
        scenario.verify(tube("SY00000303").status == "frozen")
        contract.confirm_destroyed("SY00000303", _sender=lab)
        scenario.verify(tube("SY00000303").balance == 0)
        scenario.verify(tube("SY00000303").destroyed)
        mint(contract, "SY00000304", 100, intake.address, lab)
        contract.withdraw(code="SY00000304", outcome="anonymise", _sender=owner)
        contract.unfreeze_anonymised("SY00000304", _sender=owner)
        scenario.verify(tube("SY00000304").status == "anonymised")
        scenario.verify(tube("SY00000304").consent_ref == "")
        contract.move(
            code="SY00000304",
            to_wallet=freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
        )
        scenario.verify(tube("SY00000304").wallet == freezer.address)

    @sp.add_test()
    def test_rejections():
        scenario = sp.test_scenario("bioid_rejections")
        contract = bioid.Bioid(admin.address, metadata())
        scenario += contract
        tube = sp.View(contract, "tube")
        register_core(contract, admin)
        contract.register_wallet(
            wallet(intake.address, "INTAKE", "SYN-INTAKE", "lab-a", lab.address),
            _sender=stranger,
            _valid=False,
            _exception="BIOID_NOT_ADMIN",
        )
        contract.mint_primary(
            sp.record(
                code="SY00000401",
                code_utf8=utf8("SY00000401"),
                owner=owner.address,
                to_wallet=freezer.address,
                volume_ul=1000,
                sample_type="blood",
                sample_type_utf8=utf8("blood"),
                consent_ref="cref-a1b2c3",
                meta_uri="https://example.org/synthetic/tubes/SY00000401",
                meta_hash=digest("SY00000401"),
            ),
            _sender=lab,
            _valid=False,
            _exception="BIOID_MINT_DEST",
        )
        mint(contract, "SY00000401", 1000, intake.address, lab)
        contract.mint_primary(
            sp.record(
                code="SY00000401",
                code_utf8=utf8("SY00000401"),
                owner=owner.address,
                to_wallet=intake.address,
                volume_ul=10,
                sample_type="blood",
                sample_type_utf8=utf8("blood"),
                consent_ref="cref-a1b2c3",
                meta_uri="https://example.org/synthetic/tubes/SY00000401",
                meta_hash=digest("x"),
            ),
            _sender=lab,
            _valid=False,
            _exception="BIOID_EXISTS",
        )
        contract.transform(
            code="SY00000401",
            burn_ul=100,
            reason="aliquoted",
            reason_utf8=utf8("aliquoted"),
            children=[child("SY00000411", 100, "aliquot", aliq.address)],
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_NOT_PROCESS",
        )
        contract.move(
            code="SY00000401",
            to_wallet=other_freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_CROSS_SITE",
        )
        contract.ship(
            code="SY00000401",
            to_wallet=transit.address,
            data=None,
            _sender=lab,
        )
        contract.receive(
            code="SY00000401",
            to_wallet=aliq.address,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_RECEIVE_DEST",
        )
        contract.receive(
            code="SY00000401",
            to_wallet=freezer.address,
            data=None,
            _sender=lab,
        )
        contract.consume(
            code="SY00000401",
            amount=10,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_NOT_PROCESS",
        )
        contract.adjust_volume(
            code="SY00000401",
            volume_ul=1,
            reason="measured",
            _sender=lab,
        )
        scenario.verify(tube("SY00000401").balance == 1)
        mint(contract, "SY00000402", 400, transit.address, courier)
        contract.adjust_volume(
            code="SY00000402",
            volume_ul=10,
            reason="measured",
            _sender=courier,
            _valid=False,
            _exception="BIOID_ADJUST",
        )
        contract.move(
            code="SY00000401",
            to_wallet=aliq.address,
            reason="to_process",
            data=None,
            _sender=lab,
        )
        contract.consume(
            code="SY00000401",
            amount=5000,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_BURN",
        )
        contract.move(
            code="SY00000401",
            to_wallet=rna.address,
            reason="moved",
            data=None,
            _sender=lab,
        )
        contract.ship(
            code="SY00000401",
            to_wallet=transit.address,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_PROCESS_SHIP",
        )
        contract.move(
            code="SY00000401",
            to_wallet=freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
        )
        contract.move(
            code="SY00000401",
            to_wallet=retrieval.address,
            reason="retrieval",
            data=None,
            _sender=lab,
        )
        contract.ship(
            code="SY00000401",
            to_wallet=transit.address,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_NO_ACCESS",
        )
        contract.receive(
            code="SY00000402",
            to_wallet=external_wallet.address,
            data=None,
            _sender=external,
            _valid=False,
            _exception="BIOID_NO_ACCESS",
        )
        contract.attach_data(
            code="SY00000401",
            data=data_of("http://example.org/synthetic/nope", "collected", "qc"),
            _sender=lab,
            _valid=False,
            _exception="BIOID_DATA",
        )
        contract.attach_data(
            code="SY00000401",
            data=data_of("https://example.org/synthetic/qc/SY00000401", "collected", "qc"),
            _sender=stranger,
            _valid=False,
            _exception="BIOID_NOT_CUSTODIAN",
        )
        contract.set_wallet_active(address=intake.address, active=False, _sender=admin)
        contract.mint_primary(
            sp.record(
                code="SY00000409",
                code_utf8=utf8("SY00000409"),
                owner=owner.address,
                to_wallet=intake.address,
                volume_ul=10,
                sample_type="blood",
                sample_type_utf8=utf8("blood"),
                consent_ref="cref-a1b2c3",
                meta_uri="https://example.org/synthetic/tubes/SY00000409",
                meta_hash=digest("SY00000409"),
            ),
            _sender=lab,
            _valid=False,
            _exception="BIOID_INACTIVE",
        )
        contract.confirm_destroyed(
            "SY00000402", _sender=courier, _valid=False, _exception="BIOID_FROZEN"
        )
        contract.move(
            code="SY00000401",
            to_wallet=freezer.address,
            reason="nope",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_BAD_REASON",
        )
        contract.move(
            code="SY00000999",
            to_wallet=freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_UNKNOWN_TUBE",
        )
        contract.move(
            code="SY00000401",
            to_wallet=stranger.address,
            reason="stored",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_UNKNOWN_WALLET",
        )
        contract.move(
            code="SY00000401",
            to_wallet=retrieval.address,
            reason="moved",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_SAME_WALLET",
        )
        contract.ship(
            code="SY00000401",
            to_wallet=freezer.address,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_BAD_TYPE",
        )
        contract.receive(
            code="SY00000401",
            to_wallet=freezer.address,
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_NOT_TRANSIT",
        )
        contract.register_wallet(
            wallet(freezer.address, "STORAGE", "SYN-FRZ", "lab-a", lab.address),
            _sender=admin,
            _valid=False,
            _exception="BIOID_WALLET_EXISTS",
        )
        contract.register_wallet(
            wallet(stranger.address, "BENCH", "SYN-BENCH", "lab-a", lab.address),
            _sender=admin,
            _valid=False,
            _exception="BIOID_BAD_TYPE",
        )
        contract.set_wallet_label(
            address=freezer.address,
            label="NOPE",
            metadata_uri="https://example.org/synthetic/wallets/NOPE",
            _sender=stranger,
            _valid=False,
            _exception="BIOID_NOT_CUSTODIAN",
        )
        contract.withdraw(
            code="SY00000401",
            outcome="destroy",
            _sender=stranger,
            _valid=False,
            _exception="BIOID_NOT_OWNER",
        )
        contract.request_access(
            code="SY00000401",
            agreement_ref="",
            agreement_hash=digest("synthetic-empty"),
            duo_codes="GRU",
            _sender=external,
            _valid=False,
            _exception="BIOID_ACCESS",
        )
        contract.transform(
            code="SY00000401",
            burn_ul=1,
            reason="aliquoted",
            reason_utf8=utf8("aliquoted"),
            children=[child("SY00000411", 1, "aliquot", aliq.address)],
            data=None,
            _sender=lab,
        )
        contract.withdraw(
            code="SY00000411",
            outcome="destroy",
            _sender=owner,
            _valid=False,
            _exception="BIOID_NOT_ROOT",
        )
        contract.withdraw(code="SY00000401", outcome="destroy", _sender=owner)
        contract.move(
            code="SY00000411",
            to_wallet=freezer.address,
            reason="stored",
            data=None,
            _sender=lab,
            _valid=False,
            _exception="BIOID_FROZEN",
        )
        contract.confirm_destroyed("SY00000411", _sender=lab)
        contract.confirm_destroyed(
            "SY00000411",
            _sender=lab,
            _valid=False,
            _exception="BIOID_DESTROYED",
        )
        contract.update_operators(
            [
                sp.variant(
                    "add_operator",
                    sp.record(
                        owner=lab.address, operator=stranger.address, token_id=0
                    ),
                )
            ],
            _sender=stranger,
            _valid=False,
            _exception="FA2_NOT_OWNER",
        )
