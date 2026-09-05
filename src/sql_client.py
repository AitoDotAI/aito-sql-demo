"""Run SQL against Aito over the read-only REST `_sql` endpoint.

Deliberately tiny. The demo's claim is that SQL is the whole interface, so the
server has no query builder and no ORM: a card holds SQL text, this sends it,
and the UI shows the same text it sent.

Two things about `_sql` worth knowing, both learned the hard way and both worth
a line in the docs (filed as td-20260823205040145864):

  * it takes RAW SQL as the request body, not a JSON envelope. A JSON body
    fails with "unexpected character '{' at position 0".
  * it is READ-ONLY. DDL, COPY and INSERT are wire-protocol only, which is why
    loading lives in src/load.py and goes through psql.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from src.config import Config


class SqlError(Exception):
    def __init__(self, message: str, sql: str = "", status: int | None = None):
        super().__init__(message)
        self.sql = sql
        self.status = status


@dataclass
class SqlResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    ms: float

    def first(self) -> dict[str, Any] | None:
        return self.rows[0] if self.rows else None


class SqlClient:
    def __init__(self, config: Config, timeout: float = 60.0) -> None:
        self._url = config.aito_url.rstrip("/")
        self._headers = {"x-api-key": config.aito_key, "content-type": "text/plain"}
        self._client = httpx.Client(timeout=timeout)
        self.last_ms: float = 0.0
        self.last_calls: int = 0

    @property
    def base_url(self) -> str:
        return self._url

    def query(self, sql: str) -> SqlResult:
        started = time.perf_counter()
        try:
            r = self._client.post(f"{self._url}/api/v2/_sql", headers=self._headers, content=sql)
        except httpx.HTTPError as e:
            raise SqlError(f"could not reach Aito: {e}", sql=sql) from e
        ms = (time.perf_counter() - started) * 1000.0
        self.last_ms = ms
        self.last_calls += 1

        if r.status_code >= 400:
            # Surface Aito's own message. They are good now — the alias error
            # names the fix — so passing them through beats paraphrasing.
            detail = r.text
            try:
                body = r.json()
                detail = (body.get("data") or {}).get("message") or body.get("message") or detail
            except Exception:
                pass
            raise SqlError(detail.strip(), sql=sql, status=r.status_code)

        body = r.json()
        rows = body.get("rows") or body.get("hits") or []
        cols = body.get("columns") or (list(rows[0].keys()) if rows else [])
        if rows and isinstance(rows[0], list):
            rows = [dict(zip(cols, row)) for row in rows]
        return SqlResult(sql=sql, columns=list(cols), rows=rows, ms=ms)

    def close(self) -> None:
        self._client.close()
