import json, logging
from contextlib import asynccontextmanager
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from agent import agent
from agent.config import HISTORY_TURNS
from connectors.base import Channel, IncomingMessage
from connectors.whatsapp import WhatsApp, valid_signature
from database import memory
from database.db import init_db
from settings import settings

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("madadgar")

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield

app = FastAPI(title="Madadgar", lifespan=lifespan)
whatsapp = WhatsApp()

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
        if not await memory.save_inbound(msg):
            return
        history = await memory.load_history(msg.channel, msg.user_id, HISTORY_TURNS)
        reply = await agent.run(history)
        await memory.save_reply(msg.channel, msg.user_id, reply)
        await channel.send(msg.user_id, reply)
    except Exception:
        log.exception("failed handling message %s", msg.message_id)

@app.get("/health")
async def health():
    return {"ok": True}