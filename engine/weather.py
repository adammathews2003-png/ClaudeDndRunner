"""Weather (docs/design/02 → Table mechanics → Phase 15 → Weather; 04 → Scene state added
(`weather:`), Area frontmatter `climate:`; 06 → Table mechanics → Phase 15; plan.md
Phase 15 item 7).

    weather                                  what it is now
    weather roll                             roll today's weather (the clock does it at dawn)
    weather set "heavy rain, strong wind, cold"
    weather clear                            forget it

`weather: off | on` (default off; nothing here runs while it's off, and the commands
other than the bare `weather` refuse). At each dawn the clock rolls d20 three times per
the party area's `climate:` (the site's, else up its `parent:` chain; default temperate):
- temperature: 1–14 the climate's normal, 15–17 colder by 1d4 × 10 °F, 18–20 warmer;
- wind: 1–12 calm, 13–17 light, 18–20 strong;
- precipitation: 1–12 clear, 13–17 light, 18–20 heavy (snow at or below 32 °F),
and writes `weather-now: "light rain, light wind, cool"` to current.md (not `weather:`,
the setting's own key, which a campaign without campaign.md keeps in current.md too). Effects apply only
outdoors (not in a site whose `type` is a building, dungeon, cave … or tagged `indoors`):
- strong wind: ranged weapon attacks at disadvantage (roll.py), open flames go out —
  carried torches and candles in `lit:` (lanterns don't) — and non-magical flight is
  grounded; Perception by hearing at disadvantage (a note: the tool can't tell the sense);
- heavy rain or snow: lightly obscured — Perception by sight at disadvantage (a note);
- 0 °F or below / 100 °F or above: `environment: extreme-cold | extreme-heat` (Phase 14's
  hourly saves); the next roll that isn't extreme clears an environment weather set.
The brief header carries it (`· light rain, cool`; `calm` and `clear` left out).

Python API: `dawn_lines(old, new, roller)` (clock), `ranged_note(atk, dist)` (roll.py),
`perception_note()`, `header_bit(state)` (brief), `light_warning(doc)` (supplies.light).
"""
import re

from lib import campaign, dice, journal, light as lightdata, md
from lib.errors import ToolError

KEY = "weather-now"   # current.md; not `weather`, which is the setting's key (04 → Table settings)
CLIMATES = {"arctic": 0, "cold": 30, "temperate": 60, "warm": 75, "tropical": 85, "desert": 95,
            "mountain": 40, "coast": 60}
SHELTER = ("building", "dungeon", "cave", "cavern", "interior", "underground", "tunnel", "sewer", "keep", "tower")
TEMPS = ((0, "bitter cold"), (32, "freezing"), (50, "cold"), (65, "cool"), (79, "mild"), (94, "warm"),
         (99, "hot"))
EXTREME = {"bitter cold": "extreme-cold", "scorching": "extreme-heat"}
OPEN_FLAMES = ("torch", "candle")


class WeatherError(ToolError):
    pass


def on():
    return str(campaign.settings().get("weather", "off")).strip().lower() == "on"


def _require():
    if not on():
        raise WeatherError("weather: off (campaign setting `weather: on` turns it on)")


def current(state=None):
    state = state or campaign.load_state()
    return str(state.front.get(KEY) or "").strip()


def parts(text):
    """{precip: clear|light|heavy, wind: calm|light|strong, temp: label, snow: bool}."""
    t = str(text or "").lower()
    precip = "heavy" if re.search(r"heavy (rain|snow|sleet)|downpour|blizzard", t) else \
        "light" if re.search(r"(light )?(rain|snow|drizzle|sleet)", t) else "clear"
    wind = "strong" if re.search(r"strong wind|gale|storm", t) else "light" if "wind" in t else "calm"
    temp = next((label for _, label in TEMPS + ((999, "scorching"),) if label in t), "")
    return {"precip": precip, "wind": wind, "temp": temp, "snow": "snow" in t or "blizzard" in t}


def label(f):
    for top, name in TEMPS:
        if f <= top:
            return name
    return "scorching"


def _loc_doc(slug):
    p = campaign.root() / "locations" / f"{slug}.md"
    return md.load(p) if p.exists() else None


