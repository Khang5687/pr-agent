import pytest

from pr_agent.agent.pr_agent import PRAgent, command2class
from pr_agent.algo.ai_handlers.copilot_sdk_ai_handler import CopilotSDKAIHandler
from pr_agent.config_loader import get_settings


@pytest.mark.asyncio
async def test_inline_model_override_applies_for_single_command(monkeypatch):
    settings = get_settings(use_context=False)
    original_model = settings.config.get("model")
    original_fallback_models = settings.config.get("fallback_models")
    original_handler = settings.config.get("ai_handler")
    captured: dict = {}

    class DummyReviewTool:
        def __init__(self, pr_url, ai_handler=None, args=None):
            captured["pr_url"] = pr_url
            captured["args"] = args
            captured["model_in_init"] = settings.config.get("model")

        async def run(self):
            captured["model_in_run"] = settings.config.get("model")

    try:
        settings.set("config.ai_handler", "litellm")
        settings.set("config.model", "gpt-5.2-2025-12-11")
        settings.set("config.fallback_models", ["o4-mini"])

        monkeypatch.setitem(command2class, "review", DummyReviewTool)
        monkeypatch.setattr("pr_agent.agent.pr_agent.apply_repo_settings", lambda *_: None)

        result = await PRAgent().handle_request("https://example.com/pr/1", "/review gpt-5.2-codex")

        assert result is True
        assert captured["args"] == []
        assert captured["model_in_init"] == "gpt-5.2-codex"
        assert captured["model_in_run"] == "gpt-5.2-codex"
    finally:
        settings.set("config.model", original_model)
        settings.set("config.fallback_models", original_fallback_models)
        settings.set("config.ai_handler", original_handler)

    assert settings.config.get("model") == original_model
    assert settings.config.get("fallback_models") == original_fallback_models


@pytest.mark.asyncio
async def test_non_model_first_arg_is_preserved(monkeypatch):
    settings = get_settings(use_context=False)
    original_model = settings.config.get("model")
    original_handler = settings.config.get("ai_handler")
    captured: dict = {}

    class DummyAskTool:
        def __init__(self, pr_url, ai_handler=None, args=None):
            captured["args"] = args
            captured["model_in_init"] = settings.config.get("model")

        async def run(self):
            captured["model_in_run"] = settings.config.get("model")

    try:
        settings.set("config.ai_handler", "litellm")
        settings.set("config.model", "gpt-5.2-2025-12-11")
        monkeypatch.setitem(command2class, "ask", DummyAskTool)
        monkeypatch.setattr("pr_agent.agent.pr_agent.apply_repo_settings", lambda *_: None)

        result = await PRAgent().handle_request("https://example.com/pr/1", '/ask "why is this failing?"')

        assert result is True
        assert captured["args"] == ["why is this failing?"]
        assert captured["model_in_init"] == "gpt-5.2-2025-12-11"
        assert captured["model_in_run"] == "gpt-5.2-2025-12-11"
    finally:
        settings.set("config.model", original_model)
        settings.set("config.ai_handler", original_handler)


@pytest.mark.asyncio
async def test_inline_model_override_with_copilot_when_model_list_fails(monkeypatch):
    settings = get_settings(use_context=False)
    original_model = settings.config.get("model")
    original_fallback_models = settings.config.get("fallback_models")
    original_handler = settings.config.get("ai_handler")
    captured: dict = {}

    class DummyReviewTool:
        def __init__(self, pr_url, ai_handler=None, args=None):
            captured["args"] = args
            captured["model_in_init"] = settings.config.get("model")

        async def run(self):
            captured["model_in_run"] = settings.config.get("model")

    async def fail_fetch_model_ids(*_args, **_kwargs):
        raise RuntimeError("Not authenticated")

    try:
        settings.set("config.ai_handler", "copilot_sdk")
        settings.set("config.model", "gpt-5.2")
        settings.set("config.fallback_models", ["gemini-3-pro-preview"])

        monkeypatch.setitem(command2class, "review", DummyReviewTool)
        monkeypatch.setattr("pr_agent.agent.pr_agent.apply_repo_settings", lambda *_: None)
        monkeypatch.setattr(CopilotSDKAIHandler, "fetch_model_ids", fail_fetch_model_ids)

        result = await PRAgent().handle_request("https://example.com/pr/1", "/review claude-4.5-sonnet")

        assert result is True
        assert captured["args"] == []
        assert captured["model_in_init"] == "claude-4.5-sonnet"
        assert captured["model_in_run"] == "claude-4.5-sonnet"
    finally:
        settings.set("config.model", original_model)
        settings.set("config.fallback_models", original_fallback_models)
        settings.set("config.ai_handler", original_handler)
