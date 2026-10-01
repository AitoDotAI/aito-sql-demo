"""DEMO_WARM decides whether booting costs ~22 statements against shared.

The warm-up earns its keep in production, where a process starts once per
deploy: it moves ~7s of holdout scoring, ~9s of evaluate() and a 19-statement
patterns mine off the first visitor, along with a DNS lookup that can stall
5s. In a dev loop with --reload it fires on every save, against a SHARED
instance other demos are using. That asymmetry is the whole reason for a flag.

Default ON so deploys keep the behaviour they were tuned for; `./do dev` sets
it to 0. Nothing is lost when it is off — the caches are lazy, so the cost
moves to the first request rather than disappearing.
"""

import importlib
import os

import pytest


@pytest.fixture
def warm_flag(monkeypatch):
    """Read warm_on_startup() under a given DEMO_WARM, without a live app."""
    from src import app as app_module

    def read(value):
        if value is None:
            monkeypatch.delenv("DEMO_WARM", raising=False)
        else:
            monkeypatch.setenv("DEMO_WARM", value)
        return app_module.warm_on_startup()

    return read


def test_warms_by_default(warm_flag):
    # Production sets nothing, and must keep warming.
    assert warm_flag(None) is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "No", " 0 ", ""])
def test_the_obvious_spellings_of_off_all_work(warm_flag, value):
    # A flag whose "off" only works in one spelling is a flag people think
    # they set.
    assert warm_flag(value) is False


@pytest.mark.parametrize("value", ["1", "true", "yes", "anything"])
def test_everything_else_warms(warm_flag, value):
    # Fail toward the production behaviour: a typo must not silently disable
    # the warm-up on a deploy.
    assert warm_flag(value) is True


def test_the_hook_itself_makes_no_call_when_disabled(monkeypatch):
    """The flag is only worth having if the HOOK honours it.

    Asserted against the startup function rather than the helper, because a
    guard in the wrong place still reads as a passing flag test while the
    burst goes out anyway. Patched rather than run live: a mistake here would
    put ~22 statements on a shared instance, which is the exact thing this
    commit exists to prevent.
    """
    from src import app as app_module

    calls = []
    monkeypatch.setenv("DEMO_WARM", "0")
    monkeypatch.setattr(app_module.sql, "warm", lambda: calls.append("sql"))
    monkeypatch.setattr(app_module.threading, "Thread",
                        lambda *a, **k: calls.append("thread") or _NullThread())

    app_module._warm_connection()
    app_module._warm_patterns()

    assert calls == []


def test_the_hook_does_start_a_thread_when_enabled(monkeypatch):
    """...and the other direction, so the guard cannot be left permanently on."""
    from src import app as app_module

    started = []
    monkeypatch.setenv("DEMO_WARM", "1")
    monkeypatch.setattr(app_module.threading, "Thread",
                        lambda *a, **k: started.append(k.get("name")) or _NullThread())

    app_module._warm_connection()
    app_module._warm_patterns()

    assert len(started) == 2


class _NullThread:
    def start(self):
        pass
