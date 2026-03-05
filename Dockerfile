FROM python:3.11-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# GovMap uses legacy SSL ciphers — allow them
RUN sed -i 's/CipherString = DEFAULT:@SECLEVEL=2/CipherString = DEFAULT:@SECLEVEL=1/' /etc/ssl/openssl.cnf || true

WORKDIR /app

# Copy and install Python deps first (layer caching)
COPY pyproject.toml ./
RUN pip install --no-cache-dir . 2>/dev/null || true
# Full install after copying source
COPY . .
RUN pip install --no-cache-dir .
