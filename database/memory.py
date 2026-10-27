from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from connectors.base import IncomingMessage
from database.db import Message, SessionLocal

async def save_inbound(msg: IncomingMessage) -> bool:
    """Returns False if Meta re-delivered a message we already have."""
    async with SessionLocal() as s:
        s.add(Message(channel=msg.channel, user_id=msg.user_id,
                      external_id=msg.message_id, role="user", text=msg.text))
        try:
            await s.commit()
            return True
        except IntegrityError:
            await s.rollback()
            return False

async def save_reply(channel: str, user_id: str, text: str) -> None:
    async with SessionLocal() as s:
        s.add(Message(channel=channel, user_id=user_id, role="assistant", text=text))
        await s.commit()

async def load_history(channel: str, user_id: str, limit: int) -> list[dict]:
    async with SessionLocal() as s:
        rows = (await s.execute(
            select(Message)
            .where(Message.channel == channel, Message.user_id == user_id)
            .order_by(Message.id.desc())
            .limit(limit)
        )).scalars().all()
    return [{"role": m.role, "content": m.text} for m in reversed(rows)]