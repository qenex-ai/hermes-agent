"""Tests for agent/video_gen_registry.py — provider registration & active lookup."""

from __future__ import annotations

import pytest

from agent import video_gen_registry
from agent.video_gen_provider import VideoGenProvider


class _FakeProvider(VideoGenProvider):
    def __init__(self, name: str, available: bool = True):
        self._name = name
        self._available = available

    @property
    def name(self) -> str:
        return self._name

    def is_available(self) -> bool:
        return self._available

    def generate(self, prompt, **kw):
        return {"success": True, "video": f"{self._name}://{prompt}"}


@pytest.fixture(autouse=True)
def _reset_registry():
    video_gen_registry._reset_for_tests()
    yield
    video_gen_registry._reset_for_tests()


class TestRegisterProvider:


    def test_rejects_empty_name(self):
        class Empty(VideoGenProvider):
            @property
            def name(self) -> str:
                return ""

            def generate(self, prompt, **kw):
                return {}

        with pytest.raises(ValueError):
            video_gen_registry.register_provider(Empty())


    def test_list_is_sorted(self):
        video_gen_registry.register_provider(_FakeProvider("zeta"))
        video_gen_registry.register_provider(_FakeProvider("alpha"))
        names = [p.name for p in video_gen_registry.list_providers()]
        assert names == ["alpha", "zeta"]


class TestGetActiveProvider:



    def test_single_metered_available_does_not_autoresolve(self, tmp_path, monkeypatch):
        """A box with only DeepInfra credentials must not auto-spend them.
        Pick the backend in ``hermes tools``."""
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        video_gen_registry.register_provider(_FakeProvider("fal", available=False))
        video_gen_registry.register_provider(_FakeProvider("xai", available=False))
        video_gen_registry.register_provider(_FakeProvider("deepinfra", available=True))
        assert video_gen_registry.get_active_provider() is None

    def test_single_unmetered_available_still_autoresolves(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        video_gen_registry.register_provider(_FakeProvider("comfyui", available=True))
        video_gen_registry.register_provider(_FakeProvider("fal", available=False))
        active = video_gen_registry.get_active_provider()
        assert active is not None and active.name == "comfyui"


    def test_unknown_explicit_config_fails_closed(self, tmp_path, monkeypatch):
        """A typo must not silently route a paid request to another backend."""
        import yaml

        monkeypatch.setenv("HERMES_HOME", str(tmp_path))
        (tmp_path / "config.yaml").write_text(
            yaml.safe_dump({"video_gen": {"provider": "ghost"}})
        )
        video_gen_registry.register_provider(_FakeProvider("only"))
        assert video_gen_registry.get_active_provider() is None
