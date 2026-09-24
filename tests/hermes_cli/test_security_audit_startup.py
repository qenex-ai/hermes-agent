"""Tests for the startup security posture audit (hermes_cli.security_audit_startup)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import hermes_cli.security_audit_startup as audit


@pytest.fixture(autouse=True)
def _reset_audit_sentinel():
    audit._AUDIT_RAN = False
    yield
    audit._AUDIT_RAN = False


# ── root check ────────────────────────────────────────────────────────────




# ── SSH password-auth check ─────────────────────────────────────────────────


# ── container / volume-mount check ──────────────────────────────────────────






# ── network listener without auth ──────────────────────────────────────────




# ── orchestration + logging ─────────────────────────────────────────────────


def test_run_security_audit_aggregates(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "_is_root", lambda: True)
    monkeypatch.setattr(audit, "_iter_sshd_config_lines", lambda: ["PasswordAuthentication yes"])
    monkeypatch.setattr(audit, "_in_container", lambda: False)
    findings = audit.run_security_audit(hermes_home=tmp_path, config={})
    assert len(findings) == 2  # root + ssh


def test_run_security_audit_clean_posture(monkeypatch, tmp_path):
    monkeypatch.setattr(audit, "_is_root", lambda: False)
    monkeypatch.setattr(audit, "_iter_sshd_config_lines", lambda: ["PasswordAuthentication no"])
    monkeypatch.setattr(audit, "_in_container", lambda: False)
    assert audit.run_security_audit(hermes_home=tmp_path, config={}) == []


def test_webhook_public_bind_warns_on_default_host():
    msg = audit._webhook_public_bind({"platforms": {"webhook": {"enabled": True, "extra": {}}}})
    assert msg is not None
    assert "Webhook adapter" in msg


def test_webhook_public_bind_silent_on_loopback():
    assert audit._webhook_public_bind(
        {"platforms": {"webhook": {"enabled": True, "extra": {"host": "127.0.0.1"}}}}
    ) is None


def test_local_terminal_with_messaging_warns():
    msg = audit._local_terminal_with_messaging(
        {"terminal": {"backend": "local"}, "platforms": {"telegram": {"enabled": True}}}
    )
    assert msg is not None
    assert "local" in msg.lower()


def test_local_terminal_with_messaging_silent_when_sandboxed():
    assert audit._local_terminal_with_messaging(
        {"terminal": {"backend": "docker"}, "platforms": {"telegram": {"enabled": True}}}
    ) is None


def test_log_startup_security_warnings_emits_and_is_idempotent(monkeypatch, tmp_path, caplog):
    import logging

    monkeypatch.setattr(audit, "_is_root", lambda: True)
    monkeypatch.setattr(audit, "_iter_sshd_config_lines", lambda: [])
    monkeypatch.setattr(audit, "_in_container", lambda: False)

    with caplog.at_level(logging.WARNING, logger="hermes.security_audit"):
        first = audit.log_startup_security_warnings(hermes_home=tmp_path, config={})
    assert len(first) == 1
    assert any("ROOT" in r.message for r in caplog.records)

    # Second call is a no-op (idempotent within a process) unless forced.
    second = audit.log_startup_security_warnings(hermes_home=tmp_path, config={})
    assert second == []
    forced = audit.log_startup_security_warnings(hermes_home=tmp_path, config={}, force=True)
    assert len(forced) == 1


