FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

# Copy the whole package: an explicit file list silently drops new modules
# from the image, and the failure only shows up at runtime under compose.
COPY . ./

ENV PATH="/app/.venv/bin:$PATH"
ENV AGENT_HOST=0.0.0.0
ENV AGENT_PORT=7860

EXPOSE 7860

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "7860"]
