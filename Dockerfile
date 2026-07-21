FROM python:3.13-slim

ARG VERSION=0.0.0
LABEL org.opencontainers.image.title="rockfeed-rj" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/wallacepnts/rockfeed-rj"

WORKDIR /

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && playwright install --with-deps chromium

COPY app ./app

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8765/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
