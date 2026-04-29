from src.api import prebid_client


def test_prebid_api_key_uses_prebid_secret_without_common_key(monkeypatch):
    monkeypatch.delenv("G2B_API_KEY", raising=False)
    monkeypatch.setenv("G2B_PREBID_API_KEY", "prebid-key")

    assert prebid_client._get_api_key() == "prebid-key"
