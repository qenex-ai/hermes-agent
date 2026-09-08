"""Tests for the QENEX LTD Lab ops skill — classify, draft, never send or spend.

INVARIANT: the loop can draft and queue, but send and spend stay false even when
ledger.json is edited. Setup against a temp HERMES_HOME creates a no_agent cron
job whose script lives in HERMES_HOME/scripts/.
"""
from __future__ import annotations

import importlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "optional-skills" / "productivity" / "qenex-ops"
SKILL_PATH = SKILL_DIR / "SKILL.md"
SCRIPT_PATH = SKILL_DIR / "scripts" / "qenex_ops.py"


def load_module():
    spec = importlib.util.spec_from_file_location("qenex_ops_skill", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _frontmatter_and_body():
    content = SKILL_PATH.read_text(encoding="utf-8")
    assert content.startswith("---")
    m = re.search(r"\n---\s*\n", content[3:])
    assert m, "frontmatter must close with ---"
    fm = yaml.safe_load(content[3 : m.start() + 3])
    body = content[m.end() + 3 :]
    return fm, body


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


def test_skill_file_exists():
    assert SKILL_PATH.is_file()
    assert SCRIPT_PATH.is_file()


def test_frontmatter_required_fields():
    fm, _ = _frontmatter_and_body()
    for field in ("name", "description", "version", "author", "license", "platforms"):
        assert field in fm, f"missing frontmatter field: {field}"
    assert fm["name"] == "qenex-ops"
    assert "abdulrahman305" in fm["author"]
    assert not fm["author"].startswith("Hermes Agent")


def test_description_hardline():
    fm, _ = _frontmatter_and_body()
    desc = fm["description"]
    assert len(desc) <= 60
    assert desc.endswith(".")


def test_setup_tick_split():
    _, body = _frontmatter_and_body()
    assert "Setup (foreground, once)" in body
    assert "Tick (each scheduled run)" in body
    assert "cronjob(action=" in body
    assert "Do not schedule until one foreground fetch works" in body


def test_classify_lab_license_is_revenue_not_spend():
    mod = load_module()
    item = {
        "from": "pi@example.ac.uk",
        "subject": "Academic license",
        "body": "We want to purchase a license for quantum chemistry on QENEX Lab.",
    }
    result = mod.classify(item)
    assert result.kind == "lab_license"
    assert result.send is False
    assert result.spend is False


def test_classify_buy_ads_is_spend_refuse():
    mod = load_module()
    result = mod.classify({"body": "Please buy ads and run a paid campaign for the lab."})
    assert result.kind == "spend_refuse"
    assert result.send is False
    assert result.spend is False


def test_classify_pulse_stays_archived():
    mod = load_module()
    result = mod.classify({"subject": "QENEX Pulse third-party-risk renewal"})
    assert result.kind == "pulse_archive"


def test_classify_human_gate_for_filings():
    mod = load_module()
    result = mod.classify({"body": "Please file the Companies House confirmation statement."})
    assert result.kind == "human_gate"


def test_tick_drafts_without_sending(hermes_env):
    mod = load_module()
    home = hermes_env
    mod.setup(home=home, create_cron=False)
    mod.enqueue(
        home=home,
        sender="pi@example.ac.uk",
        subject="Lab license",
        body="Our chemistry group wants a quantum chemistry academic license.",
        item_id="lead-1",
    )
    summary = mod.tick(home=home)
    assert summary["actionable"] == 1
    assert summary["auto_send"] is False
    assert summary["spend_allowed"] is False
    draft = json.loads((home / "qenex-ops" / "drafts" / "lead-1.json").read_text(encoding="utf-8"))
    assert draft["ops"]["send"] is False
    assert draft["ops"]["kind"] == "lab_license"
    assert "lab.qenex.ai" in draft["ops"]["draft"]


def test_tick_refuses_spend_and_does_not_draft_sendable(hermes_env):
    mod = load_module()
    home = hermes_env
    mod.setup(home=home, create_cron=False)
    mod.enqueue(
        home=home,
        sender="ops@qenex.ai",
        subject="Growth",
        body="Buy ads and hire a salesperson this week.",
        item_id="spend-1",
    )
    summary = mod.tick(home=home)
    assert summary["items"][0]["kind"] == "spend_refuse"
    refused = json.loads((home / "qenex-ops" / "refused" / "spend-1.json").read_text(encoding="utf-8"))
    assert refused["ops"]["send"] is False
    assert "draft" not in refused["ops"]
    assert not (home / "qenex-ops" / "drafts" / "spend-1.json").exists()


def test_ledger_invariants_override_file(hermes_env):
    mod = load_module()
    home = hermes_env
    mod.setup(home=home, create_cron=False)
    ledger_path = home / "qenex-ops" / "ledger.json"
    payload = json.loads(ledger_path.read_text(encoding="utf-8"))
    payload["auto_send"] = True
    payload["spend_allowed"] = True
    payload["product"] = "pulse"
    ledger_path.write_text(json.dumps(payload), encoding="utf-8")
    mod.tick(home=home)
    restored = json.loads(ledger_path.read_text(encoding="utf-8"))
    assert restored["auto_send"] is False
    assert restored["spend_allowed"] is False
    assert restored["product"] == "lab"


def test_empty_tick_is_silent(hermes_env, capsys):
    mod = load_module()
    home = hermes_env
    mod.setup(home=home, create_cron=False)
    exit_code = mod.main(["--home", str(home), "tick"])
    assert exit_code == 0
    assert capsys.readouterr().out == ""


def test_setup_creates_no_agent_cron_job(hermes_env):
    mod = load_module()
    home = hermes_env
    receipt = mod.setup(home=home, schedule="every 30m", create_cron=True)
    assert receipt["invariants"]["no_agent"] is True
    assert receipt["cron"]["created"] is True
    assert receipt["cron"]["no_agent"] is True
    script = Path(receipt["script"])
    assert script == home / "scripts" / "qenex_ops.py"
    assert script.is_file()

    from cron.jobs import list_jobs

    jobs = list_jobs(include_disabled=True)
    assert len(jobs) == 1
    assert jobs[0]["name"] == "qenex-ops-tick"
    assert jobs[0]["no_agent"] is True
    assert jobs[0]["script"] == "qenex_ops.py"

    again = mod.setup(home=home, create_cron=True)
    assert again["cron"]["created"] is False
    assert len(list_jobs(include_disabled=True)) == 1
