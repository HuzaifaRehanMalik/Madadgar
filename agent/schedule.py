"""Works out when the owner is free, from call hours in .env and calls already booked."""
from datetime import date, datetime, timedelta, timezone
from database import memory
from settings import settings

PK = timezone(timedelta(hours=5))  # Pakistan time, no daylight saving
FMT = "%Y-%m-%d %H:%M"
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

def now() -> datetime:
    return datetime.now(PK).replace(tzinfo=None, second=0, microsecond=0)

def parse(text: str) -> datetime | None:
    try:
        return datetime.strptime(text.strip(), FMT)
    except ValueError:
        return None

def _work_days() -> set[int]:
    return {DAYS.index(d.strip().lower()[:3]) for d in settings.call_days.split(",")
            if d.strip().lower()[:3] in DAYS}

def _length() -> timedelta:
    return timedelta(minutes=settings.call_minutes)

def within_hours(t: datetime) -> bool:
    start = t.replace(hour=settings.call_start_hour, minute=0)
    end = t.replace(hour=settings.call_end_hour, minute=0)
    return t.weekday() in _work_days() and start <= t and t + _length() <= end

async def _booked() -> list[datetime]:
    return [t for t in map(parse, await memory.booked_call_times()) if t]

def _clashes(t: datetime, booked: list[datetime]) -> bool:
    return any(abs(t - b) < _length() for b in booked)

def _day_slots(day: date, booked: list[datetime], after: datetime) -> list[datetime]:
    t = datetime(day.year, day.month, day.day, settings.call_start_hour)
    out = []
    while within_hours(t):
        if t > after and not _clashes(t, booked):
            out.append(t)
        t += _length()
    return out

async def free_slots(day: date, limit: int = 12) -> list[datetime]:
    return _day_slots(day, await _booked(), now())[:limit]

async def next_free(after: datetime, limit: int = 3) -> list[datetime]:
    booked, out = await _booked(), []
    after = max(after, now())
    for i in range(30):
        out += _day_slots((after + timedelta(days=i)).date(), booked, after)
        if len(out) >= limit:
            break
    return out[:limit]

async def check(t: datetime) -> str | None:
    """None if the owner is free at t, otherwise the reason it can't be booked."""
    if t <= now():
        return "that time has already passed"
    if not within_hours(t):
        return "it is outside call hours"
    if _clashes(t, await _booked()):
        return "another call is already booked then"
    return None

def hours_text() -> str:
    return (f"{settings.call_days} from {settings.call_start_hour}:00 to "
            f"{settings.call_end_hour}:00, {settings.call_minutes}-minute calls (Pakistan time)")
