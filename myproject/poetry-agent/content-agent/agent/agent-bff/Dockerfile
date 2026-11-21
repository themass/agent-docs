FROM python:3.12-slim
WORKDIR /app
COPY agent/agent-bff/pyproject.toml /tmp/service/pyproject.toml
RUN pip install --no-cache-dir /tmp/service
COPY agent/agent-bff/src /app/src
ENV PYTHONPATH=/app/src
EXPOSE 8100
CMD ["python", "-m", "agent_bff.main"]
