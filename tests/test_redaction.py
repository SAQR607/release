"""Secret redaction tests (§35)."""

from app.logging_setup import redact


def test_redacts_groq_keys():
    key = "gsk_FAKE0123456789abcdefghijklmnop"
    out = redact(f"using key {key}")
    assert key not in out
    assert "[REDACTED]" in out


def test_redacts_bearer():
    out = redact("Authorization: Bearer abc123DEF456")
    assert "abc123DEF456" not in out
    assert "[REDACTED]" in out


def test_redacts_telegram_token():
    tok = "0123456789:FAKEfaketoken0123456789abcdefghij"
    out = redact(f"url=https://api.telegram.org/bot{tok}/sendMessage")
    assert tok not in out
    assert "[REDACTED]" in out


def test_redacts_google_tokens():
    assert "ya29" not in redact("access_token=ya29.abcdefghijklmnop")
    assert "AIza" not in redact("key=AIzaSyA1234567890abcdefghijklmn")


def test_redacts_kaglot_style():
    assert "KGAT_" not in redact("KGAT_abc123def456")


def test_plain_text_unchanged():
    msg = "episode s01e001 published"
    assert redact(msg) == msg
