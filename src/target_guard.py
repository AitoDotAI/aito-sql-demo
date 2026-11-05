"""Refuse to run the book tests against anything but a loopback Aito, unless asked twice.

The book tests read the engine (schema, SELECTs, evaluate, holdout scoring). Run from a shell that
forgot to export a local AITO_API_URL, the project's dotenv file silently points them at the shared
instance. Two keys are required to mean it: the `--allow-shared` flag and AITO_TEST_ALLOW_SHARED=1.

    python -m src.target_guard [--allow-shared]     exit 0 = go ahead, 2 = refused
"""

from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class TargetRefused(Exception):
    pass


def check_target(url: str, flag: bool, env: bool) -> None:
    host = urlparse(url or "").hostname or ""
    if not host:
        raise TargetRefused("AITO_API_URL is not set or has no host; refusing to guess a target")
    if host in LOOPBACK or (flag and env):
        return
    raise TargetRefused(
        f"refusing to run the book tests against {host}: not a loopback Aito. "
        "Point AITO_API_URL at a local server, or, if you mean it, pass --allow-shared AND set "
        "AITO_TEST_ALLOW_SHARED=1.")


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()   # the same resolution src/config.py does, so we judge the URL the tests will use
    try:
        check_target(os.environ.get("AITO_API_URL", ""), "--allow-shared" in sys.argv[1:],
                     os.environ.get("AITO_TEST_ALLOW_SHARED") == "1")
    except TargetRefused as e:
        print(f"test-book: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
