from bioid_bridge.cli import main
from bioid_bridge.fingerprint import fingerprint, new_salt, verify

import hashlib

import pytest


def test_unsalted_is_plain_sha256():
    assert fingerprint(b"synthetic") == hashlib.sha256(b"synthetic").hexdigest()


def test_salt_defeats_guessing():
    form = b"consent form v3, box 2 ticked"
    salt = new_salt()
    salted = fingerprint(form, salt)
    assert len(salted) == 64
    # Someone who guesses the document cannot confirm it without the salt.
    assert salted != fingerprint(form)
    assert salted != fingerprint(form, new_salt())
    assert verify(form, salted, salt)
    assert not verify(b"consent form v3, box 1 ticked", salted, salt)


def test_short_salt_is_refused():
    with pytest.raises(ValueError):
        fingerprint(b"x", b"short")


def test_cli_new_salt_and_verify(tmp_path, capsys):
    doc = tmp_path / "agreement.txt"
    doc.write_bytes(b"synthetic agreement")
    salt = tmp_path / "agreement.salt"
    assert main(["fingerprint", "--file", str(doc), "--new-salt", str(salt)]) == 0
    digest = capsys.readouterr().out.strip()
    assert len(salt.read_bytes()) == 32
    assert main(["fingerprint", "--file", str(doc), "--salt-file", str(salt), "--verify", digest]) == 0
    assert main(["fingerprint", "--file", str(doc), "--verify", digest]) == 1
    # Never overwrite an existing salt: that would orphan every fingerprint made with it.
    assert main(["fingerprint", "--file", str(doc), "--new-salt", str(salt)]) == 2
