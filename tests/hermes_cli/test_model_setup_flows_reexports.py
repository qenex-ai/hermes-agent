"""The ``model_setup_flows`` facade must re-export the Bedrock flows ``main.py`` needs.

``hermes_cli/main.py`` pulls the ``_model_flow_*`` wizard callables out of the
:mod:`hermes_cli.model_setup_flows` facade in one block (so test monkeypatches
on ``hermes_cli.main._model_flow_*`` keep resolving). When the compat-shim
cleanup dropped the Bedrock re-exports it removed ``_model_flow_bedrock_api_key``
from the facade while ``main.py`` still imported it from there, so importing the
CLI died at startup with ``ImportError: cannot import name
'_model_flow_bedrock_api_key'``.

These lock the contract between the facade, its Bedrock sibling, and the CLI
entrypoint that consumes both.
"""

import importlib

import hermes_cli.model_setup_flows as facade
import hermes_cli.model_setup_flows_bedrock as bedrock


def test_cli_main_imports_without_error():
    """Importing the CLI entrypoint must not raise (the startup crash's seam)."""
    module = importlib.import_module("hermes_cli.main")
    assert hasattr(module, "_model_flow_bedrock_api_key")


def test_facade_reexports_bedrock_flows_as_the_sibling_definitions():
    assert facade._model_flow_bedrock_api_key is bedrock._model_flow_bedrock_api_key
    assert facade._model_flow_bedrock is bedrock._model_flow_bedrock
