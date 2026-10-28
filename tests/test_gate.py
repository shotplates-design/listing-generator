import hmac

from listing_generator.gate import AppGate, AppSecrets
from listing_generator.vision.factory import VisionProviders


def test_password_comes_from_secrets_before_the_environment():
    secrets = {"APP_PASSWORD": "from-secrets"}
    environ = {"APP_PASSWORD": "from-env"}
    assert AppSecrets.lookup("APP_PASSWORD", secrets, environ) == "from-secrets"


def test_blank_secret_falls_back_to_the_environment():
    secrets = {"APP_PASSWORD": "  ", "GEMINI_API_KEY": ""}
    environ = {"APP_PASSWORD": "from-env", "GEMINI_API_KEY": "env-key"}
    assert AppSecrets.lookup("APP_PASSWORD", secrets, environ) == "from-env"
    assert AppSecrets.lookup("GEMINI_API_KEY", secrets, environ) == "env-key"


def test_password_and_gemini_key_fall_back_to_the_environment():
    assert AppSecrets.lookup("APP_PASSWORD", {}, {"APP_PASSWORD": "from-env"}) == "from-env"
    assert AppSecrets.lookup("GEMINI_API_KEY", None, {"GEMINI_API_KEY": "env-key"}) == "env-key"
    assert AppSecrets.lookup("APP_PASSWORD", None, {}) == ""
    assert AppSecrets.lookup("GEMINI_API_KEY", {}, {}) == ""


def test_missing_password_refuses_to_open():
    message = AppGate.missing_message()
    assert "APP_PASSWORD" in message
    assert ".streamlit/secrets.toml" in message
    assert AppGate.decide("", True, "anything", True) == AppGate.MISSING
    assert AppGate.decide("   ", False, "", False) == AppGate.MISSING


def test_gate_stays_closed_until_the_password_matches():
    expected = "correct horse"
    assert AppGate.decide(expected, False, "", False) == AppGate.PROMPT
    assert AppGate.decide(expected, False, "nope", True) == AppGate.REJECT
    assert AppGate.decide(expected, False, "", True) == AppGate.REJECT
    assert AppGate.decide(expected, False, expected, True) == AppGate.UNLOCK
    assert AppGate.decide(expected, True, "nope", True) == AppGate.OPEN


def test_password_check_uses_compare_digest(monkeypatch):
    seen = {}
    real = hmac.compare_digest

    def fake(left, right):
        seen["left"] = left
        seen["right"] = right
        return real(left, right)

    monkeypatch.setattr("listing_generator.gate.hmac.compare_digest", fake)
    assert AppGate.matches("correct horse", "correct horse") is True
    assert seen == {"left": "correct horse", "right": "correct horse"}
    assert AppGate.matches("wrong", "correct horse") is False
    assert AppGate.matches("", "correct horse") is False


def test_empty_configured_password_never_matches(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("compare_digest should not run without a configured password")

    monkeypatch.setattr("listing_generator.gate.hmac.compare_digest", boom)
    assert AppGate.matches("", "") is False
    assert AppGate.matches("x", "") is False


def test_gemini_provider_prefers_streamlit_secrets(monkeypatch):
    monkeypatch.setattr(AppSecrets, "mapping", staticmethod(lambda: {"GEMINI_API_KEY": "secret-key"}))
    monkeypatch.setenv("VISION_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    provider = VisionProviders.from_env()
    described = VisionProviders.describe()
    assert provider.api_key == "secret-key"
    assert described["key_configured"] is True
    assert "secret-key" not in str(described)
    assert "env-key" not in str(described)


def test_read_uses_the_environment_when_streamlit_secrets_are_missing(monkeypatch):
    monkeypatch.setattr(AppSecrets, "mapping", staticmethod(lambda: {}))
    monkeypatch.setenv("GEMINI_API_KEY", "env-key")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    assert AppSecrets.read("GEMINI_API_KEY") == "env-key"
    assert AppSecrets.read("APP_PASSWORD") == ""
