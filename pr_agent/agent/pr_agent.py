import shlex
from functools import partial

from pr_agent.algo import MAX_TOKENS
from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.algo.ai_handlers.copilot_sdk_ai_handler import CopilotSDKAIHandler
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler
from pr_agent.algo.cli_args import CliArgs
from pr_agent.algo.utils import update_settings_from_args
from pr_agent.config_loader import get_settings
from pr_agent.git_providers.utils import apply_repo_settings
from pr_agent.log import get_logger
from pr_agent.tools.pr_add_docs import PRAddDocs
from pr_agent.tools.pr_code_suggestions import PRCodeSuggestions
from pr_agent.tools.pr_config import PRConfig
from pr_agent.tools.pr_description import PRDescription
from pr_agent.tools.pr_generate_labels import PRGenerateLabels
from pr_agent.tools.pr_help_docs import PRHelpDocs
from pr_agent.tools.pr_help_message import PRHelpMessage
from pr_agent.tools.pr_line_questions import PR_LineQuestions
from pr_agent.tools.pr_models import PRModels
from pr_agent.tools.pr_questions import PRQuestions
from pr_agent.tools.pr_reviewer import PRReviewer
from pr_agent.tools.pr_similar_issue import PRSimilarIssue
from pr_agent.tools.pr_update_changelog import PRUpdateChangelog

command2class = {
    "auto_review": PRReviewer,
    "answer": PRReviewer,
    "review": PRReviewer,
    "review_pr": PRReviewer,
    "describe": PRDescription,
    "describe_pr": PRDescription,
    "improve": PRCodeSuggestions,
    "improve_code": PRCodeSuggestions,
    "ask": PRQuestions,
    "ask_question": PRQuestions,
    "ask_line": PR_LineQuestions,
    "update_changelog": PRUpdateChangelog,
    "config": PRConfig,
    "settings": PRConfig,
    "help": PRHelpMessage,
    "models": PRModels,
    "similar_issue": PRSimilarIssue,
    "add_docs": PRAddDocs,
    "generate_labels": PRGenerateLabels,
    "help_docs": PRHelpDocs,
}

commands = list(command2class.keys())

KNOWN_MODEL_PREFIXES = (
    "gpt-",
    "claude-",
    "o1",
    "o3",
    "o4",
    "gemini-",
    "grok-",
    "deepseek",
    "mistral",
    "llama",
    "qwen",
    "codestral",
)


def _resolve_ai_handler(
    ai_handler: partial[BaseAiHandler,] | None = None,
) -> partial[BaseAiHandler,]:
    if ai_handler is not None:
        return ai_handler

    configured_handler = str(get_settings().config.get("ai_handler", "litellm")).strip().lower()
    handlers = {
        "litellm": LiteLLMAIHandler,
        "copilot": CopilotSDKAIHandler,
        "copilot_sdk": CopilotSDKAIHandler,
    }
    selected_handler = handlers.get(configured_handler)
    if selected_handler:
        return selected_handler

    get_logger().warning(
        f"Unknown config.ai_handler '{configured_handler}'. Falling back to 'litellm'."
    )
    return LiteLLMAIHandler


