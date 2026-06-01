# Extra CA certificates (optional)

Leave this directory empty on a normal network — the Docker build needs nothing here.

It exists for deploying **behind a TLS-intercepting proxy** (many corporate
networks and sandboxed CI/build environments). Those proxies terminate TLS with
a self-signed root that a fresh container doesn't trust, so every HTTPS download
in the image build fails with:

```
curl: (60) SSL certificate problem: self-signed certificate in certificate chain
# or, from pip:
SSLError(SSLCertVerificationError ... self-signed certificate in certificate chain)
```

To fix it, drop your proxy's root CA here as a PEM file ending in `.crt`:

```bash
cp /path/to/your-proxy-root-ca.crt certs/
docker compose up --build       # or: docker build -t agenticjob .
```

The Dockerfile appends every `certs/*.crt` to the container's system trust
bundle (the one curl and pip use) before any HTTPS download runs. With the CA
trusted, `pip install` and the Tectonic download both succeed.

Notes:
- `*.crt` files here are git-ignored (they're environment-specific); only this
  README and `.gitkeep` are tracked.
- A proxy *root CA* is not a secret, but commit it only if you really intend to.
- On a normal network this is a complete no-op.
