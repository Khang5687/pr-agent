#!/bin/bash
set -euo pipefail

ACTION_REPOSITORY="${GITHUB_ACTION_REPOSITORY:-Khang5687/pr-agent}"
ACTION_REF="${GITHUB_ACTION_REF:-main}"
PR_AGENT_GIT_REPOSITORY="${PR_AGENT_GIT_REPOSITORY:-${ACTION_REPOSITORY}}"
PR_AGENT_GIT_REF="${PR_AGENT_GIT_REF:-${ACTION_REF}}"

echo "Installing PR-Agent from ${PR_AGENT_GIT_REPOSITORY}@${PR_AGENT_GIT_REF}"
python -m pip install --no-cache-dir "git+https://github.com/${PR_AGENT_GIT_REPOSITORY}.git@${PR_AGENT_GIT_REF}"

python -m pr_agent.servers.github_action_runner
