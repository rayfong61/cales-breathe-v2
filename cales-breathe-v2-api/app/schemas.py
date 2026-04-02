"""Pydantic 請求/回應 Schema"""
from datetime import datetime, date
from pydantic import BaseModel, field_validator


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
    user_id: int
    add_by_owner: int | None = None
    service_ids: list[int]
    booking_date: datetime
    notes: str | None = None

    @field_validator("service_ids") #對 service_ids 這個欄位做額外檢查
    @classmethod
    def service_ids_not_empty(cls, v: list[int]) -> list[int]:
        if not v:
            raise ValueError("至少需選擇一項服務")
        return v


class BookingCancel(BaseModel):
    """取消預約時須帶入操作者 user_id（預約本人或 owner）"""
    user_id: int


class BookingRead(BaseModel):
    id: int
    user_id: int
    booking_date: datetime
    total_duration_minutes: int
    total_price: int
    status: str
    notes: str | None
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
