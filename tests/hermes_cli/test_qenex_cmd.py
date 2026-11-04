"""CLI tests for ``hermes qenex`` — setup/tick against a temp HERMES_HOME."""
from __future__ import annotations

import argparse
import importlib
import json

import pytest

from hermes_cli.subcommands.qenex import cmd_qenex


@pytest.fixture
def hermes_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "scripts").mkdir()
    (home / "cron").mkdir()
    monkeypatch.setenv("HERMES_HOME", str(home))
    import hermes_constants

    importlib.reload(hermes_constants)
    import cron.jobs

    importlib.reload(cron.jobs)
    return home


def test_setup_alias_init_creates_no_agent_job(hermes_env, capsys):
    args = argparse.Namespace(
        qenex_command="init",
        home=str(hermes_env),
        schedule="every 30m",
        no_cron=False,
    )
    assert cmd_qenex(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["invariants"]["no_agent"] is True
    assert receipt["cron"]["created"] is True
    assert (hermes_env / "scripts" / "qenex_ops.py").is_file()

    from cron.jobs import list_jobs

    jobs = list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0]["no_agent"] is True
    assert jobs[0]["script"] == "qenex_ops.py"


def test_enqueue_and_tick_via_cli(hermes_env, capsys):
    home = str(hermes_env)
    assert cmd_qenex(argparse.Namespace(
        qenex_command="setup", home=home, schedule="every 30m", no_cron=True,
    )) == 0
    capsys.readouterr()
    assert cmd_qenex(argparse.Namespace(
        qenex_command="add",
        home=home,
        sender="pi@example.ac.uk",
        subject="Lab license",
        body="quantum chemistry academic license for our chemistry group",
        source="manual",
        item_id="cli-1",
        url="",
    )) == 0
    capsys.readouterr()
    assert cmd_qenex(argparse.Namespace(qenex_command="tick", home=home)) == 0
    tick_out = json.loads(capsys.readouterr().out)
    assert tick_out["items"][0]["kind"] == "lab_license"
    assert tick_out["items"][0]["send"] is False


def test_bare_qenex_prints_usage(capsys):
    args = argparse.Namespace(qenex_command=None, home=None)
    assert cmd_qenex(args) == 1
    err = capsys.readouterr().err
    assert "hermes qenex" in err
    assert "hermes gateway install" in err
