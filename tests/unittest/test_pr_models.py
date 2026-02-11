import pytest

from pr_agent.config_loader import get_settings
from pr_agent.tools.pr_models import PRModels


@pytest.mark.asyncio
async def test_models_command_publishes_live_copilot_models(monkeypatch):
    published = {"body": None}

    class FakeGitProvider:
        def __init__(self, pr_url):
            self.pr_url = pr_url

        def publish_comment(self, body):
            published["body"] = body

        def remove_initial_comment(self):
            pass

    async def fake_fetch_models(force_refresh=False):
        assert force_refresh is False
        return [
            {
                "id": "gpt-5.2-codex",
                "name": "GPT-5.2 Codex",
                "policy_state": "enabled",
                "supports_vision": True,
                "supports_reasoning_effort": True,
                "max_context_window_tokens": 400000,
            },
            {
                "id": "claude-opus-4.6",
                "name": "Claude Opus 4.6",
                "policy_state": "enabled",
                "supports_vision": True,
                "supports_reasoning_effort": False,
                "max_context_window_tokens": 200000,
            },
        ]

    settings = get_settings(use_context=False)
    original_publish = settings.config.get("publish_output")
    try:
        settings.set("config.publish_output", True)
        monkeypatch.setattr("pr_agent.tools.pr_models.get_git_provider", lambda: FakeGitProvider)
        monkeypatch.setattr(
            "pr_agent.tools.pr_models.CopilotSDKAIHandler.fetch_models",
            fake_fetch_models,
        )

        result = await PRModels("https://example.com/pr/1").run()

        assert "gpt-5.2-codex" in result
        assert "claude-opus-4.6" in result
        assert published["body"] == result
    finally:
        settings.set("config.publish_output", original_publish)


@pytest.mark.asyncio
async def test_models_command_handles_fetch_failure(monkeypatch):
    published = {"body": None}

    class FakeGitProvider:
        def __init__(self, pr_url):
            self.pr_url = pr_url

        def publish_comment(self, body):
            published["body"] = body

        def remove_initial_comment(self):
            pass

    async def fake_fetch_models(force_refresh=False):
        raise RuntimeError("boom")

    settings = get_settings(use_context=False)
    original_publish = settings.config.get("publish_output")
    try:
        settings.set("config.publish_output", True)
        monkeypatch.setattr("pr_agent.tools.pr_models.get_git_provider", lambda: FakeGitProvider)
        monkeypatch.setattr(
            "pr_agent.tools.pr_models.CopilotSDKAIHandler.fetch_models",
            fake_fetch_models,
        )

        result = await PRModels("https://example.com/pr/1").run()

        assert "Failed to fetch models from Copilot API" in result
        assert published["body"] == result
    finally:
        settings.set("config.publish_output", original_publish)
