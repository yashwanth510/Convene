import pytest
from pydantic import ValidationError

from backend.config import Config


@pytest.mark.parametrize(
    "value, expected",
    [
        ("", []),
        ("   ", []),
        ("[]", []),
        ("account-one", ["account-one"]),
        (" account-one, account-two,account-one ", ["account-one", "account-two"]),
        ('["account-one", "account-two"]', ["account-one", "account-two"]),
        ('"account-one"', ["account-one"]),
    ],
)
def test_admin_ids_from_environment(monkeypatch, value, expected):
    monkeypatch.setenv("ADMIN_USER_IDS", value)
    assert Config(_env_file=None).ADMIN_USER_IDS == expected


def test_admin_ids_unset_and_dotenv(monkeypatch, tmp_path):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    assert Config(_env_file=None).ADMIN_USER_IDS == []
    env = tmp_path / ".env"
    env.write_text("ADMIN_USER_IDS=account-one,account-two\n")
    assert Config(_env_file=env).ADMIN_USER_IDS == ["account-one", "account-two"]
    monkeypatch.setenv("ADMIN_USER_IDS", "")
    assert Config(_env_file=env).ADMIN_USER_IDS == []


@pytest.mark.parametrize(
    "value", ["[account-one]", '["account-one",', "[123]", '{"id":"account-one"}']
)
def test_invalid_admin_ids_are_rejected(monkeypatch, value):
    monkeypatch.setenv("ADMIN_USER_IDS", value)
    with pytest.raises(ValidationError, match="Use \\[\\] to disable admin access"):
        Config(_env_file=None)
