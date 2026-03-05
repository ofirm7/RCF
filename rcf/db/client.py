"""Thin wrapper around psycopg for direct PostgreSQL access."""

from __future__ import annotations

from functools import lru_cache

import psycopg
from psycopg.rows import dict_row

from rcf.config import get_config


@lru_cache(maxsize=1)
def get_conn() -> psycopg.Connection:
    """Return a singleton psycopg connection (dict-row mode)."""
    cfg = get_config()
    conn = psycopg.connect(cfg.database_url, row_factory=dict_row, autocommit=True)
    return conn


def execute(query: str, params: tuple | dict | None = None) -> list[dict]:
    """Execute *query* and return all rows as dicts. Returns [] for non-SELECT."""
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute(query, params)
        if cur.description:
            return cur.fetchall()
        return []


def execute_one(query: str, params: tuple | dict | None = None) -> dict | None:
    """Execute *query* and return the first row, or None."""
    rows = execute(query, params)
    return rows[0] if rows else None
