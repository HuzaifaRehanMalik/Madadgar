from abc import ABC, abstractmethod
from pydantic import BaseModel

class IncomingMessage(BaseModel):
    channel: str      # "whatsapp" | "instagram" | "messenger"
    user_id: str
    message_id: str
    text: str

class Channel(ABC):
    name: str

    @abstractmethod
    def parse(self, payload: dict) -> list[IncomingMessage]: ...

    @abstractmethod
    async def send(self, user_id: str, text: str) -> None: ...