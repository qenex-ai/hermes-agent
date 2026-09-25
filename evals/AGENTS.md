# evals/ — offline benchmarks and live probes

Applies on top of the root `AGENTS.md`. Hermes’s pytest suite lives under `tests/`; `evals/` holds
**optional** harnesses: deterministic metrics, fake-provider A/B probes, and live model runs that cost
money or need real credentials. Nothing here is imported by the agent at runtime.

## Layout

- **Subdirectory harness** — `README.md` + `runner.py` / `run.py` / `probe.py` (e.g. `compaction/`,
  `codebase_navigability/`, `postmortem/`, `readtool/`, `tool_search/`). Prefer the README’s exact argv.
- **Root scripts** — single-file probes (`*_probe.py`, `*_wire.py`, `*_live.py`, `*_ab.py`) with a
  `Run:` line in the module docstring.
- **Packages** — `evals/__init__.py` enables `python -m evals.<pkg>.…` (notably `postmortem`).

Issue-scoped filenames (`probe_104120.py`, `issue_104359.py`) are historical anchors; new harnesses use
descriptive names unless tied to a tracking issue.

## Dev environment

From repo root with the project venv (same as root `AGENTS.md`):

```bash
source .venv/bin/activate
```

Run scripts as `.venv/bin/python …` from the checkout root so `evals.*` imports resolve. Isolated runs
use a temp `HERMES_HOME` (`mktemp -d`); many probes clear inherited API keys.

## Running harnesses (verified)

**CI-adjacent guardrails** (cheap; use the test runner, not bare `pytest`):

```bash
scripts/run_tests.sh tests/evals/test_codebase_navigability.py
scripts/run_tests.sh evals/compaction/test_region_scoping.py
scripts/run_tests.sh evals/postmortem/tests/test_postmortem_harness.py
```

**Post-mortem A/B** (fake providers unless `--live`):

```bash
python -m evals.postmortem.run --repo .
python -m evals.postmortem.run --repo /path/to/main --compare /path/to/branch
python -m evals.postmortem.run --repo . --live
```

**Codebase navigability** (offline; `tiktoken` + `radon` — see that README):

```bash
uv pip install tiktoken radon
python evals/codebase_navigability/bench.py . head --out /tmp/nav-out
python evals/codebase_navigability/static_metrics.py . head
```

**Compaction recall eval** (needs configured auxiliary provider; real tokens):

```bash
python evals/compaction/runner.py --transcript /path/to/lineage.json --policies current --questions 15 --out /tmp/comp-out
python evals/compaction/report.py /tmp/comp-out
```

**Gateway failure-writer ownership** (offline loopback; positional args):

```bash
.venv/bin/python evals/gateway_failure_ownership/probe.py "$PWD" /tmp/ownership.json
scripts/run_tests.sh -j 1 tests/gateway/test_failure_writer_ownership.py
```

**Tool search live** (paid OpenRouter):

```bash
python3 evals/tool_search/tool_search_livetest.py
python3 evals/tool_search/analyze_livetest.py
```

Forensics on real runs: copy `state.db` first — see `evals/postmortem/README.md` for
`python -m evals.postmortem.forensics.*` modules.

## Conventions

- **OBSERVED vs MODELED** — post-mortem forensics label recomputed DB/log figures vs replay probes; do
  not add modeled numbers to observed totals (`evals/postmortem/README.md`).
- **Receipts** — probes write JSON to a path you pass; CI tests shell out and assert receipts
  (`tests/gateway/test_failure_writer_ownership.py`).
- **Regression tests** for product code belong in `tests/<mirror-source-tree>/`. Add an eval for
  cross-checkout A/B, cost/recall measurement, or heavy wire probes.

## Pitfalls

- **`scripts/run_tests.sh` does not run all of `evals/`** — only explicit paths (plus a few gateway tests
  that invoke an eval script). Do not assume `scripts/run_tests.sh` exercises every file here.
- **`--live` and `*_livetest.py`** spend provider credits; `OPENROUTER_API_KEY` / `HERMES_HOME` secrets
  must be set (`evals/tool_search/README.md`).
- **Never point forensics at a live `~/.hermes/state.db`** — copy or `.backup` while idle
  (`evals/postmortem/README.md`, `evals/compaction/README.md`).
- **`runtime_bench.py` pins `PYTHONPATH` to the tree under test** — an editable install of another
  checkout silently poisons import-time numbers (`evals/codebase_navigability/README.md`).
- **Many probes have no `--help`** and require positional arguments; read the subdirectory README or the
  top-of-file `Run:` line before invoking.
