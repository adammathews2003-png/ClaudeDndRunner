"""In-game time: `Day N HH:MM` parse/format/add (docs/design/06 → `clock advance`,
L359-378 incl. the named times at L377-378; docs/design/05 #7; plan.md Phase 1 item 4).

A time is a tuple `(day, minute)` with `minute` in 0..1439. Days may be <= 0
(pre-campaign, docs/design/04 L18-21).
"""
import re

NAMED = {
    "midnight": 0, "pre-dawn": 4 * 60, "dawn": 6 * 60, "morning": 8 * 60,
    "noon": 12 * 60, "afternoon": 15 * 60, "dusk": 18 * 60, "evening": 19 * 60,
    "night": 22 * 60,
}
# periods for the brief line: the latest named time <= the clock
_PERIODS = sorted(NAMED.items(), key=lambda kv: kv[1])

DAY = 24 * 60

_TIME = re.compile(r"^\s*Day\s+(-?\d+)[ ,]+(\d{1,2}):(\d{2})\s*$", re.I)
_CLOCK = re.compile(r"^\s*(\d{1,2}):(\d{2})\s*$")
_DELTA = re.compile(r"^\s*\+\s*((?:\d+\s*[dhm]\s*)+)\s*$", re.I)


class TimeError(ValueError):
    pass


def parse(text):
    """'Day 1 19:30' -> (1, 1170)."""
    m = _TIME.match(str(text).strip().strip('"'))
    if not m:
        raise TimeError(f"not a time: {text!r} (want 'Day N HH:MM')")
    day, hh, mm = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if hh > 23 or mm > 59:
        raise TimeError(f"bad clock in {text!r}")
    return day, hh * 60 + mm


def parse_clock(text):
    """'06:00' or a named time -> minute of day."""
    text = str(text).strip().lower()
    if text in NAMED:
        return NAMED[text]
    m = _CLOCK.match(text)
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise TimeError(f"not a clock time: {text!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def fmt(day, minute=None):
    """(1, 1170) -> 'Day 1 19:30'. Accepts a tuple too."""
    if minute is None:
        day, minute = day
    return f"Day {day} {minute // 60:02d}:{minute % 60:02d}"


def fmt_clock(minute):
    """425 -> '07:05'."""
    return f"{minute // 60:02d}:{minute % 60:02d}"


def normalize(day, minute):
    """Carry minutes outside 0..1439 into the day."""
    day += minute // DAY
    return day, minute % DAY


def parse_delta(spec):
    """'+4h30m' | '+20m' | '+1d' | '+1d 3h' -> minutes."""
    m = _DELTA.match(spec)
    if not m:
        raise TimeError(f"not a duration: {spec!r} (want +Nd, +Nh, +Nm or combinations)")
    total = 0
    for num, unit in re.findall(r"(\d+)\s*([dhm])", m.group(1).lower()):
        total += int(num) * {"d": DAY, "h": 60, "m": 1}[unit]
    return total


def add(t, spec):
    """Advance (day, minute) by '+4h30m' | '+1d' | 'to 06:00' | 'to dawn'.
    'to X' means the next occurrence of X after t (so 'to 06:00' at 06:00 is a day).
    Returns the new (day, minute)."""
    day, minute = t
    spec = str(spec).strip()
    if spec.lower().startswith("to "):
        target = parse_clock(spec[3:])
        if target > minute:
            return day, target
        return day + 1, target
    if not spec.startswith("+"):
        spec = "+" + spec
    return normalize(day, minute + parse_delta(spec))


def diff(a, b):
    """Minutes from a to b (b - a)."""
    return (b[0] - a[0]) * DAY + (b[1] - a[1])


def fmt_delta(minutes):
    """90 -> '1h30m'; 1670 -> '1d 3h50m'; 0 -> '0m'."""
    sign = "-" if minutes < 0 else ""
    minutes = abs(minutes)
    d, rem = divmod(minutes, DAY)
    h, m = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    hm = (f"{h}h" if h else "") + (f"{m}m" if m else "")
    if hm:
        parts.append(hm)
    return sign + (" ".join(parts) if parts else "0m")


def period(t):
    """Name of the period of day for the brief line: midnight, pre-dawn, dawn,
    morning, noon, afternoon, dusk, evening, night."""
    minute = t[1] if isinstance(t, tuple) else int(t)
    name = _PERIODS[0][0]
    for label, start in _PERIODS:
        if minute >= start:
            name = label
    return name


def between(t, start, end):
    """True when t's clock lies in [start, end). Windows may wrap midnight:
    between('23:30', '22:00', '02:00') is True. `t` is (day, minute), a minute of
    day, or a clock string; start/end are clock strings, named times or minutes.
    start == end means the whole day."""
    def minute_of(x):
        if isinstance(x, tuple):
            return x[1]
        if isinstance(x, int):
            return x % DAY
        return parse_clock(x)
    m, s, e = minute_of(t), minute_of(start), minute_of(end)
    if s == e:
        return True
    if s < e:
        return s <= m < e
    return m >= s or m < e


def parse_window(text):
    """'04:00–00:00' (en dash or hyphen) -> (start_minute, end_minute)."""
    m = re.match(r"^\s*(\d{1,2}:\d{2})\s*[–-]\s*(\d{1,2}:\d{2})\s*$", text)
    if not m:
        raise TimeError(f"not a time window: {text!r}")
    return parse_clock(m.group(1)), parse_clock(m.group(2))
