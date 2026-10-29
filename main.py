import asyncio, json, logging, sys
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from agent import agent
from agent.config import FALLBACK_REPLY, HISTORY_TURNS
from connectors.base import Channel, IncomingMessage
from connectors.whatsapp import WhatsApp, valid_signature
from database import memory
from database.db import init_db
from settings import settings

# Windows consoles default to cp1252 and crash on emoji / Urdu text
for stream in (sys.stdout, sys.stderr):
    stream.reconfigure(encoding="utf-8", errors="replace")
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("madadgar")

whatsapp = WhatsApp()
whatsapp_qr = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global whatsapp_qr
    await init_db()
    if settings.whatsapp_mode == "qr":
        from connectors.whatsapp_qr import WhatsAppQR
        whatsapp_qr = WhatsAppQR()
        whatsapp_qr.start(asyncio.get_running_loop(), handle)
        log.info("WhatsApp QR mode: scan the QR code printed above (first run only)")
    yield
    if whatsapp_qr is not None:
        whatsapp_qr.stop()

app = FastAPI(title="Madadgar", lifespan=lifespan)

@app.get("/webhook/whatsapp")
async def verify(
    mode: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    challenge: str = Query("", alias="hub.challenge"),
):
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return PlainTextResponse(challenge)
    raise HTTPException(403)

@app.post("/webhook/whatsapp")
async def receive(request: Request, bg: BackgroundTasks):
    raw = await request.body()
    if not valid_signature(raw, request.headers.get("X-Hub-Signature-256")):
        raise HTTPException(403)
    for msg in whatsapp.parse(json.loads(raw)):
        bg.add_task(handle, whatsapp, msg)
    return {"status": "ok"}

async def handle(channel: Channel, msg: IncomingMessage) -> None:
    try:
        log.info("message from %s: %s", msg.user_id, msg.text)
        if not await memory.save_inbound(msg):
            return
        history = await memory.load_history(msg.channel, msg.user_id, HISTORY_TURNS)
        ctx = agent.ChatContext(msg.channel, msg.user_id,
                                lambda text: notify_owner(channel, text))
        try:
            reply = await agent.run(history, ctx)
        except Exception:
            log.exception("agent failed for message %s", msg.message_id)
            reply = ""
        if not reply:
            # not saved to history, so the model never sees this canned text
            await channel.send(msg.user_id, FALLBACK_REPLY)
            return
        await memory.save_reply(msg.channel, msg.user_id, reply)
        await channel.send(msg.user_id, reply)
        log.info("replied to %s: %s", msg.user_id, reply)
    except Exception:
        log.exception("failed handling message %s", msg.message_id)

async def notify_owner(channel: Channel, text: str) -> None:
    if not settings.owner_phone:
        log.warning("OWNER_PHONE not set in .env, owner alert not sent:\n%s", text)
        return
    for phone in filter(None, (p.strip() for p in settings.owner_phone.split(","))):
        try:
            await channel.send(channel.owner_id(phone), text)
            log.info("owner %s notified: %s", phone, text.splitlines()[0])
        except Exception:
            # the booking is already saved in the database, so don't fail it
            log.exception("could not send owner alert to %s:\n%s", phone, text)

@app.get("/health")
async def health():
    return {"ok": True}
