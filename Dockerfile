FROM python:3.12-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir .

ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8000
ENV AI_CHALLENGE_DB=/data/aichallenge.sqlite3

VOLUME ["/data"]
EXPOSE 8000

CMD ["python", "-m", "aichallenge_mcp.server"]
