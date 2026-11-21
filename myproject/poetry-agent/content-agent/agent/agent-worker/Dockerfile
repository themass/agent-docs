FROM python:3.12-slim
WORKDIR /app
# Build context is content-agent/. .dockerignore hides pipeline/, deploy/ and frontend/, so the two
# JSON schemas the worker ships with live inside the package (src/agent_worker/schemas, copied below)
# and a test keeps them byte-identical to pipeline/contracts.
COPY agent/agent-worker/pyproject.toml /tmp/service/pyproject.toml
COPY agent/agent-worker/src /tmp/service/src
RUN pip install --no-cache-dir /tmp/service && rm -rf /tmp/service
COPY agent/agent-worker/src /app/src
# Only the budgets file is needed from the profile; compose mounts the full profile at /profile
# (POETRY_AGENT_PROFILE_ROOT) read-only, which takes precedence.
COPY agent/deerflow-profile/config/budgets.yaml /app/deerflow-profile/config/budgets.yaml
ENV PYTHONPATH=/app/src \
    POETRY_AGENT_PROFILE_ROOT=/app/deerflow-profile \
    PORT=8102
EXPOSE 8102
CMD ["python", "-m", "agent_worker.app"]
