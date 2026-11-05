"""./do test-book must not run against a non-loopback Aito unless asked twice."""

import pytest

from src.target_guard import TargetRefused, check_target


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:29108", "http://localhost:9005", "http://[::1]:9005",
])
def test_loopback_is_always_allowed(url):
    check_target(url, flag=False, env=False)


@pytest.mark.parametrize("url", [
    "https://shared.aito.ai/db/aito-sql-demo", "https://example.aito.ai", "http://10.0.0.5:9005",
])
def test_remote_is_refused_by_default(url):
    with pytest.raises(TargetRefused) as e:
        check_target(url, flag=False, env=False)
    assert "--allow-shared" in str(e.value)


@pytest.mark.parametrize("flag,env", [(True, False), (False, True)])
def test_one_key_is_not_enough(flag, env):
    with pytest.raises(TargetRefused):
        check_target("https://shared.aito.ai/db/aito-sql-demo", flag=flag, env=env)


def test_both_keys_allow_remote():
    check_target("https://shared.aito.ai/db/aito-sql-demo", flag=True, env=True)


def test_missing_url_is_refused():
    with pytest.raises(TargetRefused):
        check_target("", flag=True, env=True)
