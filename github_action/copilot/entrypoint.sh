#!/bin/bash
set -euo pipefail

ACTION_REPOSITORY="${GITHUB_ACTION_REPOSITORY:-Khang5687/pr-agent}"
ACTION_REF="${GITHUB_ACTION_REF:-main}"
PR_AGENT_GIT_REPOSITORY="${PR_AGENT_GIT_REPOSITORY:-${ACTION_REPOSITORY}}"
PR_AGENT_GIT_REF="${PR_AGENT_GIT_REF:-${ACTION_REF}}"

set +e
python - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

event_name = os.environ.get("GITHUB_EVENT_NAME", "")
event_path = os.environ.get("GITHUB_EVENT_PATH", "")
github_token = os.environ.get("GITHUB_TOKEN", "")

if event_name != "issue_comment" or not event_path or not os.path.exists(event_path) or not github_token:
    sys.exit(1)

try:
    with open(event_path, "r", encoding="utf-8") as f:
        event = json.load(f)
except Exception:
    sys.exit(1)

comment_body = (event.get("comment", {}).get("body") or "").strip()
if not comment_body.startswith("/help"):
    sys.exit(1)

repository = (event.get("repository", {}) or {}).get("full_name")
issue_number = (event.get("issue", {}) or {}).get("number")
if not repository or not issue_number:
    sys.exit(1)

help_message = """## PR Agent Walkthrough 🤖

Available commands in this deployment:

- `/review [model]`
- `/describe [model]`
- `/improve [model]`
- `/ask [model] <question>`
- `/models [--refresh]`
- `/update_changelog [model]`
- `/help_docs <question>`
- `/add_docs`
- `/generate_labels`
- `/similar_issue`
- `/config`

Model override example:
`/review gpt-5.2-codex`
"""

url = f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments"
payload = json.dumps({"body": help_message}).encode("utf-8")
request = urllib.request.Request(
    url,
    data=payload,
    method="POST",
    headers={
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    },
)
try:
    with urllib.request.urlopen(request, timeout=30) as response:
        response.read()
    print("Handled /help with lightweight fast path.")
    sys.exit(0)
except urllib.error.HTTPError as exc:
    print(f"Fast-path /help failed with status={exc.code}. Falling back to full PR-Agent bootstrap.")
except Exception as exc:
    print(f"Fast-path /help failed: {exc}. Falling back to full PR-Agent bootstrap.")
sys.exit(1)
PY

fast_help_status=$?
set -e

if [ "$fast_help_status" -eq 0 ]; then
  exit 0
fi

echo "Installing PR-Agent from ${PR_AGENT_GIT_REPOSITORY}@${PR_AGENT_GIT_REF}"
python -m pip install --no-cache-dir "git+https://github.com/${PR_AGENT_GIT_REPOSITORY}.git@${PR_AGENT_GIT_REF}"

python -m pr_agent.servers.github_action_runner
