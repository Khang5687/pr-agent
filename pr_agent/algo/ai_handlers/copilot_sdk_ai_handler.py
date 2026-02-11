import asyncio
import json
import os
import shutil
import time
from typing import Any

from pr_agent.algo.ai_handlers.base_ai_handler import BaseAiHandler
from pr_agent.config_loader import get_settings
from pr_agent.log import get_logger

try:
    import openai
except Exception:  # pragma: no cover
    openai = None


class CopilotSDKAIHandler(BaseAiHandler):
    """
    AI handler backed by GitHub Copilot SDK (python package: github-copilot-sdk).
    """

    _client = None
    _client_lock: asyncio.Lock | None = None
    _models_cache: list[dict[str, Any]] | None = None
    _models_cache_timestamp: float = 0.0
    _models_cache_ttl_seconds: float = 300.0
    _models_cache_lock: asyncio.Lock | None = None

    def __init__(self):
        self.main_pr_language = "unknown"

    @property
    def deployment_id(self):
        return None

    @classmethod
    def _get_client_lock(cls) -> asyncio.Lock:
        if cls._client_lock is None:
            cls._client_lock = asyncio.Lock()
        return cls._client_lock

    @classmethod
    def _get_models_cache_lock(cls) -> asyncio.Lock:
        if cls._models_cache_lock is None:
            cls._models_cache_lock = asyncio.Lock()
        return cls._models_cache_lock

    def _get_setting(self, key: str, default: Any = None) -> Any:
        return get_settings().get(f"copilot.{key}", default)

    @staticmethod
    def _coerce_bool(value: Any, default: bool) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @staticmethod
    def _coerce_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return []
            if stripped.startswith("["):
                try:
                    parsed = json.loads(stripped)
                    if isinstance(parsed, list):
                        return [str(v).strip() for v in parsed if str(v).strip()]
                except json.JSONDecodeError:
                    pass
            return [v.strip() for v in stripped.split(",") if v.strip()]
        return [str(value).strip()]

    async def _get_or_start_client(self):
        if self.__class__._client is not None:
            return self.__class__._client

        async with self.__class__._get_client_lock():
            if self.__class__._client is not None:
                return self.__class__._client

            try:
                from copilot import CopilotClient
            except Exception as e:
                raise ImportError(
                    "Copilot SDK is not installed. Install with: pip install github-copilot-sdk"
                ) from e

            options = {}
            str_fields = ["cli_path", "cli_url", "cwd", "log_level", "github_token"]
            for field in str_fields:
                value = self._get_setting(field, None)
                if value not in (None, ""):
                    if field == "cli_path":
                        cli_path = str(value)
                        resolved_cli_path = cli_path
                        if os.path.isabs(cli_path):
                            exists = os.path.exists(cli_path)
                        else:
                            resolved_cli_path = shutil.which(cli_path) or ""
                            exists = bool(resolved_cli_path)
                        if not exists:
                            get_logger().warning(
                                f"Configured copilot.cli_path '{cli_path}' was not found. "
                                "Falling back to bundled Copilot CLI."
                            )
                            continue
                        value = resolved_cli_path
                    options[field] = value

            if "github_token" not in options:
                env_github_token = os.getenv("COPILOT_GITHUB_TOKEN") or os.getenv("GITHUB_TOKEN")
                if env_github_token:
                    options["github_token"] = env_github_token

            cli_url = options.get("cli_url")
            options["auto_start"] = self._coerce_bool(self._get_setting("auto_start", True), True)
            options["auto_restart"] = self._coerce_bool(self._get_setting("auto_restart", True), True)
            if cli_url:
                options.pop("cli_path", None)
                options.pop("github_token", None)
            else:
                maybe_port = self._get_setting("port", None)
                if maybe_port not in (None, ""):
                    options["port"] = int(maybe_port)
                options["use_stdio"] = self._coerce_bool(self._get_setting("use_stdio", True), True)
                options["use_logged_in_user"] = self._coerce_bool(
                    self._get_setting("use_logged_in_user", True),
                    True,
                )

            client = CopilotClient(options)
            await client.start()
            self.__class__._client = client
            return self.__class__._client

    @staticmethod
    def _normalize_model_info(model: Any) -> dict[str, Any]:
        capabilities = getattr(model, "capabilities", None)
        supports = getattr(capabilities, "supports", None) if capabilities else None
        limits = getattr(capabilities, "limits", None) if capabilities else None
        policy = getattr(model, "policy", None)
        billing = getattr(model, "billing", None)
        return {
            "id": str(getattr(model, "id", "") or ""),
            "name": str(getattr(model, "name", "") or ""),
            "policy_state": str(getattr(policy, "state", "") or ""),
            "billing_multiplier": getattr(billing, "multiplier", None),
            "supports_vision": getattr(supports, "vision", None),
            "supports_reasoning_effort": getattr(supports, "reasoning_effort", None),
            "max_prompt_tokens": getattr(limits, "max_prompt_tokens", None),
            "max_context_window_tokens": getattr(limits, "max_context_window_tokens", None),
            "supported_reasoning_efforts": getattr(model, "supported_reasoning_efforts", None),
            "default_reasoning_effort": getattr(model, "default_reasoning_effort", None),
        }

    @classmethod
    async def fetch_models(cls, force_refresh: bool = False) -> list[dict[str, Any]]:
        async with cls._get_models_cache_lock():
            now = time.time()
            if (
                not force_refresh
                and cls._models_cache is not None
                and (now - cls._models_cache_timestamp) < cls._models_cache_ttl_seconds
            ):
                return list(cls._models_cache)

            handler = cls()
            client = await handler._get_or_start_client()
            models = await client.list_models()
            normalized_models = [cls._normalize_model_info(model) for model in models]
            normalized_models.sort(key=lambda item: item.get("id", ""))
            cls._models_cache = normalized_models
            cls._models_cache_timestamp = now
            return list(normalized_models)

    @classmethod
    async def fetch_model_ids(cls, force_refresh: bool = False) -> list[str]:
        models = await cls.fetch_models(force_refresh=force_refresh)
        return [m["id"] for m in models if m.get("id")]

    def _build_session_config(self, model: str, system: str) -> dict:
        session_config: dict[str, Any] = {"model": model}

        reasoning_effort = get_settings().config.get("reasoning_effort", None)
        if reasoning_effort:
            session_config["reasoning_effort"] = reasoning_effort

        system_message_mode = self._get_setting("system_message_mode", "append")
        if system:
            session_config["system_message"] = {"mode": system_message_mode, "content": system}

        available_tools = self._coerce_list(self._get_setting("available_tools", []))
        excluded_tools = self._coerce_list(self._get_setting("excluded_tools", []))
        if available_tools:
            session_config["available_tools"] = available_tools
        elif excluded_tools:
            session_config["excluded_tools"] = excluded_tools

        working_directory = self._get_setting("working_directory", None)
        if working_directory:
            session_config["working_directory"] = working_directory

        infinite_sessions_enabled = self._coerce_bool(
            self._get_setting("infinite_sessions_enabled", False),
            False,
        )
        infinite_sessions: dict[str, Any] = {"enabled": infinite_sessions_enabled}
        if infinite_sessions_enabled:
            bg_threshold = self._get_setting("background_compaction_threshold", None)
            buffer_threshold = self._get_setting("buffer_exhaustion_threshold", None)
            if bg_threshold is not None:
                infinite_sessions["background_compaction_threshold"] = float(bg_threshold)
            if buffer_threshold is not None:
                infinite_sessions["buffer_exhaustion_threshold"] = float(buffer_threshold)
        session_config["infinite_sessions"] = infinite_sessions

        provider_type = self._get_setting("provider_type", None)
        provider_base_url = self._get_setting("provider_base_url", None)
        if provider_type and provider_base_url:
            provider: dict[str, Any] = {"type": provider_type, "base_url": provider_base_url}
            provider_api_key = self._get_setting("provider_api_key", None)
            provider_bearer_token = self._get_setting("provider_bearer_token", None)
            provider_wire_api = self._get_setting("provider_wire_api", None)
            provider_azure_api_version = self._get_setting("provider_azure_api_version", None)
            if provider_api_key:
                provider["api_key"] = provider_api_key
            if provider_bearer_token:
                provider["bearer_token"] = provider_bearer_token
            if provider_wire_api:
                provider["wire_api"] = provider_wire_api
            if provider_azure_api_version:
                provider["azure"] = {"api_version": provider_azure_api_version}
            session_config["provider"] = provider

        mcp_servers = self._get_setting("mcp_servers", None)
        if isinstance(mcp_servers, dict) and mcp_servers:
            session_config["mcp_servers"] = mcp_servers

        skill_directories = self._coerce_list(self._get_setting("skill_directories", []))
        if skill_directories:
            session_config["skill_directories"] = skill_directories

        return session_config

    async def chat_completion(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float = 0.2,
        img_path: str = None,
    ):
        _ = temperature  # Copilot SDK does not expose temperature in SessionConfig.

        client = await self._get_or_start_client()
        timeout = float(self._get_setting("timeout", get_settings().config.ai_timeout))
        session = None
        try:
            session = await client.create_session(self._build_session_config(model=model, system=system))
            prompt = user
            if img_path:
                prompt = (
                    f"{user}\n\nImage URL context (external): {img_path}\n"
                    "If you cannot access this URL, continue based on code context only."
                )
            response = await session.send_and_wait({"prompt": prompt}, timeout=timeout)
            resp = ""
            if response and getattr(response, "data", None):
                resp = getattr(response.data, "content", "") or ""
            finish_reason = "completed" if resp else "error"
            return resp, finish_reason
        except Exception as e:
            get_logger().warning(f"Copilot SDK inference failed: {e}")
            if openai:
                raise openai.APIError from e
            raise
        finally:
            if session:
                try:
                    await session.destroy()
                except Exception:
                    pass
