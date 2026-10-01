#!/usr/bin/env python3
"""
Fill in the favourite for anyone who forgot to pick.

Runs after a week's deadline. For every player who is actually in the league
and left games blank, it records the favourite as their pick and marks it as
assigned rather than chosen.

The favourite comes from the spread that was frozen when picks opened, so the
result is fixed before anyone kicks off and cannot be influenced by what has
happened since. A favourite is worth one point under the scoring rules, which
is the least a pick can be worth -- forgetting still costs you the chance at
an underdog.

Deliberately does nothing in three cases:
  * a game with no betting line, because there is no favourite to assign
  * a game already final, which would mean assigning a settled result
  * a player who has never made a pick, who is not really in the league

Env:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   service_role key
  SEASON                 optional, defaults to the current season
  DRY_RUN                set to 1 to report without writing
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DRY_RUN = os.environ.get("DRY_RUN") == "1"

# How far back to look. A deadline older than this is somebody else's problem.
LOOKBACK_HOURS = 36


def sb(path, params=None, method="GET", body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"apikey": SERVICE_KEY, "Authorization": f"Bearer {SERVICE_KEY}",
               "Content-Type": "application/json"}
    if method == "POST":
        headers["Prefer"] = "return=minimal,resolution=ignore-duplicates"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as exc:
        print(f"!! {method} {path} failed ({exc.code}): "
              f"{exc.read().decode('utf-8','replace')[:300]}")
        raise


def parse_ts(v):
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    d = datetime.fromisoformat(v)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def season_now():
    n = datetime.now(timezone.utc)
    return n.year if n.month >= 8 else n.year - 1


def favourite(game):
    """Team id of the favourite, or None when there is no line to read."""
    spread = game.get("home_spread")
    if spread is None:
        return None
    spread = float(spread)
    if spread == 0:
        return None                      # a true pick'em has no favourite
    return game["home_id"] if spread < 0 else game["away_id"]


def main():
    season = int(os.environ.get("SEASON") or season_now())
    now = datetime.now(timezone.utc)
    print(f"Auto-pick check for {season}" + ("  (DRY RUN)" if DRY_RUN else ""))

    weeks = sb("pickem_weeks", {"select": "*", "order": "lock_at.desc"})
    due = [w for w in weeks
           if w.get("season") == season and w.get("lock_at")
           and timedelta(0) <= now - parse_ts(w["lock_at"]) <= timedelta(hours=LOOKBACK_HOURS)]
    if not due:
        print("No week has locked in the last "
              f"{LOOKBACK_HOURS} hours. Nothing to do.")
        return

    # Only people who actually play. A row in pickem_players can mean nothing
    # more than having opened the app once.
    ever = sb("pickem_picks", {"select": "user_id"})
    participants = sorted({r["user_id"] for r in ever})
    if not participants:
        print("Nobody has ever made a pick. Nothing to do.")
        return
    names = {p["user_id"]: p.get("display_name") or p["user_id"]
             for p in sb("pickem_players", {"select": "user_id,display_name"})}

    for wk in due:
        week = wk["week"]
        locked_ago = now - parse_ts(wk["lock_at"])
        print(f"\nWeek {week} -- locked {locked_ago.total_seconds()/3600:.1f}h ago")

        games = sb("pickem_games", {
            "select": "id,home_id,away_id,home_abbr,away_abbr,home_spread,status,kickoff",
            "season": f"eq.{season}", "week": f"eq.{week}", "order": "kickoff.asc"})
        if not games:
            print("  no games"); continue

        ids = [g["id"] for g in games]
        existing = sb("pickem_picks", {
            "select": "user_id,game_id",
            "game_id": "in.(" + ",".join(f'"{i}"' for i in ids) + ")"})
        have = {}
        for r in existing:
            have.setdefault(r["user_id"], set()).add(r["game_id"])

        playable, skipped_line, skipped_final = [], 0, 0
        for g in games:
            if g.get("status") == "final":
                skipped_final += 1; continue
            fav = favourite(g)
            if fav is None:
                skipped_line += 1
                print(f"  no line on {g['away_abbr']} at {g['home_abbr']} "
                      f"-- leaving it blank")
                continue
            playable.append((g, fav))

        if skipped_final:
            print(f"  {skipped_final} game(s) already final -- not assigning those")

        rows = []
        for uid in participants:
            mine = have.get(uid, set())
            missing = [(g, fav) for g, fav in playable if g["id"] not in mine]
            if not missing:
                continue
            who = names.get(uid, uid)
            picks = ", ".join(
                (g["home_abbr"] if fav == g["home_id"] else g["away_abbr"])
                for g, fav in missing)
            print(f"  {who}: assigning {len(missing)} favourite(s) -- {picks}")
            for g, fav in missing:
                rows.append({"user_id": uid, "game_id": g["id"], "team_id": fav,
                             "auto": True,
                             "updated_at": now.isoformat()})

        if not rows:
            print("  everyone is covered"); continue
        if DRY_RUN:
            print(f"  DRY RUN: would write {len(rows)} pick(s)"); continue
        for i in range(0, len(rows), 100):
            sb("pickem_picks", method="POST", body=rows[i:i + 100])
        print(f"  wrote {len(rows)} assigned pick(s)")

    print("\nDone.")


if __name__ == "__main__":
    main()
