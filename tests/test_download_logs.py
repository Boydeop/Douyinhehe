"""Security regression: exported diagnostics must not expose Douyin browser sessions."""
from douyinhehe.logging_support import redact


def test_redact_douyin_session_values():
    raw = "Cookie: sessionid=secret-session; sid_tt=secret-auth\nmsToken=opaque-credential-value"
    safe = redact(raw)
    assert "secret-session" not in safe
    assert "secret-auth" not in safe
    assert "opaque-credential-value" not in safe
    assert "REDACTED" in safe


def test_redact_query_parameter_without_destroying_video_id():
    raw = "https://www.douyin.com/video/7263619345228582203?msToken=abc123secret456"
    safe = redact(raw)
    assert "7263619345228582203" in safe
    assert "abc123secret456" not in safe


def test_sensitive_share_url_parameters_never_escape_logs():
    raw = ("https://www.douyin.com/video/7263619345228582203"
           "?share_token=topsecret123&signature=private-signature&is_from_webapp=1")
    safe = redact(raw)
    assert "7263619345228582203" in safe
    assert "topsecret123" not in safe
    assert "private-signature" not in safe
    assert "is_from_webapp=1" in safe
