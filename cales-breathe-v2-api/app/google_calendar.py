"""Google Calendar 整合：預約建立 / 確認 / 取消時同步行事曆事件。"""
from __future__ import annotations

import json
import os
from datetime import timedelta

from app.models import Booking, User

# Google Calendar colorId 對照
# 1=Lavender 2=Sage(綠) 3=Grape 4=Flamingo 5=Banana(黃)
# 6=Tangerine(橘) 7=Peacock(藍) 8=Blueberry 9=Basil(深綠) 10=Tomato(紅)
_STATUS_COLOR = {
    "pending":   "5",   # 黃：待確認
    "confirmed": "7",   # 藍：已確認
    "completed": "2",   # 綠：已完成
}
_STATUS_LABEL = {
    "pending":   "待確認",
    "confirmed": "已確認",
    "completed": "已完成",
}
_STATUS_PREFIXES = list(_STATUS_LABEL.values())


def _get_service():
    """建立 Google Calendar API 服務物件；未設定時回傳 None。"""
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        return None
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        info = json.loads(raw)
        creds = Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/calendar"],
        )
        return build("calendar", "v3", credentials=creds)
    except Exception as e:
        print(f"[Google Calendar] 初始化失敗：{e}")
        return None


def _calendar_id() -> str:
    return os.getenv("GOOGLE_CALENDAR_ID", "primary").strip()


def _resolve_display_name_phone(booking: Booking, customer: User | None) -> tuple[str, str | None]:
    """會員預約用 User；代訂訪客用 booking 的 guest 欄位。"""
    if customer is not None:
        return customer.name, customer.phone
    guest_name = (booking.guest_name or "").strip()
    guest_phone = (booking.guest_phone or "").strip() or None
    return (guest_name or "訪客"), guest_phone


def _build_body(booking: Booking, customer: User | None, status: str) -> dict:
    """組成 Calendar Event body。"""
    start = booking.booking_date
    end = start + timedelta(minutes=booking.total_duration_minutes)
    service_names = "、".join(s.name for s in booking.services)
    cust_name, cust_phone = _resolve_display_name_phone(booking, customer)
    phone_line = f"電話：{cust_phone}\n" if cust_phone else ""
    notes_line = f"備註：{booking.notes}\n" if booking.notes else ""
    label = _STATUS_LABEL.get(status, status)
    color = _STATUS_COLOR.get(status, "7")

    return {
        "summary": f"{label}：{cust_name}",
        "description": (
            f"預約編號：#{booking.id}\n"
            f"客人：{cust_name}\n"
            f"{phone_line}"
            f"服務項目：{service_names}\n"
            f"總費用：${booking.total_price}\n"
            f"{notes_line}"
        ),
        "start": {"dateTime": start.isoformat(), "timeZone": "Asia/Taipei"},
        "end":   {"dateTime": end.isoformat(),   "timeZone": "Asia/Taipei"},
        "colorId": color,
        "reminders": {
            "useDefault": False,
            "overrides": [
                {"method": "popup", "minutes": 60},
            ],
        },
    }


def create_event(booking: Booking, customer: User | None, status: str = "pending") -> str | None:
    """建立行事曆事件，回傳 event_id；失敗時回傳 None（不中斷預約流程）。"""
    service = _get_service()
    if not service:
        return None
    try:
        body = _build_body(booking, customer, status)
        result = service.events().insert(
            calendarId=_calendar_id(), body=body
        ).execute()
        event_id = result.get("id")
        print(f"[Google Calendar] 建立成功 event_id={event_id} status={status}")
        return event_id
    except Exception as e:
        print(f"[Google Calendar] 建立失敗：{e}")
        return None


def update_event_status(
    event_id: str,
    booking: Booking,
    customer: User | None,
    status: str,
) -> None:
    """更新事件的標題與顏色以反映新狀態；失敗只 log，不中斷流程。"""
    if not event_id:
        return
    service = _get_service()
    if not service:
        return
    try:
        cal_id = _calendar_id()
        event = service.events().get(calendarId=cal_id, eventId=event_id).execute()

        # 移除舊狀態前綴，換上新的
        cust_name, _ = _resolve_display_name_phone(booking, customer)
        summary = event.get("summary", f"預約：{cust_name}")
        for prefix in _STATUS_PREFIXES:
            if summary.startswith(f"{prefix}："):
                summary = summary[len(prefix) + 1:]
                break

        label = _STATUS_LABEL.get(status, status)
        event["summary"] = f"{label}：{summary}"
        event["colorId"] = _STATUS_COLOR.get(status, "7")

        service.events().update(
            calendarId=cal_id, eventId=event_id, body=event
        ).execute()
        print(f"[Google Calendar] 更新成功 event_id={event_id} status={status}")
    except Exception as e:
        print(f"[Google Calendar] 更新失敗：{e}")


def delete_event(event_id: str) -> None:
    """刪除行事曆事件；失敗只 log，不中斷流程。"""
    if not event_id:
        return
    service = _get_service()
    if not service:
        return
    try:
        service.events().delete(
            calendarId=_calendar_id(), eventId=event_id
        ).execute()
        print(f"[Google Calendar] 刪除成功 event_id={event_id}")
    except Exception as e:
        print(f"[Google Calendar] 刪除失敗：{e}")