class PRAgent:
    def __init__(self, ai_handler: partial[BaseAiHandler,] | None = None):
        self.ai_handler = _resolve_ai_handler(ai_handler)

    @staticmethod
    def _looks_like_model_name(value: str) -> bool:
        if not value:
            return False
        candidate = value.strip().lower()
        if not candidate or candidate.startswith("--") or " " in candidate:
            return False
        if candidate in MAX_TOKENS:
            return True
        if candidate.startswith(KNOWN_MODEL_PREFIXES):
            return True
        return "/" in candidate and "-" in candidate

    async def _extract_model_override(self, args: list[str]) -> tuple[str | None, list[str]]:
        if not args:
            return None, args
        candidate = str(args[0]).strip()
        if not candidate or candidate.startswith("--"):
            return None, args

        # Prefer an exact match from Copilot API when using the Copilot SDK handler.
        configured_handler = str(get_settings().config.get("ai_handler", "litellm")).strip().lower()
        if configured_handler in {"copilot", "copilot_sdk"}:
            try:
                copilot_models = await CopilotSDKAIHandler.fetch_model_ids()
                if candidate in copilot_models:
                    return candidate, args[1:]
            except Exception as e:
                get_logger().debug(f"Failed to fetch Copilot models for inline model override detection: {e}")

        if self._looks_like_model_name(candidate):
            return candidate, args[1:]
        return None, args

    async def _handle_request(self, pr_url, request, notify=None) -> bool:
        # First, apply repo specific settings if exists
        apply_repo_settings(pr_url)

        # Then, apply user specific settings if exists
        if isinstance(request, str):
            request = request.replace("'", "\\'")
            lexer = shlex.shlex(request, posix=True)
            lexer.whitespace_split = True
            action, *args = list(lexer)
        else:
            action, *args = request

        model_override = None
        model_args = args
        try:
            model_override, model_args = await self._extract_model_override(args)
            if model_override:
                get_logger().info(f"Using inline model override: {model_override}")
        except Exception as e:
            get_logger().debug(f"Failed to parse inline model override: {e}")

        # validate args
        is_valid, arg = CliArgs.validate_user_args(model_args)
        if not is_valid:
            get_logger().error(
                f"CLI argument for param '{arg}' is forbidden. Use instead a configuration file."
            )
            return False

        # Update settings from args
        args = update_settings_from_args(model_args)
        original_model = get_settings().config.get("model", None)
        original_fallback_models = get_settings().config.get("fallback_models", None)
        if model_override:
            # Inline command model should take precedence over env/repo defaults for this request.
            get_settings().set("config.model", model_override)
            get_settings().set("config.fallback_models", [])

        # Append the response language in the extra instructions
        response_language = get_settings().config.get('response_language', 'en-us')
        if response_language.lower() != 'en-us':
            get_logger().info(f'User has set the response language to: {response_language}')
            for key in get_settings():
                setting = get_settings().get(key)
                if str(type(setting)) == "<class 'dynaconf.utils.boxing.DynaBox'>":
                    if hasattr(setting, 'extra_instructions'):
                        current_extra_instructions = setting.extra_instructions
                        
                        # Define the language-specific instruction and the separator
                        lang_instruction_text = f"Your response MUST be written in the language corresponding to locale code: '{response_language}'. This is crucial."
                        separator_text = "\n======\n\nIn addition, "

                        # Check if the specific language instruction is already present to avoid duplication
                        if lang_instruction_text not in str(current_extra_instructions):
                            if current_extra_instructions: # If there's existing text
                                setting.extra_instructions = str(current_extra_instructions) + separator_text + lang_instruction_text
                            else: # If extra_instructions was None or empty
                                setting.extra_instructions = lang_instruction_text
                        # If lang_instruction_text is already present, do nothing.

        action = action.lstrip("/").lower()
        if action not in command2class:
            get_logger().warning(f"Unknown command: {action}")
            if model_override:
                get_settings().set("config.model", original_model)
                get_settings().set("config.fallback_models", original_fallback_models)
            return False
        try:
            with get_logger().contextualize(command=action, pr_url=pr_url):
                get_logger().info("PR-Agent request handler started", analytics=True)
                if action == "answer":
                    if notify:
                        notify()
                    await PRReviewer(pr_url, is_answer=True, args=args, ai_handler=self.ai_handler).run()
                elif action == "auto_review":
                    await PRReviewer(pr_url, is_auto=True, args=args, ai_handler=self.ai_handler).run()
                elif action in command2class:
                    if notify:
                        notify()

                    await command2class[action](pr_url, ai_handler=self.ai_handler, args=args).run()
                else:
                    return False
                return True
        finally:
            if model_override:
                get_settings().set("config.model", original_model)
                get_settings().set("config.fallback_models", original_fallback_models)

    async def handle_request(self, pr_url, request, notify=None) -> bool:
        try:
            return await self._handle_request(pr_url, request, notify)
        except:
            get_logger().exception("Failed to process the command.")
            return False
