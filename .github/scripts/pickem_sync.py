#!/usr/bin/env python3
"""
Pull the Big 12 slate from ESPN and upsert it into Supabase.

Runs on a schedule from .github/workflows/pickem-sync.yml. Two jobs in one:
  1. keeps the upcoming schedule current (new weeks appear automatically)
  2. writes final scores + winners so the leaderboard scores itself

Only needs the ESPN public scoreboard, which takes no API key.

Env:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   service_role key (bypasses RLS -- never ship to browser)
  SEASON                 optional, defaults to the current football season
  WEEKS                  optional, e.g. "1-16". Defaults to 1-16.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ESPN = ("https://site.api.espn.com/apis/site/v2/sports/football/"
        "college-football/scoreboard")
LOCAL_TZ = ZoneInfo("America/Denver")
BIG12_GROUP = 4          # ESPN's conference id for the Big 12
REGULAR_SEASON = 2       # seasontype: 1=pre, 2=regular, 3=post

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]


def window_opens(first_kickoff):
    """Sunday 06:00 Mountain preceding a week's first kickoff.

    Lines freeze at this moment, which is also when picking opens. Freezing at
    kickoff instead would quietly reward waiting until Thursday, when the line
    is sharpest -- the opposite of the point.

    timedelta arithmetic on an aware datetime is wall-clock, not absolute, so
    stepping back whole days stays correct across the November clock change.
    """
    local = first_kickoff.astimezone(LOCAL_TZ)
    midnight = local.replace(hour=0, minute=0, second=0, microsecond=0)
    # weekday(): Monday is 0, Sunday is 6. Step back to the most recent Sunday.
    sunday = midnight - timedelta(days=(midnight.weekday() + 1) % 7)
    opens = sunday.replace(hour=6)
    # A game starting before 6am Sunday would otherwise open its own window
    # after kickoff, leaving nobody able to pick it at all.
    return opens - timedelta(days=7) if opens >= local else opens


def parse_ts(value):
    """ESPN timestamps look like 2026-09-04T00:00Z."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def existing_spreads(season):
    """Which games already have a line recorded, so we never move one."""
    url = (f"{SUPABASE_URL}/rest/v1/pickem_games"
           f"?select=id,home_spread&season=eq.{season}&home_spread=not.is.null")
    req = urllib.request.Request(url, headers={
        "apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return {r["id"] for r in json.loads(resp.read().decode("utf-8"))}
    except Exception as exc:                                   # noqa: BLE001
        print(f"  could not read existing lines ({exc}); treating all as unset")
        return set()


def football_season(now=None):
    """Aug-Dec belongs to that year; Jan-Jul is the tail of the prior season."""
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 8 else now.year - 1


def get_json(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "byu-pickem/1.0 (+github actions)"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            if attempt == tries:
                raise
            print(f"  retry {attempt}/{tries} after {exc.__class__.__name__}: {exc}")
    return None


SPREAD_RE = re.compile(r"^([A-Za-z&.'\- ]+?)\s+([+-]?\d+(?:\.\d+)?)$")


def parse_spread(comp, home_abbr, away_abbr):
    """Return (home_spread, detail). Negative home_spread means home is favored.

    ESPN's `details` string ("TTU -3.5") names the team it refers to, so it is
    self-describing and preferred. The bare `spread` number is used only as a
    fallback, where ESPN documents it as home-relative.
    """
    odds = comp.get("odds") or []
    if not odds:
        return None, ""
    o = odds[0]
    detail = (o.get("details") or "").strip()

    if detail:
        flat = detail.upper().replace(" ", "")
        if flat in ("EVEN", "PK", "PICK", "PICKEM", "PICK'EM"):
            return 0.0, detail
        m = SPREAD_RE.match(detail)
        if m:
            abbr, num = m.group(1).strip().upper(), float(m.group(2))
            if abbr == (home_abbr or "").upper():
                return num, detail
            if abbr == (away_abbr or "").upper():
                return -num, detail

    sp = o.get("spread")
    if isinstance(sp, (int, float)):
        return float(sp), detail

    return None, detail


def side(competitors, home_away):
    for c in competitors:
        if c.get("homeAway") == home_away:
            return c
    return {}


def as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_event(event, fallback_week, season):
    """Turn one ESPN event into a pickem_games row, or None if unusable."""
    comps = event.get("competitions") or []
    if not comps:
        return None
    comp = comps[0]
    competitors = comp.get("competitors") or []
    if len(competitors) != 2:
        return None

    home, away = side(competitors, "home"), side(competitors, "away")
    if not home or not away:
        return None

    status = ((comp.get("status") or event.get("status") or {})
              .get("type") or {})
    state = status.get("state")           # pre | in | post
    completed = bool(status.get("completed"))
    if completed:
        norm_status = "final"
    elif state == "in":
        norm_status = "in"
    else:
        norm_status = "scheduled"

    winner_id = None
    if norm_status == "final":
        for c in competitors:
            if c.get("winner"):
                winner_id = str((c.get("team") or {}).get("id") or "") or None

    def team_fields(c):
        team = c.get("team") or {}
        rank = c.get("curatedRank") or {}
        rank_val = as_int(rank.get("current"))
        if rank_val is not None and rank_val > 25:   # 99 == unranked
            rank_val = None
        records = c.get("records") or []
        record = ""
        for r in records:
            if r.get("type") in ("total", "overall") or not record:
                record = r.get("summary") or record
        return {
            "id": str(team.get("id") or ""),
            "name": team.get("shortDisplayName") or team.get("displayName") or "",
            "abbr": team.get("abbreviation") or "",
            "logo": team.get("logo") or "",
            "rank": rank_val,
            "score": as_int(c.get("score")),
            "record": record,
        }

    h, a = team_fields(home), team_fields(away)
    week = as_int((event.get("week") or {}).get("number")) or fallback_week
    spread, odds_detail = parse_spread(comp, h["abbr"], a["abbr"])

    return {
        "id": str(event.get("id")),
        "season": season,
        "week": week,
        "kickoff": event.get("date"),
        "status": norm_status,
        "neutral": bool(comp.get("neutralSite")),
        "conference_game": bool(comp.get("conferenceCompetition")),
        "home_id": h["id"], "home_name": h["name"], "home_abbr": h["abbr"],
        "home_logo": h["logo"], "home_rank": h["rank"], "home_score": h["score"],
        "home_record": h["record"],
        "away_id": a["id"], "away_name": a["name"], "away_abbr": a["abbr"],
        "away_logo": a["logo"], "away_rank": a["rank"], "away_score": a["score"],
        "away_record": a["record"],
        "winner_id": winner_id,
        "home_spread": spread,
        "odds_detail": odds_detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def upsert(rows):
    """PostgREST bulk upsert on the primary key.

    Every row in a batch must carry the same keys, which is why started games
    are sent separately -- see freeze_started_lines().
    """
    if not rows:
        return
    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/pickem_games",
        data=body,
        method="POST",
        headers={
            "apikey": SERVICE_KEY,
            "Authorization": f"Bearer {SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        print(f"!! Supabase rejected the upsert ({exc.code}): "
              f"{exc.read().decode('utf-8', 'replace')[:500]}")
        raise


def week_range():
    spec = os.environ.get("WEEKS", "1-16").strip()
    if "-" in spec:
        lo, hi = spec.split("-", 1)
        return range(int(lo), int(hi) + 1)
    return range(int(spec), int(spec) + 1)


def main():
    season = as_int(os.environ.get("SEASON")) or football_season()
    print(f"Syncing Big 12 games for the {season} season")

    all_rows, seen = [], set()
    for week in week_range():
        url = (f"{ESPN}?groups={BIG12_GROUP}&limit=200"
               f"&dates={season}&seasontype={REGULAR_SEASON}&week={week}")
        try:
            data = get_json(url)
        except Exception as exc:                      # noqa: BLE001
            print(f"  week {week:>2}: FAILED ({exc}) -- skipping")
            continue

        events = data.get("events") or []
        rows = []
        for event in events:
            row = parse_event(event, week, season)
            # ESPN sometimes echoes a game into an adjacent week; keep the first.
            if row and row["kickoff"] and row["id"] not in seen:
                seen.add(row["id"])
                rows.append(row)

        finals = sum(1 for r in rows if r["status"] == "final")
        print(f"  week {week:>2}: {len(rows):>2} games ({finals} final)")
        all_rows.extend(rows)

    if not all_rows:
        print("!! No games parsed. ESPN may have changed its response shape.")
        sys.exit(1)

    # Lines are frozen when the pick window opens: Sunday 00:00 Mountain. Before
    # that the market can move freely. After it, a game's number never changes --
    # except that a game with no line yet can still receive its first one, which
    # only ever turns "unknown" into a value rather than moving an existing one.
    now_utc = datetime.now(timezone.utc)
    first_kick = {}
    for r in all_rows:
        k = parse_ts(r["kickoff"])
        wk = r["week"]
        if wk not in first_kick or k < first_kick[wk]:
            first_kick[wk] = k
    opens = {wk: window_opens(k) for wk, k in first_kick.items()}
    already = existing_spreads(season)

    live, frozen = [], []
    for r in all_rows:
        open_at = opens.get(r["week"])
        may_write = (open_at is not None and now_utc < open_at) or r["id"] not in already
        if may_write:
            live.append(r)
        else:
            r = dict(r)
            r.pop("home_spread", None)
            r.pop("odds_detail", None)
            frozen.append(r)

    for batch in (live, frozen):
        for i in range(0, len(batch), 100):
            upsert(batch[i:i + 100])

    total_finals = sum(1 for r in all_rows if r["status"] == "final")
    with_line = len(already) + sum(
        1 for r in live if r.get("home_spread") is not None and r["id"] not in already)
    print(f"\nUpserted {len(all_rows)} games ({total_finals} final).")
    print(f"Odds: {with_line} of {len(all_rows)} games have a line; "
          f"{len(frozen)} frozen, {len(live)} still open to change.")
    for wk in sorted(opens):
        state = "open" if now_utc >= opens[wk] else "not yet open"
        print(f"  week {wk:>2}: picks {state}, "
              f"opened {opens[wk].astimezone(LOCAL_TZ):%a %b %d %H:%M} MT")
    if with_line == 0:
        print("!! No lines on any game. Every pick is worth 1 point until this "
              "resolves -- check ESPN's odds field.")


if __name__ == "__main__":
    main()
