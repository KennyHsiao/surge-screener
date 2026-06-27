FROM python:3.11-slim

ARG INSTALL_CLAUDE_CLI=1

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN if [ "$INSTALL_CLAUDE_CLI" = "1" ]; then \
      apt-get update \
      && apt-get install -y --no-install-recommends ca-certificates nodejs npm \
      && npm install -g @anthropic-ai/claude-code \
      && apt-get clean \
      && rm -rf /var/lib/apt/lists/*; \
    fi

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
