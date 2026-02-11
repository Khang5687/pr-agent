FROM python:3.12.10-slim

RUN apt-get update && apt-get install --no-install-recommends -y git curl nodejs npm && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install --no-cache-dir github-copilot-sdk==0.1.23
RUN npm install -g @github/copilot

ENV PYTHONPATH=/app

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
