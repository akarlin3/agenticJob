# Single-worker image suitable for a personal/portfolio deploy.
# NOTE: scaling to multiple workers would require reworking the per-request
# state (master_portfolio.pdf and output/*.json are written to shared paths
# on disk). That refactor is intentionally out of scope for a single-user
# tool — see README for the public-deploy checklist.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN groupadd --system app && useradd --system --gid app --home /app app

# Tectonic compiles tailored_resume.tex -> .pdf inside the container so the
# web UI can offer a one-click PDF download. curl + ca-certificates are
# needed for the installer; we leave them in the image so Tectonic can fetch
# missing TeX packages on first compile.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && curl -fsSL https://drop-sh.fullyjustified.net/x86_64-unknown-linux-musl/install.sh | sh \
    && mv tectonic /usr/local/bin/tectonic \
    && tectonic --version \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output /app/static && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
