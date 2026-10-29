from dataclasses import dataclass
from typing import Awaitable, Callable
from agents import (Agent, OpenAIChatCompletionsModel, RunContextWrapper, Runner,
                    function_tool, set_tracing_disabled)
from openai import AsyncOpenAI
from settings import settings
from agent import config, schedule
from database import memory

set_tracing_disabled(True)

# Gemini often returns 503 when busy; retry a few times with backoff before giving up
client = AsyncOpenAI(api_key=settings.gemini_api_key, base_url=config.GEMINI_BASE_URL,
                     max_retries=5, timeout=60)

@dataclass
class ChatContext:
    channel: str
    user_id: str
    notify_owner: Callable[[str], Awaitable[None]]  # WhatsApp alert to the owner(s) in OWNER_PHONE

def customer_number(user_id: str) -> str:
    user, _, server = user_id.partition("@")
    if server in ("", "s.whatsapp.net"):
        return "+" + user
    return user_id  # privacy id (e.g. @lid), not a real phone number

def _details(**fields) -> str:
    return "\n".join(f"{k}: {v}" for k, v in fields.items() if v)

def _slots(times) -> str:
    return ", ".join(f"{t:%a %d %b %H:%M}" for t in times) or "none"

@function_tool
async def check_availability(day: str) -> str:
    """List free call times on a date. Use before suggesting or booking a time.

    Args:
        day: The date to check, as "YYYY-MM-DD".
    """
    t = schedule.parse(day + " 00:00")
    if not t:
        return "Invalid date. Use YYYY-MM-DD."
    free = await schedule.free_slots(t.date())
    if free:
        return f"Free on {day}: {_slots(free)}"
    return f"No free time on {day}. Next free times: {_slots(await schedule.next_free(t))}"

@function_tool
async def book_call(ctx: RunContextWrapper[ChatContext], name: str, call_time: str,
                    company: str = "", team_size: str = "", need: str = "",
                    email: str = "", phone: str = "") -> str:
    """Book a demo/consultation call. Only succeeds if the owner is free at that time.

    Args:
        name: Customer's name.
        call_time: Exact date and time of the call, as "YYYY-MM-DD HH:MM" (24-hour).
        company: Customer's company name.
        team_size: Number of employees.
        need: What HR problem they want to solve.
        email: Customer's email, if given.
        phone: Customer's phone number, if they gave a different one.
    """
    t = schedule.parse(call_time)
    if not t:
        return "NOT BOOKED: call_time must be in YYYY-MM-DD HH:MM format."
    problem = await schedule.check(t)
    if problem:
        return (f"NOT BOOKED: {problem}. Offer these free times instead: "
                f"{_slots(await schedule.next_free(t))}")
    c = ctx.context
    when = f"{t:%Y-%m-%d %H:%M}"
    await memory.save_lead(c.channel, c.user_id, status="call_booked", name=name,
                           company=company, team_size=team_size, need=need,
                           email=email, phone=phone, call_time=when)
    await c.notify_owner("📅 *New call booked!*\n" + _details(
        Name=name, Time=f"{t:%A %d %B %Y, %I:%M %p}", Company=company, Team=team_size,
        Need=need, Email=email, Phone=phone, WhatsApp=customer_number(c.user_id)))
    return f"BOOKED for {t:%A %d %B %Y, %I:%M %p}."

@function_tool
async def save_lead(ctx: RunContextWrapper[ChatContext], name: str, need: str,
                    company: str = "", team_size: str = "", email: str = "",
                    phone: str = "") -> str:
    """Save an interested potential client who has not booked a call yet.

    Args:
        name: Customer's name.
        need: What they are interested in.
        company: Customer's company name.
        team_size: Number of employees.
        email: Customer's email, if given.
        phone: Customer's phone number, if they gave a different one.
    """
    c = ctx.context
    await memory.save_lead(c.channel, c.user_id, status="new", name=name,
                           company=company, team_size=team_size, need=need,
                           email=email, phone=phone)
    return "Lead saved for follow-up."

def instructions(ctx: RunContextWrapper[ChatContext], agent: Agent) -> str:
    now = schedule.now()
    return (config.INSTRUCTIONS
            + f"\nCall hours: {schedule.hours_text()}."
            + f"\nToday is {now:%A, %d %B %Y}, current time {now:%H:%M} (Pakistan time).")

madadgar = Agent[ChatContext](
    name="Madadgar",
    instructions=instructions,
    tools=[check_availability, book_call, save_lead],
    model=OpenAIChatCompletionsModel(model=config.MODEL, openai_client=client),
)

async def run(history: list[dict], context: ChatContext) -> str:
    result = await Runner.run(madadgar, history, context=context)
    return str(result.final_output or "").strip()
