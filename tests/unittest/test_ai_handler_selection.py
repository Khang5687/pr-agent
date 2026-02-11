from pr_agent.agent.pr_agent import PRAgent
from pr_agent.algo.ai_handlers.copilot_sdk_ai_handler import CopilotSDKAIHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.config_loader import get_settings


def test_default_ai_handler_is_litellm():
    settings = get_settings(use_context=False)
    original = settings.config.get("ai_handler", None)
    try:
        settings.set("config.ai_handler", "litellm")
        agent = PRAgent()
        assert agent.ai_handler == LiteLLMAIHandler
    finally:
        settings.set("config.ai_handler", original if original is not None else "litellm")


def test_ai_handler_can_switch_to_copilot_sdk():
    settings = get_settings(use_context=False)
    original = settings.config.get("ai_handler", None)
    try:
        settings.set("config.ai_handler", "copilot_sdk")
        agent = PRAgent()
        assert agent.ai_handler == CopilotSDKAIHandler
    finally:
        settings.set("config.ai_handler", original if original is not None else "litellm")


def test_unknown_ai_handler_falls_back_to_litellm():
    settings = get_settings(use_context=False)
    original = settings.config.get("ai_handler", None)
    try:
        settings.set("config.ai_handler", "does-not-exist")
        agent = PRAgent()
        assert agent.ai_handler == LiteLLMAIHandler
    finally:
        settings.set("config.ai_handler", original if original is not None else "litellm")
