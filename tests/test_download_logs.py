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
