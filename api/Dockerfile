FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FASTEMBED_CACHE_PATH=/app/.cache/fastembed

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

RUN useradd --create-home appuser && chown appuser /app
USER appuser

# Bake the embedding model into the image (ONNX, ~70 MB) so startup needs no download
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RUN python -c "from fastembed import TextEmbedding; TextEmbedding('${EMBEDDING_MODEL}')"
ENV HF_HUB_OFFLINE=1

COPY --chown=appuser . .

EXPOSE 8000
CMD ["sh", "start.sh"]