def climate(state=None):
    """The party area's `climate:` (site, then up the `parent:` chain), else temperate."""
    state = state or campaign.load_state()
    slug = str(state.front.get("party-location") or "").split("/")[0].lstrip("@")
    seen = set()
    while slug and slug not in seen:
        seen.add(slug)
        doc = _loc_doc(slug)
        if doc is None:
            break
        c = str(doc.front.get("climate") or "").strip().lower()
        if c:
            return c if c in CLIMATES else "temperate"
        slug = str(doc.front.get("parent") or "").strip()
    return "temperate"


def outdoors(state=None):
    """Is the party under the sky? Not inside a site whose `type` is a shelter or that is
    tagged `indoors`/`underground`; on the road or lost they are outdoors."""
    state = state or campaign.load_state()
    loc = str(state.front.get("party-location") or "")
    if not loc or loc.startswith("@"):
        return True
    doc = _loc_doc(loc.split("/")[0])
    if doc is None:
        return True
    tags = doc.front.get("tags") or []
    tags = [str(x).strip().lower() for x in (tags if isinstance(tags, list) else [tags])]
    kind = str(doc.front.get("type") or "").strip().lower()
    return not (kind in SHELTER or "indoors" in tags or "underground" in tags)


def roll(roller):
    """(text, detail) for one day's weather in the party's climate."""
    clim = climate()
    base = CLIMATES.get(clim, 60)
    t, w, p = roller.die(20), roller.die(20), roller.die(20)
    temp = base
    shift = ""
    if 15 <= t <= 17:
        n = roller.die(4)
        temp -= 10 * n
        shift = f" −{10 * n}°F"
    elif t >= 18:
        n = roller.die(4)
        temp += 10 * n
        shift = f" +{10 * n}°F"
    wind = "calm" if w <= 12 else "light wind" if w <= 17 else "strong wind"
    kind = "snow" if temp <= 32 else "rain"
    precip = "clear" if p <= 12 else f"light {kind}" if p <= 17 else f"heavy {kind}"
    text = f"{precip}, {wind}, {label(temp)}"
    detail = f"{clim} · temperature d20 {t}{shift} ({temp}°F) · wind d20 {w} · precipitation d20 {p}"
    return text, detail


def _snuff(state):
    """Strong wind outdoors: put out carried open flames (PCs in the scene, NPC files on
    stage). -> lines."""
    out = []
    docs = campaign.scene_pcs(include_absent=True)
    docs += [m.doc for m in campaign.stage_matches(state) if m.doc is not None and not m.is_pc]
    for d in docs:
        doc = md.load(d.path)
        items = lightdata.entries(doc.front)
        gone = [src for src, _ in items if src in OPEN_FLAMES]
        if not gone:
            continue
        kept = [lightdata.fmt_entry(src, left) for src, left in items if src not in OPEN_FLAMES]
        if kept:
            doc.set_front("lit", kept)
        else:
            doc.del_front("lit")
        doc.save()
        who = str(doc.front.get("name") or "?").split()[0]
        for src in gone:
            name = lightdata.SOURCES[src][3]
            journal.log_delta(f"light {who} {name} out (strong wind)")
            out.append(f"Light out: {who}'s {name} (strong wind)")
    return out


def apply(text, why, state=None):
    """Write `weather:` and apply what it does now. -> lines."""
    state = state or campaign.load_state()
    old = current(state)
    state.set_front(KEY, text)
    state.save()
    journal.log_delta(f"weather {why}: {text}" + (f" (was {old})" if old else ""))
    lines = [f"[weather {why}: {text}]"]
    p = parts(text)
    out = outdoors(state)
    effects = []
    if p["wind"] == "strong":
        effects.append("strong wind: ranged weapon attacks at disadvantage, Perception by hearing at "
                       "disadvantage, open flames go out, non-magical flight grounded")
    if p["precip"] == "heavy":
        effects.append("heavy " + ("snow" if p["snow"] else "rain") + ": lightly obscured "
                       "(Perception by sight at disadvantage)")
    if effects:
        lines.append("  " + " · ".join(effects) + ("" if out else " — outdoors only (the party is under a roof)"))
    if p["wind"] == "strong" and out:
        lines += ["  " + x for x in _snuff(campaign.load_state())]
    import hazard
    env = hazard.env()
    want = EXTREME.get(p["temp"])
    was = EXTREME.get(parts(old)["temp"]) if old else None
    if want and env != want:
        lines += ["  " + x for x in hazard.set_env(want)]
    elif not want and was and env == was:
        lines += ["  " + x for x in hazard.set_env("none")]
    return lines


