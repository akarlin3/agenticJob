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
# needed for the installer; the lib* packages are the shared libraries the
# prebuilt Tectonic binary dynamically links against (graphite2, harfbuzz,
# fontconfig, freetype, icu). We leave curl in the image so Tectonic can
# fetch missing TeX packages on first compile. These all come from the Debian
# mirror over apt, which is reliable even behind a TLS-intercepting proxy.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates \
        libgraphite2-3 libharfbuzz0b libfontconfig1 libfreetype6 libicu76 \
    && rm -rf /var/lib/apt/lists/*

# --- Optional: trust an extra CA for TLS-intercepting proxies --------------
# Networks that intercept TLS (many corporate proxies, sandboxed CI/build
# environments) present a self-signed root the container doesn't know about,
# which breaks every HTTPS download in this build (pip from PyPI, the Tectonic
# binary) with "self-signed certificate in certificate chain". To deploy in
# such a network, drop your proxy's root CA (PEM, *.crt) into ./certs/ and it
# is appended to the system trust bundle that curl and pip use. On a normal
# network leave ./certs empty — this block is a no-op. (apt already works:
# it fetches over HTTP and verifies packages with GPG, not TLS.)
COPY certs/ /tmp/extra-cacerts/
RUN if ls /tmp/extra-cacerts/*.crt >/dev/null 2>&1; then \
        echo "Trusting extra CA cert(s) from ./certs/ for HTTPS during build:"; \
        ls -1 /tmp/extra-cacerts/*.crt; \
        cat /tmp/extra-cacerts/*.crt >> /etc/ssl/certs/ca-certificates.crt; \
    fi; \
    rm -rf /tmp/extra-cacerts
# Point pip/requests at the system trust bundle (which now includes any extra
# CA appended above) instead of pip's vendored certifi store.
ENV PIP_CERT=/etc/ssl/certs/ca-certificates.crt \
    SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Fetch the prebuilt Tectonic binary from a third-party host over HTTPS. This
# download is the one fragile step in the build: it fails behind a corporate /
# sandbox TLS-intercepting proxy (the container doesn't trust the proxy's CA)
# or if the host is unreachable. PDF rendering is OPTIONAL — app.py probes for
# the `tectonic` binary at runtime and degrades gracefully when it's absent
# (the .tex source stays downloadable; the run never aborts). So this step is
# best-effort by design: a failed download must NOT abort the image build, or
# an offline/proxied deploy can never come up at all. Where the network allows
# (normal deploys, CI), Tectonic installs and the PDF feature is enabled.
RUN set -eu; \
    if curl -fsSL https://drop-sh.fullyjustified.net/x86_64-unknown-linux-musl/install.sh -o /tmp/install-tectonic.sh \
        && sh /tmp/install-tectonic.sh \
        && mv tectonic /usr/local/bin/tectonic \
        && tectonic --version; then \
        echo "Tectonic installed — server-side PDF render enabled."; \
    else \
        echo "WARNING: Tectonic install failed (offline or TLS-intercepting proxy?); " \
             "building without server-side PDF render. The app still runs and " \
             "degrades gracefully — see compile_resume_to_pdf() in app.py."; \
    fi; \
    rm -f /tmp/install-tectonic.sh

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/output /app/static && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/api/health').status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
