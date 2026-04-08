"""SQLAlchemy 資料表 Model"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Date, ForeignKey, Table
from sqlalchemy.orm import relationship

from app.database import Base


# 預約-服務 多對多關聯表
booking_services = Table(
    "booking_services",
    Base.metadata,
    Column("booking_id", Integer, ForeignKey("bookings.id"), primary_key=True),
    Column("service_id", Integer, ForeignKey("services.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    # 舊前端需要的欄位映射：
    # - client_name -> name
    # - contact_mobile -> phone
    # - contact_mail -> contact_mail
    # - provider -> provider
    name = Column(String(100), nullable=False)
    contact_mail = Column(String(255), unique=True, index=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    provider = Column(String(20), default="local")  # local | google | line

    # OAuth/LINE login 可先建立 user，手機最後一步再補（phone 允許為空）
    phone = Column(String(20), unique=True, index=True, nullable=True)
    google_user_id = Column(String(100), unique=True, index=True, nullable=True)
    line_user_id = Column(String(100), unique=True, index=True, nullable=True)

    photo = Column(String(2048), nullable=True)  # 建議存 S3 公開 URL
    birthday = Column(Date, nullable=True)
    address = Column(String(255), nullable=True)

    role = Column(String(20), default="customer")  # customer | owner
    created_at = Column(DateTime, default=datetime.utcnow)

    # 使用 Booking.user_id 作為關聯鍵（避免與 created_by_owner_id 產生歧義）。
    bookings = relationship(
        "Booking",
        back_populates="user",
        foreign_keys="Booking.user_id",
    )


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), nullable=False, index=True)
    duration_minutes = Column(Integer, default=60)
    price = Column(Integer, default=0)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    bookings = relationship(
        "Booking", secondary=booking_services, back_populates="services"
    )


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    # 被預約的客人（會員）；若為訪客預約，可為空。
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # 訪客姓名（非會員時使用）。
    guest_name = Column(String(100), nullable=True)
    # 訪客手機（非會員時使用）。
    guest_phone = Column(String(20), nullable=True)
    # 代客建立的業主 id；一般客人自行預約時為空。
    created_by_owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    booking_date = Column(DateTime, nullable=False)
    total_duration_minutes = Column(Integer, nullable=False)
    total_price = Column(Integer, nullable=False)
    status = Column(String(20), default="pending")  # pending | confirmed | cancelled | completed
    notes = Column(String(500))
    google_calendar_event_id = Column(String(255), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    services = relationship(
        "Service", secondary=booking_services, back_populates="bookings"
    )


class LineWebhookEvent(Base):
    __tablename__ = "line_webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(String(120), unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
