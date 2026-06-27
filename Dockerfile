FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt

ARG INSTALL_CLAUDE_CLI=1

RUN if [ "$INSTALL_CLAUDE_CLI" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends ca-certificates nodejs npm \
      && apt-get clean \
      && rm -rf /var/lib/apt/lists/*; \
    fi

RUN if [ "$INSTALL_CLAUDE_CLI" = "1" ]; then \
      npm config set fetch-retries 5 \
      && npm config set fetch-retry-mintimeout 20000 \
      && npm config set fetch-retry-maxtimeout 120000 \
      && for attempt in 1 2 3 4 5; do \
        npm install -g @anthropic-ai/claude-code && break; \
        if [ "$attempt" = "5" ]; then exit 1; fi; \
        sleep $((attempt * 10)); \
      done; \
    fi

COPY . .

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
