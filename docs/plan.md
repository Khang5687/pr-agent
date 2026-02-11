# PR-Agent + Copilot SDK Plan

## Objective

Run PR-Agent reviews on GitHub-hosted Actions using GitHub Copilot usage (no self-hosted infrastructure).

## Constraints

- Keep current LiteLLM path as default.
- Add Copilot support as an opt-in backend.
- Enable workflow-level configuration through existing `config.*` / section-based env variables.
- Avoid hard dependency on Copilot SDK when the LiteLLM backend is used.

## Implementation Plan

1. Add a Copilot SDK AI handler implementing `BaseAiHandler`.
2. Add runtime backend selection in `PRAgent` via `config.ai_handler`.
3. Extend default configuration with Copilot backend settings.
4. Add a GitHub-hosted workflow that installs Copilot CLI + Copilot SDK and runs PR-Agent with `copilot_sdk`.
5. Update documentation with usage and setup examples.
6. Add unit tests for backend selection behavior.

## Execution Status

- [x] Added `CopilotSDKAIHandler` at `pr_agent/algo/ai_handlers/copilot_sdk_ai_handler.py`.
- [x] Added backend resolver in `pr_agent/agent/pr_agent.py` with `config.ai_handler`.
- [x] Added Copilot config section and `config.ai_handler` default in `pr_agent/settings/configuration.toml`.
- [x] Added workflow `/.github/workflows/pr-agent-copilot-sdk.yaml` for GitHub-hosted execution.
- [x] Converted execution to Docker action path `./github_action/copilot`.
- [x] Updated docs:
  - `docs/docs/installation/github.md`
  - `docs/docs/usage-guide/changing_a_model.md`
- [x] Added unit tests in `tests/unittest/test_ai_handler_selection.py`.

## Notes

- The Copilot backend is opt-in and does not change existing LiteLLM behavior.
- CI users should provide `COPILOT_GITHUB_TOKEN` for non-interactive authentication.