def dawn_lines(old, new, roller=None):
    """Clock: roll the weather at the last dawn crossed in (old, new] (`weather: on`)."""
    if not on():
        return []
    from lib import gametime
    dawn = gametime.NAMED["dawn"]
    days = [d for d in range(old[0], new[0] + 1)
            if gametime.diff(old, (d, dawn)) > 0 and gametime.diff((d, dawn), new) >= 0]
    if not days:
        return []
    roller = roller or dice.Roller()
    text, detail = roll(roller)
    journal.log_delta(f"weather roll Day {days[-1]}: {detail}", gm=True)
    return ["  " + x.strip() if not x.startswith("  ") else x for x in apply(text, f"Day {days[-1]} dawn")]


def _wind_now():
    if not on():
        return False
    state = campaign.load_state()
    return parts(current(state))["wind"] == "strong" and outdoors(state)


def ranged_note(atk, dist=None):
    """roll.attack: strong wind outdoors gives disadvantage on a ranged weapon attack. A
    thrown weapon counts as ranged when it is more than 5 ft away (or has no distance
    and isn't a melee weapon). -> note or ''."""
    rng = str(atk.get("range") or "")
    if "/" not in rng:
        return ""
    if "thrown" in str(atk.get("notes") or "").lower() and (dist is None or dist <= 5):
        return ""
    return "strong wind: ranged at disadvantage" if _wind_now() else ""


def perception_note():
    """roll.ability_check for Perception: the weather's senses note, or ''."""
    if not on():
        return ""
    state = campaign.load_state()
    if not outdoors(state):
        return ""
    p = parts(current(state))
    bits = []
    if p["precip"] == "heavy":
        bits.append("by sight at disadvantage (heavy " + ("snow" if p["snow"] else "rain") + ")")
    if p["wind"] == "strong":
        bits.append("by hearing at disadvantage (strong wind)")
    return "weather: " + ", ".join(bits) if bits else ""


def light_warning():
    """supplies.light: lighting an open flame in a strong wind outdoors."""
    return "[strong wind: an open flame won't stay lit out here]" if _wind_now() else ""


def header_bit(state):
    """The brief header's `· light rain, cool` (weather on and set)."""
    if not on():
        return ""
    text = current(state)
    if not text:
        return ""
    shown = [x.strip() for x in text.split(",") if x.strip() and x.strip().lower() not in ("calm", "clear")]
    return " · " + (", ".join(shown) or text)


# ---------- CLI ----------

def cmd_weather(ctx):
    a = ctx.args
    if a.action is None:
        text = current()
        lines = [f"[weather: {text or 'not set'} · {'on' if on() else 'off'} · climate {climate()}"
                 + ("" if outdoors() else " · the party is under a roof") + "]"]
    elif a.action == "roll":
        _require()
        text, detail = roll(ctx.roller)
        journal.log_delta(f"weather roll: {detail}", gm=True)
        lines = apply(text, "roll")
    elif a.action == "set":
        _require()
        if not a.text:
            raise WeatherError('weather set "heavy rain, strong wind, cold"')
        lines = apply(" ".join(a.text).strip(), "set")
    else:
        _require()
        state = campaign.load_state()
        if not current(state):
            raise WeatherError("weather clear: no weather is set")
        state.del_front(KEY)
        state.save()
        journal.log_delta("weather cleared")
        lines = ["[weather cleared]"]
    for line in lines:
        ctx.emit(line)
    ctx.result = {"lines": lines}


def register(sub, g):
    p = sub.add_parser("weather", parents=[g], help='weather [roll | set "…" | clear]')
    p.add_argument("action", nargs="?", choices=["roll", "set", "clear"])
    p.add_argument("text", nargs="*")
    p.set_defaults(func=cmd_weather)
