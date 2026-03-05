"""Shared test fixtures — mock config so tests don't need real env vars."""

import os

# Set dummy env vars before any rcf module tries to read them
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
