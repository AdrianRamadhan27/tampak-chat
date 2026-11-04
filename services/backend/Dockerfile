FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH" \
    HF_HOME=/data/cache/huggingface XDG_CACHE_HOME=/data/cache OMP_NUM_THREADS=2
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng tesseract-ocr-ind libglib2.0-0 libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir uv==0.12.5
WORKDIR /app
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --extra processing --no-dev
COPY app ./app
COPY migrations ./migrations
RUN useradd --create-home --uid 10001 tampak && mkdir -p /data && chown tampak:tampak /data
USER tampak
EXPOSE 8100
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8100"]
