FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_PORT=8000 \
    MCP_STATELESS_HTTP=true

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml /app/
COPY src /app/src

RUN pip install --no-cache-dir .

USER app

EXPOSE 8000

CMD ["aichallenge-mcp"]
