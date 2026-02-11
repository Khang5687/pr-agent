from datetime import datetime, timezone
from functools import partial

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.copilot_sdk_ai_handler import CopilotSDKAIHandler
from pr_agent.config_loader import get_settings
from pr_agent.git_providers import get_git_provider
from pr_agent.log import get_logger


class PRModels:
    """
    List available Copilot models for the current GitHub identity.
    """

    def __init__(
        self,
        pr_url: str,
        args=None,
        ai_handler: partial[BaseAiHandler,] = CopilotSDKAIHandler,
    ):
        self.git_provider = get_git_provider()(pr_url)
        self.args = args or []
        self.ai_handler = ai_handler
        self.force_refresh = any(str(arg).strip().lower() in {"--refresh", "-r"} for arg in self.args)

    @staticmethod
    def _format_models_comment(models: list[dict]) -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            "## Available Copilot Models",
            "",
            f"Fetched live from Copilot API at `{timestamp}`.",
            "",
            "Use them inline in any command:",
            "- `/review gpt-5.2-codex`",
            "- `/ask gpt-5.2-codex Why was this design chosen?`",
            "",
        ]
        if not models:
            lines.append("No models were returned by Copilot API for this account.")
            return "\n".join(lines)

        for model in models:
            model_id = model.get("id", "")
            model_name = model.get("name", "")
            policy_state = model.get("policy_state", "unknown") or "unknown"
            supports_vision = model.get("supports_vision")
            supports_reasoning = model.get("supports_reasoning_effort")
            context_window = model.get("max_context_window_tokens")
            capabilities = []
            if supports_vision is True:
                capabilities.append("vision")
            if supports_reasoning is True:
                capabilities.append("reasoning")
            capabilities_str = ", ".join(capabilities) if capabilities else "standard"
            context_str = f", ctx={context_window}" if context_window else ""
            name_str = f" - {model_name}" if model_name and model_name != model_id else ""
            lines.append(
                f"- `{model_id}`{name_str} (policy={policy_state}, {capabilities_str}{context_str})"
            )
        return "\n".join(lines)

    async def run(self):
        get_logger().info("Listing Copilot models")
        comment = ""
        try:
            models = await CopilotSDKAIHandler.fetch_models(force_refresh=self.force_refresh)
            comment = self._format_models_comment(models)
        except Exception as e:
            get_logger().error(f"Failed to list Copilot models: {e}")
            comment = (
                "## Available Copilot Models\n\n"
                "Failed to fetch models from Copilot API.\n\n"
                "Ensure:\n"
                "- `config.ai_handler=\"copilot_sdk\"`\n"
                "- `COPILOT_GITHUB_TOKEN` is configured\n"
                "- `copilot.github_token` is set (or allow fallback from `COPILOT_GITHUB_TOKEN`)\n"
                "- Copilot access is active for this account"
            )

        if get_settings().config.publish_output:
            self.git_provider.publish_comment(comment)
            self.git_provider.remove_initial_comment()
        return comment
