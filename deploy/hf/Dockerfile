# Live demo: one container with PostgreSQL + pgvector, the FastAPI agent and the React app.
# Built from the repository root (the deploy workflow copies this file there for Hugging Face Spaces).

FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ .
RUN npx vite build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed

# PostgreSQL with pgvector, from the Debian repository of this image
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql \
    && PGV=$(ls /usr/lib/postgresql) \
    && apt-get install -y --no-install-recommends "postgresql-${PGV}-pgvector" \
    && ln -s /usr/lib/postgresql/${PGV}/bin /usr/lib/postgresql/bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY api/requirements.txt .
RUN pip install -r requirements.txt

# Hugging Face Spaces runs the container as uid 1000
RUN useradd --create-home --uid 1000 user && chown user /app
USER user

ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"
ENV HF_HUB_OFFLINE=1

COPY --chown=user api/ /app/
COPY --chown=user data/ /data/
COPY --chown=user --from=web /web/dist /app/static
COPY --chown=user deploy/hf/serve.py deploy/hf/start.sh /app/

# Demo defaults: free rule-based model, tickets in the built-in mock system (no n8n in the demo)
ENV DATABASE_URL=postgresql+psycopg://helpdesk@127.0.0.1:5432/helpdesk \
    LLM_PROVIDER=stub \
    TICKET_BACKEND=direct \
    PUBLIC_URL=/api \
    DEMO_MODE=1

EXPOSE 7860
CMD ["sh", "/app/start.sh"]
