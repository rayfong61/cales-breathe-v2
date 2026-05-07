from datetime import datetime, timedelta
from uuid import uuid4

import app.main as main_module
from app.models import User


def _auth_cookies(user_id: int) -> dict[str, str]:
    token = main_module._create_access_token(user_id)
    return {main_module.JWT_COOKIE_NAME: token}


def _create_user(client, name: str, role: str = "customer", line_user_id: str | None = None) -> int:
    db = main_module.SessionLocal()
    try:
        phone = f"09{uuid4().int % 100000000:08d}"
        uid_line = line_user_id or f"{name}-line-id"
        mail = f"{uuid4().hex[:12]}@pytest.example.com"
        u = User(
            name=name,
            phone=phone,
            line_user_id=uid_line,
            role=role,
            contact_mail=mail,
            provider="local",
        )
        db.add(u)
        db.commit()
        db.refresh(u)
        return u.id
    finally:
        db.close()


def _get_service_ids_by_category(client, category: str) -> list[int]:
    response = client.get("/services")
    assert response.status_code == 200
    return [item["id"] for item in response.json() if item["category"] == category]


def _create_booking(
    client,
    actor_user_id: int,
    service_ids: list[int],
    when: datetime,
    *,
    target_user_id: int | None = None,
    add_by_owner: int | None = None,
):
    payload = {
        "service_ids": service_ids,
        "booking_date": when.isoformat(),
        "notes": "pytest booking",
    }
    if add_by_owner is not None:
        payload["add_by_owner"] = add_by_owner
        if target_user_id is not None:
            payload["user_id"] = target_user_id
    elif target_user_id is not None:
        payload["user_id"] = target_user_id
    else:
        payload["user_id"] = actor_user_id

    return client.post(
        "/bookings",
        json=payload,
        cookies=_auth_cookies(actor_user_id),
    )


def test_create_user_and_booking_success(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "alice")
    arm_service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 1, 1, 10, 0, 0)

    booking_resp = _create_booking(client, user_id, [arm_service_id], when)
    assert booking_resp.status_code == 200

    booking = booking_resp.json()
    assert booking["user_id"] == user_id
    assert booking["status"] == "pending"
    assert len(booking["services"]) == 1

    list_resp = client.get("/bookings", cookies=_auth_cookies(user_id))
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    get_resp = client.get(f"/bookings/{booking['id']}", cookies=_auth_cookies(user_id))
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == booking["id"]


def test_create_booking_same_category_rejected(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "bob")
    face_service_ids = _get_service_ids_by_category(client, "臉部")[:2]
    when = datetime(2030, 1, 2, 11, 0, 0)

    response = _create_booking(client, user_id, face_service_ids, when)

    assert response.status_code == 400
    assert "同一分類只能選一項" in response.json()["detail"]


def test_create_booking_service_not_found(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "carol")
    when = datetime(2030, 1, 2, 12, 0, 0)

    response = _create_booking(client, user_id, [999999], when)

    assert response.status_code == 404
    assert response.json()["detail"] == "部分服務不存在"


def test_create_booking_time_conflict(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "dave")
    private_service_id = _get_service_ids_by_category(client, "私密處")[0]
    start = datetime(2030, 1, 3, 9, 0, 0)

    first = _create_booking(client, user_id, [private_service_id], start)
    assert first.status_code == 200

    second = _create_booking(
        client,
        user_id,
        [private_service_id],
        start + timedelta(minutes=30),
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "該時段已被預約"


def test_create_booking_requires_30_minute_grid(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "grid-invalid")
    arm_service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 1, 3, 9, 15, 0)

    response = _create_booking(client, user_id, [arm_service_id], when)

    assert response.status_code == 400
    assert response.json()["detail"] == "預約時間需為 30 分鐘格線（HH:00 或 HH:30）"


