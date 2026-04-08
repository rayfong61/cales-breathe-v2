"""刪除帳號：須先清 booking_services，否則外鍵會阻擋刪除預約。"""
from datetime import datetime

import app.main as main_module
from tests.test_bookings import _get_service_ids_by_category


def test_delete_account_removes_user_and_bookings_with_services(client, monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-for-delete-account-!")
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)

    reg = client.post(
        "/register",
        json={
            "client_name": "Delete Me",
            "contact_mail": "delete-me-account@example.com",
            "password": "secret-pass-123",
        },
    )
    assert reg.status_code == 200
    user_id = reg.json()["user"]["id"]

    arm_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 6, 15, 14, 0, 0)
    book = client.post(
        "/bookings",
        json={
            "user_id": user_id,
            "service_ids": [arm_id],
            "booking_date": when.isoformat(),
            "notes": "pytest",
        },
    )
    assert book.status_code == 200

    del_resp = client.delete("/account")
    assert del_resp.status_code == 200
    assert del_resp.json().get("message") == "帳號已刪除"

    me = client.get("/me")
    assert me.status_code == 401
