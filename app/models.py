from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import String, Date, DateTime, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

class Bill(Base):
    __tablename__="bills"
    id: Mapped[int]=mapped_column(primary_key=True)
    provider: Mapped[str]=mapped_column(String(120),default="Da verificare")
    category: Mapped[str]=mapped_column(String(40),default="Altro")
    amount: Mapped[Decimal|None]=mapped_column(Numeric(10,2),nullable=True)
    due_date: Mapped[date|None]=mapped_column(Date,nullable=True)
    status: Mapped[str]=mapped_column(String(30),default="DA_PAGARE")
    invoice_number: Mapped[str|None]=mapped_column(String(120),nullable=True)
    pdf_path: Mapped[str|None]=mapped_column(String(500),nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)

class EmailAccount(Base):
    __tablename__="email_accounts"
    id: Mapped[int]=mapped_column(primary_key=True)
    provider: Mapped[str]=mapped_column(String(30))
    email: Mapped[str]=mapped_column(String(255),default="")
    auth_type: Mapped[str]=mapped_column(String(20),default="oauth")
    secret: Mapped[str|None]=mapped_column(Text,nullable=True)
    refresh_token: Mapped[str|None]=mapped_column(Text,nullable=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    last_sync: Mapped[datetime|None]=mapped_column(DateTime,nullable=True)
    last_error: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,default=datetime.utcnow)
