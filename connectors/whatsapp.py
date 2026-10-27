import hashlib
import hmac
import httpx
from connectors.base import Channel, IncomingMessage
from settings import settings

class WhatsApp(Channel):
    name = "whatsapp"

    def parse(self, payload: dict) -> list[IncomingMessage]:
        out = []
        for entry in payload.get("entry", []):
            for change in entry.get("changes", []):
                for m in change.get("value", {}).get("messages", []):
                    if m.get("type") == "text":   # images/voice come later
                        out.append(IncomingMessage(
                            channel=self.name, user_id=m["from"],
                            message_id=m["id"], text=m["text"]["body"]))
        return out

    async def send(self, user_id: str, text: str) -> None:
        url = (f"https://graph.facebook.com/{settings.graph_version}/"
               f"{settings.whatsapp_phone_number_id}/messages")
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                url,
                headers={"Authorization": f"Bearer {settings.whatsapp_access_token}"},
                json={"messaging_product": "whatsapp", "to": user_id,
                      "type": "text", "text": {"body": text}},
            )
            r.raise_for_status()

def valid_signature(raw: bytes, header: str | None) -> bool:
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(settings.whatsapp_app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))