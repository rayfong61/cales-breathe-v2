"""OAuth 路由基本行為（未設定憑證時應回 503）。"""


def test_google_oauth_start_returns_503_when_not_configured(client, monkeypatch):
    for k in (
        "GOOGLE_OAUTH_CLIENT_ID",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_OAUTH_CLIENT_SECRET",
        "GOOGLE_CLIENT_SECRET",
    ):
        monkeypatch.delenv(k, raising=False)
    r = client.get("/auth/google", follow_redirects=False)
    assert r.status_code == 503


def test_line_oauth_start_returns_503_when_not_configured(client, monkeypatch):
    for k in ("LINE_LOGIN_CHANNEL_ID", "LINE_LOGIN_CHANNEL_SECRET"):
        monkeypatch.delenv(k, raising=False)
    r = client.get("/auth/line", follow_redirects=False)
    assert r.status_code == 503
