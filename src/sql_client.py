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
from dataclasses import dataclass, field
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
    # The v2 non-fatal channel. Worth carrying rather than discarding: this is
    # where "you filtered on a field that does not exist" arrives, and that
    # condition otherwise looks exactly like an honest empty result
    # (td-20260823204811553899).
    warnings: list[Any] = field(default_factory=list)

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

    def query(self, sql: str, timeout: float | None = None) -> SqlResult:
        """Run one statement. `timeout` overrides the client default per call —
        used by the public /api/sql route, which should not be able to hold a
        connection for as long as the demo's own card queries may."""
        started = time.perf_counter()
        try:
            r = self._client.post(f"{self._url}/api/v2/_sql", headers=self._headers,
                                  content=sql, timeout=timeout or self._client.timeout)
        except httpx.HTTPError as e:
            raise SqlError(f"could not reach Aito: {e}", sql=sql) from e
        ms = (time.perf_counter() - started) * 1000.0
        self.last_ms = ms
        self.last_calls += 1

        if r.status_code >= 400:
            # Surface Aito's own message. They are good — the alias error names
            # the fix — so passing them through beats paraphrasing.
            detail = r.text
            try:
                body = r.json()
                detail = ((body.get("data") or {}).get("message")
                          or body.get("message") or detail)
            except Exception:
                pass
            raise SqlError(detail.strip(), sql=sql, status=r.status_code)

        return self._normalise(r.json(), sql, ms)

    @staticmethod
    def _normalise(body: dict, sql: str, ms: float) -> SqlResult:
        """Turn whatever shape `_sql` returned into (columns, list-of-dicts).

        Written defensively because this response has changed THREE times under
        this demo, twice breaking it after it was working:

          1. rows as objects, with engine internals (`ps`/`fs`) leaking through
          2. those internals trimmed to the documented columns, and `related`
             arriving as a JSON string rather than an object
          3. (2.8.0-dev) a Postgres-style envelope — column names moved to
             `fields[].name`, and rows became POSITIONAL ARRAYS

        Shape 3 is the right one: `command` / `rowCount` / `fields[].dataTypeID`
        is what a Postgres client library hands you, which is exactly correct
        for a surface whose pitch is that Postgres clients work unchanged. But
        the demo has to survive a rollback to a build serving shape 1 or 2, so
        all three are accepted and normalised to one internal form.
        """
        rows = body.get("rows")
        if rows is None:
            rows = body.get("hits") or []

        # Column names: `fields[].name` (shape 3), `columns` (shapes 1-2), else
        # the keys of the first row when it is already an object.
        cols: list[str] = []
        fields = body.get("fields")
        if isinstance(fields, list) and fields:
            cols = [f.get("name", f"col{i}") if isinstance(f, dict) else str(f)
                    for i, f in enumerate(fields)]
        if not cols and isinstance(body.get("columns"), list):
            cols = [str(c) for c in body["columns"]]
        if not cols and rows and isinstance(rows[0], dict):
            cols = list(rows[0].keys())

        # Positional rows -> dicts. zip() stops at the shorter side, so a row
        # longer than `fields` would lose its tail; name the extras instead,
        # because a silently truncated row surfaces later as a missing number
        # on a card rather than as an error.
        if rows and isinstance(rows[0], list):
            named = []
            for row in rows:
                if len(row) > len(cols):
                    cols = cols + [f"col{i}" for i in range(len(cols), len(row))]
                named.append(dict(zip(cols, row)))
            rows = named

        warnings = body.get("warnings")
        return SqlResult(sql=sql, columns=list(cols), rows=rows, ms=ms,
                         warnings=list(warnings) if isinstance(warnings, list) else [])

    def close(self) -> None:
        self._client.close()
