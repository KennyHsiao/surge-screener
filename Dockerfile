FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel \
    && python -m pip install -r requirements.txt

RUN apt-get update \
    && apt-get install -y --no-install-recommends bubblewrap ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN mkdir -p /app/.codex /app/var/candidates /app/var/ai_chat_sessions /app/var/content \
    && ln -sfn /app/var/candidates/filtered_universe.json /app/filtered_universe.json \
    && ln -sfn /app/var/candidates/ranked_candidates.json /app/ranked_candidates.json \
    && ln -sfn /app/var/candidates/scored_candidates.json /app/scored_candidates.json \
    && ln -sfn /app/var/candidates/layer2_results.json /app/layer2_results.json \
    && ln -sfn /app/var/candidates/dd_results.json /app/dd_results.json

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501", "--server.headless", "true", "--browser.gatherUsageStats", "false"]
