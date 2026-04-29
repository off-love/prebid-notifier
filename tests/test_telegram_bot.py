from src import telegram_bot


def test_sanitize_error_redacts_telegram_token(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "secret-token")

    message = telegram_bot._sanitize_error(
        "HTTPSConnectionPool url=/botsecret-token/sendMessage timed out"
    )

    assert "secret-token" not in message
    assert "[REDACTED]" in message