def test_create_booking_rejects_past_time(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "past-time-user")
    arm_service_id = _get_service_ids_by_category(client, "手臂")[0]

    now = datetime.now().replace(second=0, microsecond=0)
    minute = 30 if now.minute >= 30 else 0
    past_when = now.replace(minute=minute) - timedelta(hours=1)

    response = _create_booking(client, user_id, [arm_service_id], past_when)
    assert response.status_code == 400
    assert response.json()["detail"] == "不可預約過去時間"


def test_unavailable_dates_marks_fully_booked_day(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    user_id = _create_user(client, "full-day-user")
    service_id = _get_service_ids_by_category(client, "手臂")[0]

    target_day = datetime(2030, 5, 1, 0, 0, 0)
    for hour in range(9, 18):
        when = target_day.replace(hour=hour)
        resp = _create_booking(client, user_id, [service_id], when)
        assert resp.status_code == 200

    dates_resp = client.get("/unavailable-dates")
    assert dates_resp.status_code == 200
    assert "2030-05-01" in dates_resp.json()


def test_owner_can_create_booking_for_customer(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    owner_id = _create_user(client, "owner-create", role="owner")
    customer_id = _create_user(client, "owner-target-customer")
    arm_service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 1, 3, 13, 0, 0)

    response = _create_booking(
        client,
        owner_id,
        [arm_service_id],
        when,
        target_user_id=customer_id,
        add_by_owner=owner_id,
    )

    assert response.status_code == 200
    booking = response.json()
    assert booking["user_id"] == customer_id
    assert booking["status"] == "confirmed"
    assert len(booking["services"]) == 1


def test_non_owner_cannot_create_booking_for_other_customer(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    non_owner_id = _create_user(client, "not-owner-actor")
    target_customer_id = _create_user(client, "not-owner-target")
    arm_service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 1, 3, 14, 0, 0)

    response = _create_booking(
        client,
        non_owner_id,
        [arm_service_id],
        when,
        target_user_id=target_customer_id,
        add_by_owner=non_owner_id,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "僅限 owner 可替他人建立預約"


def test_cancel_booking_permissions_and_not_found(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    owner_id = _create_user(client, "owner-user", role="owner")
    customer1_id = _create_user(client, "eve")
    customer2_id = _create_user(client, "frank")
    leg_service_id = _get_service_ids_by_category(client, "腿部")[0]
    when = datetime(2030, 1, 4, 15, 0, 0)

    booking_resp = _create_booking(client, customer1_id, [leg_service_id], when)
    assert booking_resp.status_code == 200
    booking_id = booking_resp.json()["id"]

    forbidden_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(customer2_id),
    )
    assert forbidden_resp.status_code == 403

    owner_cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(owner_id),
    )
    assert owner_cancel_resp.status_code == 200
    assert owner_cancel_resp.json()["status"] == "cancelled"

    not_found_resp = client.post("/bookings/999999/cancel", cookies=_auth_cookies(owner_id))
    assert not_found_resp.status_code == 404
    assert not_found_resp.json()["detail"] == "預約不存在"


def test_cancel_pending_booking_no_time_restriction(client, monkeypatch):
    """pending 狀態的預約可在 24 小時內取消（尚未確認，不受時間限制）。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    customer_id = _create_user(client, "cancel-pending-user")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=2)

    booking_resp = _create_booking(client, customer_id, [service_id], when)
    assert booking_resp.status_code == 200
    assert booking_resp.json()["status"] == "pending"
    booking_id = booking_resp.json()["id"]

    cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(customer_id),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_cancel_booking_rejected_within_24_hours(client, monkeypatch):
    """confirmed 預約在 24 小時內無法取消。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    customer_id = _create_user(client, "cancel-window-user")
    owner_id = _create_user(client, "cancel-window-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=23)

    booking_resp = _create_booking(client, customer_id, [service_id], when)
    assert booking_resp.status_code == 200
    booking_id = booking_resp.json()["id"]

    # 先由 owner 確認，讓預約進入 confirmed 狀態
    _force_confirm_booking(client, monkeypatch, owner_id, booking_id)

    cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(customer_id),
    )
    assert cancel_resp.status_code == 400
    assert cancel_resp.json()["detail"] == "開約前 24 小時內不可取消"


def test_cancel_booking_allowed_before_24_hours(client, monkeypatch):
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    customer_id = _create_user(client, "cancel-allowed-user")
    owner_id = _create_user(client, "cancel-allowed-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=25)

    booking_resp = _create_booking(client, customer_id, [service_id], when)
    assert booking_resp.status_code == 200
    booking_id = booking_resp.json()["id"]

    _force_confirm_booking(client, monkeypatch, owner_id, booking_id)

    cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(customer_id),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_owner_cancel_booking_pushes_line_to_customer(client, monkeypatch):
    """owner 透過 API 取消預約後，應推播取消通知給客人。"""
    customer_line_id = "U_owner_cancel_target"
    customer_id = _create_user(client, "owner-cancel-customer", line_user_id=customer_line_id)
    owner_id = _create_user(client, "owner-cancel-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 2, 6, 10, 0, 0)

    # 建立預約時先關閉 push，避免干擾驗證
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    booking_id = _create_booking(client, customer_id, [service_id], when).json()["id"]

    push_calls: list = []
    monkeypatch.setattr(
        main_module,
        "_push_text_to_line_sync",
        lambda access_token, user_id, text: push_calls.append((user_id, text)),
    )
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    cancel_resp = client.post(
        f"/bookings/{booking_id}/cancel",
        cookies=_auth_cookies(owner_id),
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"

    assert any(uid == customer_line_id for uid, _ in push_calls), "應推播取消通知給客人"
    cancelled_msg = next(t for uid, t in push_calls if uid == customer_line_id)
    assert "已取消" in cancelled_msg


def _force_confirm_booking(client, monkeypatch, owner_id: int, booking_id: int) -> dict:
    """測試用：monkeypatch JWT cookie auth 為 owner，呼叫 /confirm endpoint。
    
    注意：呼叫前請自行 monkeypatch _push_text_to_line_sync 以攔截 LINE push。
    """
    from app.models import User

    # 用 SQLAlchemy model 建立一個「未附到 session」的 mock 物件，
    # 僅用於 role 驗證，不需要寫入 DB。
    mock_owner = User(id=owner_id, name="mock-owner", role="owner")
    monkeypatch.setattr(main_module, "_get_current_user_from_cookie", lambda req, db: mock_owner)

    resp = client.post(f"/bookings/{booking_id}/confirm")
    assert resp.status_code == 200
    assert resp.json()["status"] == "confirmed"
    return resp.json()


# ---------------------------------------------------------------------------
# 新流程測試：pending → confirm / 推播
# ---------------------------------------------------------------------------

def test_create_booking_returns_pending_status(client, monkeypatch):
    """建立預約後，status 應為 pending（待業主審核）。"""
    push_calls: list = []
    monkeypatch.setattr(
        main_module, "_push_text_to_line_sync",
        lambda access_token, user_id, text: push_calls.append((user_id, text)),
    )
    monkeypatch.setenv("OWNER_LINE_USER_ID", "U_owner_line")
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    user_id = _create_user(client, "pending-customer")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 2, 1, 10, 0, 0)

    resp = _create_booking(client, user_id, [service_id], when)
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"

    assert len(push_calls) == 1
    assert push_calls[0][0] == "U_owner_line"
    assert "新預約待審核" in push_calls[0][1]
    assert "確認" in push_calls[0][1]


def test_confirm_booking_by_owner_via_api(client, monkeypatch):
    """owner 透過 API confirm 後，status 變 confirmed，並推播客人。"""
    customer_line_id = "U_customer_line"
    customer_id = _create_user(client, "confirm-customer", line_user_id=customer_line_id)
    owner_id = _create_user(client, "confirm-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 2, 2, 10, 0, 0)

    # 建立預約時 mock push，避免觸發業主通知 error
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    booking_resp = _create_booking(client, customer_id, [service_id], when)
    assert booking_resp.status_code == 200
    booking_id = booking_resp.json()["id"]

    # 確認前換成 push_calls 追蹤版本
    push_calls: list = []
    monkeypatch.setattr(
        main_module, "_push_text_to_line_sync",
        lambda access_token, user_id, text: push_calls.append((user_id, text)),
    )
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "fake-token")

    confirmed = _force_confirm_booking(client, monkeypatch, owner_id, booking_id)
    assert confirmed["status"] == "confirmed"

    assert any(uid == customer_line_id for uid, _ in push_calls), "應推播通知給客人"
    confirmed_msg = next(t for uid, t in push_calls if uid == customer_line_id)
    assert "已確認" in confirmed_msg


def test_confirm_booking_by_non_owner_rejected(client, monkeypatch):
    """非 owner 角色不可確認預約。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)

    from app.models import User

    customer_id = _create_user(client, "non-owner-confirm")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 2, 3, 10, 0, 0)

    booking_resp = _create_booking(client, customer_id, [service_id], when)
    booking_id = booking_resp.json()["id"]

    mock_customer = User(id=customer_id, name="mock-customer", role="customer")
    monkeypatch.setattr(main_module, "_get_current_user_from_cookie", lambda req, db: mock_customer)
    resp = client.post(f"/bookings/{booking_id}/confirm")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "僅限 owner 可確認預約"


def test_confirm_already_confirmed_rejected(client, monkeypatch):
    """重複 confirm 應回 400。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    customer_id = _create_user(client, "double-confirm-customer")
    owner_id = _create_user(client, "double-confirm-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "手臂")[0]
    when = datetime(2030, 2, 4, 10, 0, 0)

    booking_id = _create_booking(client, customer_id, [service_id], when).json()["id"]
    _force_confirm_booking(client, monkeypatch, owner_id, booking_id)

    resp = client.post(
        f"/bookings/{booking_id}/confirm",
        cookies=_auth_cookies(owner_id),
    )
    assert resp.status_code == 400
    assert "已是確認狀態" in resp.json()["detail"]


def test_list_bookings_includes_pending(client, monkeypatch):
    """GET /bookings 預設應包含 pending 與 confirmed。"""
    monkeypatch.setattr(main_module, "_push_text_to_line_sync", lambda *a, **kw: None)
    customer_id = _create_user(client, "list-pending")
    owner_id = _create_user(client, "list-owner", role="owner")
    service_id = _get_service_ids_by_category(client, "腿部")[0]

    when1 = datetime(2030, 3, 1, 10, 0, 0)
    when2 = datetime(2030, 3, 1, 13, 0, 0)

    b1_id = _create_booking(client, customer_id, [service_id], when1).json()["id"]
    b2_id = _create_booking(client, customer_id, [service_id], when2).json()["id"]

    _force_confirm_booking(client, monkeypatch, owner_id, b1_id)

    all_resp = client.get("/bookings", cookies=_auth_cookies(owner_id))
    statuses = {b["id"]: b["status"] for b in all_resp.json()}
    assert statuses[b1_id] == "confirmed"
    assert statuses[b2_id] == "pending"

    confirmed_only = client.get("/bookings?status=confirmed", cookies=_auth_cookies(owner_id))
    assert all(b["status"] == "confirmed" for b in confirmed_only.json())

    pending_only = client.get("/bookings?status=pending", cookies=_auth_cookies(owner_id))
    assert all(b["status"] == "pending" for b in pending_only.json())


def test_duplicate_phone_allowed_at_database(client):
    """users.phone 非 unique：可儲存多筆相同手機。"""
    db = main_module.SessionLocal()
    try:
        u1 = User(
            name="same-phone-1",
            phone="0911111111",
            line_user_id="same-phone-line-1",
            contact_mail="a1@pytest.example.com",
            role="customer",
            provider="local",
        )
        u2 = User(
            name="same-phone-2",
            phone="0911111111",
            line_user_id="same-phone-line-2",
            contact_mail="a2@pytest.example.com",
            role="customer",
            provider="local",
        )
        db.add(u1)
        db.commit()
        db.add(u2)
        db.commit()

        same_phone_users = db.query(User).filter(User.phone == "0911111111").all()
        assert len(same_phone_users) >= 2
    finally:
        db.close()
