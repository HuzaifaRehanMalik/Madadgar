import asyncio
import threading
from neonize.client import NewClient
from neonize.events import MessageEv
from neonize.utils import build_jid
from connectors.base import Channel, IncomingMessage

class WhatsAppQR(Channel):
    name = "whatsapp_qr"

    def __init__(self) -> None:
        self.client = NewClient("whatsapp_session.sqlite3")  # login is saved here

    def parse(self, payload: dict) -> list[IncomingMessage]:
        return []  # not used: messages arrive through start() below

    def start(self, loop: asyncio.AbstractEventLoop, on_message) -> None:
        @self.client.event(MessageEv)
        def _on_message(client, ev: MessageEv):
            src = ev.Info.MessageSource
            if src.IsFromMe or src.IsGroup:
                return
            m = ev.Message
            text = m.conversation or m.extendedTextMessage.text
            if not text:
                return
            msg = IncomingMessage(
                channel=self.name,
                user_id=f"{src.Chat.User}@{src.Chat.Server}",
                message_id=ev.Info.ID,
                text=text,
            )
            # neonize calls this from its own thread, so hand off to the asyncio loop
            asyncio.run_coroutine_threadsafe(on_message(self, msg), loop)

        # connect() blocks and prints the QR in the terminal on first run
        threading.Thread(target=self.client.connect, daemon=True).start()

    def owner_id(self, phone: str) -> str:
        return super().owner_id(phone) + "@s.whatsapp.net"

    def stop(self) -> None:
        try:
            self.client.stop()  # ends the blocking connect() thread
        except Exception:
            pass

    async def send(self, user_id: str, text: str) -> None:
        user, server = user_id.split("@", 1)
        await asyncio.to_thread(self.client.send_message, build_jid(user, server), text)