#!/usr/bin/env python3
"""
Freeze the Big 12 War Room board every Monday morning.

The whole point of the app is the history, and a history that depends on
somebody remembering to press a button has holes in it. This runs at 6am
Mountain on Mondays and writes the same self-contained snapshot the app's
"Save this week" button writes: every prediction, plus every result as it
stands right now, so the week can be re-scored later exactly as it looked.

It takes at most one automatic snapshot per week. Running it twice, or running
it by hand, is a no-op.

Env:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   service_role key (bypasses RLS -- never ship to browser)
  SEASON                 optional, defaults to the current football season
  FORCE                  optional, "1" to snapshot even if this week already has one
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
FORCE = os.environ.get("FORCE", "") == "1"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}


def football_season(now=None):
    """Aug-Dec belongs to that year; Jan-Jul is the tail of the prior season."""
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 8 else now.year - 1


def get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={**HEADERS, "Prefer": "return=minimal"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        print(f"!! Supabase rejected the insert ({exc.code}): "
              f"{exc.read().decode('utf-8', 'replace')[:500]}")
        raise


def current_week(games):
    """The week we are living in: the earliest one with a game still to play."""
    pending = [g["week"] for g in games if g.get("status") != "final" and g.get("week")]
    if pending:
        return min(pending)
    weeks = [g["week"] for g in games if g.get("week")]
    return max(weeks) if weeks else None


def main():
    season = int(os.environ.get("SEASON") or football_season())

    games = get(f"pickem_games?select=id,week,conference_game,status,winner_id,"
                f"home_id,away_id,home_score,away_score,home_spread"
                f"&season=eq.{season}&limit=1000")
    if not games:
        print(f"No {season} games loaded yet -- nothing to snapshot. "
              f"Run the pick'em sync workflow first.")
        return

    settings = get(f"b12_settings?select=*&season=eq.{season}")
    if not settings:
        print(f"Nobody has opened the {season} board yet (no b12_settings row). Skipping.")
        return
    cfg = settings[0]

    week = current_week(games)
    if week is None:
        print("Could not work out the current week. Skipping.")
        return

    if not FORCE:
        existing = get(f"b12_snapshots?select=id,taken_at&season=eq.{season}"
                       f"&week=eq.{week}&source=eq.auto&limit=1")
        if existing:
            print(f"Week {week} already has an automatic snapshot "
                  f"(taken {existing[0]['taken_at']}). Nothing to do.")
            return

    preds = get(f"b12_predictions?select=game_id,pick_team_id,strength,note"
                f"&season=eq.{season}&limit=2000")

    finals = sum(1 for g in games if g.get("status") == "final")
    called = sum(1 for p in preds if p.get("strength") != "auto")

    payload = {
        "v": 1,
        "season": season,
        "likely_prob": float(cfg.get("likely_prob") or 0.75),
        "contenders": cfg.get("contenders") or [],
        "predictions": [
            {"game_id": p["game_id"], "pick_team_id": p.get("pick_team_id"),
             "strength": p.get("strength"), "note": p.get("note")}
            for p in preds
        ],
        "games": [
            {"id": g["id"], "week": g.get("week"),
             "conference_game": bool(g.get("conference_game")),
             "status": g.get("status"), "winner_id": g.get("winner_id"),
             "home_id": g.get("home_id"), "away_id": g.get("away_id"),
             "home_score": g.get("home_score"), "away_score": g.get("away_score"),
             "home_spread": (None if g.get("home_spread") is None
                             else float(g["home_spread"]))}
            for g in games
        ],
    }

    post("b12_snapshots", {
        "season": season,
        "week": week,
        "label": f"Week {week}",
        "note": None,
        "source": "auto",
        "taken_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    })

    print(f"Snapshot saved for the {season} season, week {week}.")
    print(f"  {len(games)} games ({finals} final), {called} of them with a call on the board.")
    print(f"  tracking {len(payload['contenders'])} contenders, "
          f"'likely' worth {payload['likely_prob']:.0%}")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"!! HTTP {exc.code} from Supabase: {exc.read().decode('utf-8', 'replace')[:400]}")
        sys.exit(1)
