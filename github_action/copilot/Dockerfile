FROM python:3.12.10-slim

RUN apt-get update && apt-get install --no-install-recommends -y git curl nodejs npm && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN pip install --no-cache-dir github-copilot-sdk==0.1.23
RUN npm install -g @github/copilot

ENV PYTHONPATH=/app

COPY pr_agent /app/pr_agent
COPY docs /app/docs
COPY github_action/copilot/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
