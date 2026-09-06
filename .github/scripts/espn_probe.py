#!/usr/bin/env python3
"""
Report what ESPN's public college-football API actually gives us.

Two jobs:

  1. Explain missing betting lines. For a given week it lists every Big 12 game,
     whether a line exists, and what the odds block contains when it does.

  2. Survey what else is available per game -- box score, drives, plays, win
     probability, leaders -- so we know what an in-game app could show.

Read-only. Touches nothing in the database.

Env:
  SEASON  season year, defaults to the current one
  WEEK    week number to inspect, defaults to 2
  TEAM    team abbreviation to survey in depth, defaults to BYU
"""

import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

SITE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
CORE = ("https://sports.core.api.espn.com/v2/sports/football/leagues/"
        "college-football")
BIG12 = 4


def get(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "byu-pickem-probe/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as exc:                                # noqa: BLE001
            if attempt == tries:
                print(f"    ! {type(exc).__name__}: {exc}")
                return None
    return None


def season_now():
    n = datetime.now(timezone.utc)
    return n.year if n.month >= 8 else n.year - 1


def rule(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def shape(obj, depth=0, prefix=""):
    """Print the shape of a JSON blob without drowning in values."""
    pad = "  " * depth
    if isinstance(obj, dict):
        for k, v in list(obj.items())[:14]:
            if isinstance(v, (dict, list)):
                n = len(v)
                kind = "obj" if isinstance(v, dict) else f"list[{n}]"
                print(f"{pad}{prefix}{k}: {kind}")
                if depth < 1:
                    shape(v[0] if isinstance(v, list) and v else v, depth + 1)
            else:
                s = str(v)
                print(f"{pad}{prefix}{k} = {s[:64]}")
    elif isinstance(obj, list) and obj:
        shape(obj[0], depth)


# ---------------------------------------------------------------------------
# 1. Why does a game have no line?
# ---------------------------------------------------------------------------

def audit_lines(season, week):
    rule(f"BETTING LINES -- {season} week {week}")
    url = (f"{SITE}/scoreboard?groups={BIG12}&limit=200"
           f"&dates={season}&seasontype=2&week={week}")
    data = get(url)
    if not data:
        print("  could not load the scoreboard")
        return

    events = data.get("events") or []
    print(f"  {len(events)} games on the Big 12 board\n")
    missing = []

    for ev in events:
        comp = (ev.get("competitions") or [{}])[0]
        comps = comp.get("competitors") or []
        names = {}
        for c in comps:
            t = c.get("team") or {}
            names[c.get("homeAway")] = {
                "abbr": t.get("abbreviation"),
                "name": t.get("displayName"),
                # FBS teams sit in a conference group; FCS opponents usually
                # have no conferenceId or a very different one.
                "conf": t.get("conferenceId"),
                "id": t.get("id"),
            }
        odds = comp.get("odds") or []
        away, home = names.get("away", {}), names.get("home", {})
        label = f"{away.get('abbr','?')} at {home.get('abbr','?')}"

        if odds:
            o = odds[0]
            print(f"  [line]    {label:22} {o.get('details','?'):14} "
                  f"O/U {o.get('overUnder','-')}  via {(o.get('provider') or {}).get('name','?')}")
        else:
            print(f"  [NO LINE] {label:22} "
                  f"away conf={away.get('conf')}  home conf={home.get('conf')}")
            missing.append((ev.get("id"), label, away, home))

    if not missing:
        print("\n  Every game has a line.")
        return

    rule("GAMES WITH NO LINE -- digging in")
    for eid, label, away, home in missing:
        print(f"\n  {label}   event {eid}")
        # Does the dedicated odds endpoint know anything the scoreboard omits?
        core = get(f"{CORE}/events/{eid}/competitions/{eid}/odds")
        if core is None:
            print("    core odds endpoint: unreachable")
        else:
            items = core.get("items") or []
            print(f"    core odds endpoint: {core.get('count', len(items))} providers")
            for it in items[:3]:
                print(f"      {json.dumps(it)[:220]}")
        # Is the opponent FCS? That is the usual reason a book posts nothing.
        for side, t in (("away", away), ("home", home)):
            tid = t.get("id")
            if not tid:
                continue
            info = get(f"{SITE}/teams/{tid}")
            if info:
                team = (info.get("team") or {})
                grp = team.get("groups") or {}
                print(f"    {side:4} {team.get('displayName','?'):28} "
                      f"group={grp.get('id')} parent={(grp.get('parent') or {}).get('id')} "
                      f"conference={team.get('conferenceId')}")


# ---------------------------------------------------------------------------
# 2. What else could an in-game app show?
# ---------------------------------------------------------------------------

def survey_game(season, team_abbr):
    rule(f"WHAT A LIVE {team_abbr} APP COULD SHOW")
    # find the team's most recent completed game
    sched = None
    board = get(f"{SITE}/teams")
    tid = None
    if board:
        for sport in board.get("sports", []):
            for lg in sport.get("leagues", []):
                for t in lg.get("teams", []):
                    tt = t.get("team") or {}
                    if (tt.get("abbreviation") or "").upper() == team_abbr.upper():
                        tid = tt.get("id")
    if not tid:
        print(f"  could not find {team_abbr}; falling back to the Big 12 board")
    else:
        print(f"  {team_abbr} team id = {tid}")
        sched = get(f"{SITE}/teams/{tid}/schedule?season={season}")

    eid = None
    if sched:
        for ev in sched.get("events", []):
            st = (((ev.get("competitions") or [{}])[0].get("status") or {})
                  .get("type") or {})
            if st.get("completed"):
                eid = ev.get("id")
        print(f"  most recent completed game: event {eid}")
    if not eid:
        print("  no completed game found; cannot survey")
        return

    summary = get(f"{SITE}/summary?event={eid}")
    if not summary:
        print("  summary endpoint unreachable")
        return

    print("\n  Top-level sections returned by /summary:")
    for k, v in summary.items():
        n = len(v) if isinstance(v, (list, dict)) else "-"
        print(f"    {k:22} {type(v).__name__:6} {n}")

    for section in ("boxscore", "drives", "leaders", "winprobability",
                    "scoringPlays", "plays", "predictor", "againstTheSpread"):
        if section not in summary:
            continue
        rule(f"/summary -> {section}")
        shape(summary[section])

    # team + player statistics, the raw material for stat categories
    box = summary.get("boxscore") or {}
    for t in (box.get("teams") or [])[:1]:
        print("\n  team stat categories available:")
        for s in (t.get("statistics") or [])[:40]:
            print(f"    {s.get('name','?'):26} {s.get('displayValue','')}")
    for p in (box.get("players") or [])[:1]:
        print("\n  player stat groups available:")
        for grp in (p.get("statistics") or []):
            keys = grp.get("keys") or grp.get("labels") or []
            print(f"    {grp.get('name','?'):16} -> {', '.join(map(str, keys))[:90]}")


def main():
    season = int(os.environ.get("SEASON") or season_now())
    week = int(os.environ.get("WEEK") or 2)
    team = os.environ.get("TEAM") or "BYU"
    print(f"ESPN probe -- season {season}, week {week}, team {team}")
    audit_lines(season, week)
    survey_game(season, team)
    print("\nDone.")


if __name__ == "__main__":
    main()
