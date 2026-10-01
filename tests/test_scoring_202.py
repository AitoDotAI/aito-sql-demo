"""A request arriving while the holdout is being scored must not wait for it.

Measured on a real startup: the warm-up takes ~40s end to end, and a request
landing inside that window blocked for 27.9 seconds before returning — because
`cached()` held the lock across the whole computation, so the second caller
queued behind the first rather than being told to come back.

Forty seconds after a deploy is exactly when someone opens the page to check
the deploy worked, so the page that argues this demo is honest was the slowest
thing on the site at the worst moment. The fix is to answer immediately with
202 and let the page poll; the computation still happens once, on one thread.

These assert the contract that makes that possible:
  - a cold cache starts ONE fill and returns None at once, however many
    callers arrive;
  - a filled cache returns the result;
  - a fill that fails does not wedge the endpoint into permanent 202.
"""

import threading
import time

import pytest


@pytest.fixture(autouse=True)
def fresh_cache():
    """Reset the cache, and make sure no fill from a previous test is still alive.

    These tests start real background threads. Without the drain, a fill
    released at the end of one test can finish AFTER the next test has reset
    the cache, write its result into the fresh cache, and make the next
    `ensure()` return early — so the next test counts zero computations and
    fails for a reason that has nothing to do with it. Found exactly that way:
    green alone, red in the suite.
    """
    from src import holdout

    def drain():
        deadline = time.time() + 5
        while holdout._FILLING and time.time() < deadline:
            time.sleep(0.01)

    drain()
    holdout.reset_cache()
    yield
    drain()
    holdout.reset_cache()


class _SlowSql:
    """Stands in for the client; `score()` is patched, so this is only a token."""


def test_a_cold_cache_answers_immediately_rather_than_computing(monkeypatch):
    from src import holdout

    started = threading.Event()
    release = threading.Event()

    def slow_score(_sql):
        started.set()
        release.wait(10)
        return {"n": 240, "accuracy": 78.8}

    monkeypatch.setattr(holdout, "score", slow_score)

    t = time.perf_counter()
    first = holdout.ensure(_SlowSql())
    elapsed = time.perf_counter() - t

    assert first is None, "a cold cache must report 'not yet', not block"
    assert elapsed < 1.0, f"returned in {elapsed:.2f}s — it waited for the score"

    assert started.wait(5), "nobody actually started computing"
    release.set()   # let the fill finish, so the fixture can drain it


def test_many_callers_start_exactly_one_computation(monkeypatch):
    from src import holdout

    runs = []
    release = threading.Event()

    def counting_score(_sql):
        runs.append(1)
        release.wait(10)
        return {"n": 240}

    monkeypatch.setattr(holdout, "score", counting_score)

    for _ in range(8):
        assert holdout.ensure(_SlowSql()) is None

    time.sleep(0.2)
    counted = sum(runs)
    release.set()
    assert counted == 1, f"{counted} computations started; single-flight is broken"


def test_once_filled_it_returns_the_result(monkeypatch):
    from src import holdout

    monkeypatch.setattr(holdout, "score", lambda _sql: {"n": 240, "accuracy": 78.8})

    assert holdout.ensure(_SlowSql()) is None          # kicks it off
    deadline = time.time() + 5
    while holdout.ensure(_SlowSql()) is None and time.time() < deadline:
        time.sleep(0.02)

    assert holdout.ensure(_SlowSql()) == {"n": 240, "accuracy": 78.8}


def test_a_failed_fill_does_not_wedge_the_endpoint(monkeypatch):
    """A fill that raises must leave the next caller able to try again.

    Otherwise one transient failure turns the page into a permanent spinner,
    which is worse than the 28s wait this replaces: at least that one ended.
    """
    from src import holdout

    attempts = []

    def failing_score(_sql):
        attempts.append(1)
        raise RuntimeError("Aito unreachable")

    monkeypatch.setattr(holdout, "score", failing_score)

    assert holdout.ensure(_SlowSql()) is None
    deadline = time.time() + 5
    while not attempts and time.time() < deadline:
        time.sleep(0.02)

    # The failure is absorbed, and a later request starts a fresh attempt.
    # Polled rather than called once: the in-flight flag clears in the thread's
    # `finally`, so a single immediate retry can land before it does — which is
    # what a polling page does anyway.
    deadline = time.time() + 5
    while len(attempts) < 2 and time.time() < deadline:
        holdout.ensure(_SlowSql())
        time.sleep(0.02)

    assert len(attempts) >= 2, "a failed fill left the endpoint stuck"
