"""Pydantic 請求/回應 Schema"""
from datetime import datetime, date
from pydantic import BaseModel, field_validator, model_validator


class ServiceBase(BaseModel):
    name: str
    category: str
    duration_minutes: int = 60
    price: int = 0
    sort_order: int = 0


class ServiceCreate(ServiceBase):
    pass


class ServiceRead(BaseModel):
    id: int
    name: str
    category: str
    duration_minutes: int
    price: int
    sort_order: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserBase(BaseModel):
    name: str
    line_user_id: str | None = None
    phone: str | None = None
    contact_mail: str | None = None
    provider: str = "local"
    photo: str | None = None
    birthday: date | None = None
    address: str | None = None
    role: str = "customer"


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class BookingCreate(BaseModel):
    # 被預約的會員 id；若為訪客可為 None
    user_id: int | None = None
    # 代客建立的業主 id（僅 owner 可帶）
    add_by_owner: int | None = None
    # 訪客姓名（非會員時使用）
    guest_name: str | None = None
    # 訪客手機（非會員時使用）
    guest_phone: str | None = None
    service_ids: list[int]
    booking_date: datetime
    notes: str | None = None

    @field_validator("service_ids") #對 service_ids 這個欄位做額外檢查
    @classmethod
    def service_ids_not_empty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("至少需選擇一項服務")
        return v

    @field_validator("guest_name")
    @classmethod
    def strip_guest_name(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @field_validator("guest_phone")
    @classmethod
    def strip_guest_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        return v or None

    @model_validator(mode="after")
    def ensure_user_or_guest(self):
        if self.user_id is None and not self.guest_name:
            raise ValueError("user_id 與 guest_name 至少需擇一提供")
        return self


class BookingCancel(BaseModel):
    """取消預約時須帶入操作者 user_id（預約本人或 owner）"""
    user_id: int


class BookingRead(BaseModel):
    id: int
    user_id: int | None
    booking_date: datetime
    total_duration_minutes: int
    total_price: int
    status: str
    notes: str | None
    guest_name: str | None = None
    guest_phone: str | None = None
    created_by_owner_id: int | None = None
    google_calendar_event_id: str | None = None
    created_at: datetime
    services: list[ServiceRead] = []

    class Config:
        from_attributes = True


# ----------------------------
# Legacy/BFF adaptor schemas
# ----------------------------

class LegacyMeResponse(BaseModel):
    user: dict | None


class LegacyLoginRequest(BaseModel):
    contact_mail: str
    password: str


class LegacyLoginResponse(BaseModel):
    message: str
    user: dict


class LegacyRegisterRequest(BaseModel):
    client_name: str
    contact_mail: str
    password: str


class LegacyAccountUpdate2Request(BaseModel):
    client_name: str
    contact_mobile: str


class LegacyUnavailableTimeRange(BaseModel):
    start_time: str  # "HH:MM:SS"
    end_time: str    # "HH:MM:SS"


class LegacyOrderDetail(BaseModel):
    services: list[str] = []
    addons: list[str] = []


class LegacyOrderRead(BaseModel):
    id: int
    booking_date: str          # "YYYY-MM-DD"
    booking_time: str          # "HH:MM:SS"
    total_price: int
    total_duration: int
    booking_note: str | None = None
    is_cancelled: bool
    status: str                # pending | confirmed | cancelled | completed
    booking_detail: LegacyOrderDetail
    # 代客/訪客資訊（若有）
    guest_name: str | None = None
    created_by_owner_id: int | None = None
    customer_id: int | None = None
    customer_name: str | None = None
    customer_photo: str | None = None
    customer_phone: str | None = None
