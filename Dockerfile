FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PADDLE_PDX_CACHE_HOME=/opt/paddlex

WORKDIR /app

COPY pyproject.toml .
RUN mkdir packing_service && touch packing_service/__init__.py \
    && pip install ".[api]" \
    && pip uninstall -y erp-packing-service \
    && pip install ".[api,gpu]" --extra-index-url https://www.paddlepaddle.org.cn/packages/stable/cu129/ \
    && rm -rf packing_service build *.egg-info

COPY packing_service ./packing_service

RUN python -c "from packing_service.ocr import ocr_model; ocr_model()"

ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
    PACKING_HOST=0.0.0.0 \
    PACKING_PORT=8091

RUN useradd --system --no-create-home packing && chown -R packing /opt/paddlex
USER packing

EXPOSE 8091

HEALTHCHECK --interval=10s --timeout=3s --start-period=60s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen(f'http://127.0.0.1:{os.environ[\"PACKING_PORT\"]}/health', timeout=2)"

CMD ["python", "-m", "packing_service.api"]
