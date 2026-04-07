import base64
import hashlib
import hmac
import json
from datetime import datetime
from uuid import uuid4

import app.main as main_module


def _sign_body(secret: str, payload: dict) -> tuple[bytes, str]:
    raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    signature = base64.b64encode(
        hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).digest()
    ).decode("utf-8")
    return raw, signature


def _make_text_event(text: str, source_user_id: str = "U_someone") -> dict:
    return {
        "webhookEventId": f"evt-{uuid4().hex[:8]}",
        "type": "message",
        "replyToken": "fake-reply-token",
        "source": {"type": "user", "userId": source_user_id},
        "message": {"type": "text", "text": text},
    }


def _post_webhook(client, monkeypatch, events: list, secret: str = "test-secret") -> dict:
    monkeypatch.setenv("LINE_CHANNEL_SECRET", secret)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr(main_module, "_reply_text_to_line",
                        lambda **kw: __import__("asyncio").sleep(0))

    async def _noop_reply(**kw):
        pass

    monkeypatch.setattr(main_module, "_reply_text_to_line", _noop_reply)

    payload = {"events": events}
    raw, signature = _sign_body(secret, payload)
    resp = client.post("/line/webhook", content=raw, headers={"X-Line-Signature": signature})
    return resp


def _create_booking_in_db(client, monkeypatch) -> int:
    """建立一個 pending 預約，回傳 booking_id。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    phone = f"09{uuid4().int % 100000000:08d}"
    user_resp = client.post("/users", json={"name": "wb-customer", "phone": phone, "line_user_id": "U_customer_wb"})
    user_id = user_resp.json()["id"]
    svc_resp = client.get("/services")
    service_id = next(s["id"] for s in svc_resp.json() if s["category"] == "手臂")
    booking_resp = client.post("/bookings", json={
        "user_id": user_id,
        "service_ids": [service_id],
        "booking_date": "2030-04-01T10:00:00",
    })
    assert booking_resp.status_code == 200
    return booking_resp.json()["id"]


def test_line_webhook_rejects_invalid_signature(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    # Ensure secret exists so the request fails on signature mismatch.
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    payload = {"events": [{"webhookEventId": "evt-1"}]}
    raw, _ = _sign_body("test-secret", payload)

    response = client.post(
        "/line/webhook",
        content=raw,
        headers={"X-Line-Signature": "invalid-signature"},
    )
    assert response.status_code == 401


def test_line_webhook_processes_and_deduplicates_events(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    payload = {
        "events": [
            {"webhookEventId": "evt-1"},
            {"webhookEventId": "evt-2"},
        ]
    }
    raw, signature = _sign_body("test-secret", payload)

    first = client.post(
        "/line/webhook",
        content=raw,
        headers={"X-Line-Signature": signature},
    )
    assert first.status_code == 200
    assert first.json() == {"status": "ok", "processed": 2, "duplicated": 0}

    second = client.post(
        "/line/webhook",
        content=raw,
        headers={"X-Line-Signature": signature},
    )
    assert second.status_code == 200
    assert second.json() == {"status": "ok", "processed": 0, "duplicated": 2}


# ---------------------------------------------------------------------------
# 業主指令：確認 / 拒絕
# ---------------------------------------------------------------------------

def test_webhook_owner_confirm_command_changes_status(client, monkeypatch):
    """業主在 LINE 輸入「確認 {id}」，預約狀態應變為 confirmed，並推播客人。"""
    OWNER_LINE_ID = "U_owner_123"
    monkeypatch.setenv("OWNER_LINE_USER_ID", OWNER_LINE_ID)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    booking_id = _create_booking_in_db(client, monkeypatch)

    push_calls: list = []

    async def _noop_reply(**kw):
        pass

    def _fake_push_sync(access_token, user_id, text):
        push_calls.append((user_id, text))

    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setattr(main_module, "_reply_text_to_line", _noop_reply)
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", _fake_push_sync)

    event = _make_text_event(f"確認 {booking_id}", source_user_id=OWNER_LINE_ID)
    payload = {"events": [event]}
    raw, signature = _sign_body("test-secret", payload)

    resp = client.post("/line/webhook", content=raw, headers={"X-Line-Signature": signature})
    assert resp.status_code == 200

    booking_resp = client.get(f"/bookings/{booking_id}")
    assert booking_resp.json()["status"] == "confirmed"

    customer_notified = any("U_customer_wb" in uid for uid, _ in push_calls)
    assert customer_notified, "應推播通知給客人"
    msg = next(t for uid, t in push_calls if "U_customer_wb" in uid)
    assert "已確認" in msg


def test_webhook_owner_reject_command_cancels_booking(client, monkeypatch):
    """業主輸入「拒絕 {id}」，預約狀態應變為 cancelled，並推播客人。"""
    OWNER_LINE_ID = "U_owner_456"
    monkeypatch.setenv("OWNER_LINE_USER_ID", OWNER_LINE_ID)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    booking_id = _create_booking_in_db(client, monkeypatch)

    push_calls: list = []

    async def _noop_reply(**kw):
        pass

    def _fake_push_sync(access_token, user_id, text):
        push_calls.append((user_id, text))

    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setattr(main_module, "_reply_text_to_line", _noop_reply)
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", _fake_push_sync)

    event = _make_text_event(f"拒絕 {booking_id}", source_user_id=OWNER_LINE_ID)
    payload = {"events": [event]}
    raw, signature = _sign_body("test-secret", payload)

    resp = client.post("/line/webhook", content=raw, headers={"X-Line-Signature": signature})
    assert resp.status_code == 200

    booking_resp = client.get(f"/bookings/{booking_id}")
    assert booking_resp.json()["status"] == "cancelled"

    customer_notified = any("U_customer_wb" in uid for uid, _ in push_calls)
    assert customer_notified, "應推播拒絕通知給客人"
    msg = next(t for uid, t in push_calls if "U_customer_wb" in uid)
    assert "已取消" in msg


def test_webhook_non_owner_confirm_rejected(client, monkeypatch):
    """非業主的 LINE 用戶送出「確認」指令，應被拒絕（不影響預約狀態）。"""
    monkeypatch.setenv("OWNER_LINE_USER_ID", "U_real_owner")

    booking_id = _create_booking_in_db(client, monkeypatch)

    async def _noop_reply(**kw):
        pass

    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")
    monkeypatch.setattr(main_module, "_reply_text_to_line", _noop_reply)

    event = _make_text_event(f"確認 {booking_id}", source_user_id="U_random_user")
    payload = {"events": [event]}
    raw, signature = _sign_body("test-secret", payload)

    client.post("/line/webhook", content=raw, headers={"X-Line-Signature": signature})

    booking_resp = client.get(f"/bookings/{booking_id}")
    assert booking_resp.json()["status"] == "pending", "非業主不可確認，狀態應維持 pending"


def test_webhook_confirm_invalid_id_format(client, monkeypatch):
    """「確認 abc」格式錯誤，應回覆錯誤提示，預約不受影響。"""
    OWNER_LINE_ID = "U_owner_fmt"
    monkeypatch.setenv("OWNER_LINE_USER_ID", OWNER_LINE_ID)
    monkeypatch.setenv("LINE_CHANNEL_SECRET", "test-secret")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    replied: list = []

    async def _capture_reply(access_token, reply_token, text):
        replied.append(text)

    monkeypatch.setattr(main_module, "_reply_text_to_line", _capture_reply)
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)

    event = _make_text_event("確認 abc", source_user_id=OWNER_LINE_ID)
    payload = {"events": [event]}
    raw, signature = _sign_body("test-secret", payload)

    resp = client.post("/line/webhook", content=raw, headers={"X-Line-Signature": signature})
    assert resp.status_code == 200
    assert any("格式錯誤" in t for t in replied)
