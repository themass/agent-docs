FROM python:3.12-slim
WORKDIR /app
COPY agent/poetry-domain-mcp/pyproject.toml /tmp/service/pyproject.toml
RUN pip install --no-cache-dir /tmp/service
COPY agent/poetry-domain-mcp/src /app/src
ENV PYTHONPATH=/app/src
EXPOSE 8101
CMD ["python", "-m", "poetry_domain_mcp.server"]
