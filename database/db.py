from datetime import datetime
from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, func, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from settings import settings

def _async_url(url: str) -> tuple[str, dict]:
    """Neon gives a plain postgresql:// URL with libpq params; asyncpg needs its own driver + ssl arg."""
    u = make_url(url)
    if u.drivername in ("postgresql", "postgres"):
        u = u.set(drivername="postgresql+asyncpg")
    connect_args = {}
    if u.drivername == "postgresql+asyncpg":
        q = dict(u.query)
        if q.pop("sslmode", None) in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = True
        q.pop("channel_binding", None)  # asyncpg doesn't accept this
        u = u.set(query=q)
    return u.render_as_string(hide_password=False), connect_args

_url, _connect_args = _async_url(settings.database_url)
engine = create_async_engine(_url, connect_args=_connect_args, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("channel", "external_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20), index=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # Meta's message id
    role: Mapped[str] = mapped_column(String(10))  # "user" | "assistant"
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(20))  # "new" | "call_booked"
    name: Mapped[str] = mapped_column(String(120), default="")
    company: Mapped[str] = mapped_column(String(200), default="")
    team_size: Mapped[str] = mapped_column(String(50), default="")
    need: Mapped[str] = mapped_column(Text, default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    call_time: Mapped[str] = mapped_column(String(100), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)   # swap for Alembic later