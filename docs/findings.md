# Findings

## GitHub Copilot SDK Technical Preview

- Link: https://github.blog/changelog/2026-01-14-copilot-sdk-in-technical-preview/
- Relevance: Confirms SDK is available in technical preview and suitable for custom PR-Agent backend integration.

The changelog establishes that Copilot SDK is now a supported programmable path (Python included), which enables
replacing direct provider calls with Copilot-managed sessions while keeping automation on GitHub-hosted compute.

## GitHub Copilot SDK Documentation

- Link: https://github.com/github/copilot-sdk
- Relevance: Defines authentication, model/session config, and backend deployment patterns used in this integration.

The SDK docs directly provide the integration model used here: Python `CopilotClient`, non-interactive token auth via
`COPILOT_GITHUB_TOKEN`, configurable session options (model/reasoning/tools/provider), and server-side usage patterns
appropriate for GitHub Actions-based automation.
