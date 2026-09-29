"""The live smoke's content checks (scripts/live_smoke.py), offline."""
import importlib.util
import sys
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "live_smoke", Path(__file__).resolve().parents[1] / "scripts" / "live_smoke.py")
smoke = importlib.util.module_from_spec(_spec)
sys.modules["live_smoke"] = smoke
_spec.loader.exec_module(smoke)


def _card(**over):
    card = {"key": "thermal", "churn": 38.2, "base_churn": 20.1,
            "causes": [{"field": "cooling", "value": "passive", "n": 860}], "levers": [{"value": "liquid"}]}
    return {**card, **over}


def test_a_full_card_passes():
    assert "1 causes, 1 levers" in smoke.check_card(_card())


def test_a_failed_group_by_shows_as_an_uncounted_cause():
    # src/app.py: a GROUP BY failure leaves n/rate None
    with pytest.raises(AssertionError, match="without a count"):
        smoke.check_card(_card(causes=[{"field": "cooling", "value": "passive", "n": None}]))


def test_a_failed_recommend_shows_as_no_levers():
    # src/explore.py: a failed recommend becomes levers=[]
    with pytest.raises(AssertionError, match="levers"):
        smoke.check_card(_card(levers=[]))
    with pytest.raises(AssertionError, match="levers"):
        smoke.check_explore({"dimensions": [{}], "levers": [], "predicted": 20.1})


def test_no_patterns_fails():
    with pytest.raises(AssertionError, match="patterns"):
        smoke.check_patterns({"patterns": []})


def test_sql_needs_rows():
    with pytest.raises(AssertionError, match="no rows"):
        smoke.check_sql_rows({"rows": []})
    assert "2 rows" in smoke.check_sql_rows({"rows": [[1], [2]]})


def test_a_dropped_connection_is_a_recorded_failure_not_a_crash(monkeypatch, capsys):
    import http.client

    def urlopen(req, timeout):
        raise http.client.RemoteDisconnected("Remote end closed connection without response")
    monkeypatch.setattr(smoke.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(smoke.sys, "argv", ["live_smoke.py", "--base", "http://x"])
    assert smoke.main() == 1
    assert "checks FAILED" in capsys.readouterr().out


def test_the_kpi_sql_must_say_what_the_card_says():
    # aito-sql-demo #3: predict() gave only the complement row under a 38.2% card
    bug = {"rows": [{"value": "false", "p": 0.618}]}
    with pytest.raises(AssertionError, match="no 'true' row"):
        smoke.check_kpi_matches_card(bug, 38.2)
    fixed = {"rows": [{"value": "false", "p": 0.618}, {"value": "true", "p": 0.382}]}
    assert "38.2%" in smoke.check_kpi_matches_card(fixed, 38.2)
    with pytest.raises(AssertionError, match="card shows 45.0%"):
        smoke.check_kpi_matches_card(fixed, 45.0)
