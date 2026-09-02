#!/usr/bin/env python3
"""
Fill in the season props that are about players, straight from BYU's box scores.

Every BYU game ESPN has finished carries a full per-player box score. This walks
the season's finals, adds each player up, and writes the answer into the prop
row it belongs to -- so nobody types "712" into a yards box ever again.

What it can answer, via a prop's `auto` key:

  needs auto_player          leader keys (work it out themselves)
  ---------------------      -----------------------------------
  pass_yds   pass_td         rec_leader        who leads receiving yards
  rush_yds   rush_td         rec_leader_yds    ...and how many
  long_rush  rec_yds         int_leader        who leads interceptions
  rec_td     long_rec        int_leader_ints   ...and how many
  ints       sacks
  tackles                    team totals
                             -----------
                             team_ints  team_sacks

A settled prop is never touched: settling is how you stop a number moving.

Env:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   service_role key (bypasses RLS -- never ship to browser)
  SEASON                 optional, defaults to the current football season
  DRY_RUN                optional, "1" to print what it found and write nothing
"""

import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

SUMMARY = ("https://site.api.espn.com/apis/site/v2/sports/football/"
           "college-football/summary")

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"

HEADERS = {
    "apikey": SERVICE_KEY,
    "Authorization": f"Bearer {SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Which box-score category each stat lives in, and the ESPN key to read from it.
# `agg` is how a season total is built from the per-game numbers.
STATS = {
    "pass_yds":  ("passing",       ["passingYards", "YDS"],           "sum"),
    "pass_td":   ("passing",       ["passingTouchdowns", "TD"],       "sum"),
    "rush_yds":  ("rushing",       ["rushingYards", "YDS"],           "sum"),
    "rush_td":   ("rushing",       ["rushingTouchdowns", "TD"],       "sum"),
    "long_rush": ("rushing",       ["longRushing", "LONG"],           "max"),
    "rec_yds":   ("receiving",     ["receivingYards", "YDS"],         "sum"),
    "rec_td":    ("receiving",     ["receivingTouchdowns", "TD"],     "sum"),
    "long_rec":  ("receiving",     ["longReception", "LONG"],         "max"),
    "ints":      ("interceptions", ["interceptions", "INT"],          "sum"),
    "sacks":     ("defensive",     ["sacks", "SACKS"],                "sum"),
    "tackles":   ("defensive",     ["totalTackles", "TOT"],           "sum"),
}
LEADERS = {
    "rec_leader":      ("rec_yds", "who"),
    "rec_leader_yds":  ("rec_yds", "how many"),
    "int_leader":      ("ints",    "who"),
    "int_leader_ints": ("ints",    "how many"),
}
TEAM_TOTALS = {"team_ints": "ints", "team_sacks": "sacks"}


def football_season(now=None):
    now = now or datetime.now(timezone.utc)
    return now.year if now.month >= 8 else now.year - 1


def get(path):
    req = urllib.request.Request(f"{SUPABASE_URL}/rest/v1/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def patch(path, body):
    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{path}",
        data=json.dumps(body).encode("utf-8"),
        method="PATCH",
        headers={**HEADERS, "Prefer": "return=minimal"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        resp.read()


def espn(url, tries=3):
    for attempt in range(1, tries + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "byu-war-room/1.0 (+github actions)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as exc:
            if attempt == tries:
                print(f"  !! gave up on {url}: {exc}")
                return None
            print(f"  retry {attempt}/{tries}: {exc.__class__.__name__}")
    return None


def norm(name):
    """Compare names the way a person would: case, punctuation and accents out."""
    if not name:
        return ""
    n = unicodedata.normalize("NFKD", name)
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", " ", n.lower())
    return re.sub(r"[^a-z ]", " ", n).split()


def same_person(a, b):
    """Exact, or same surname and same first initial -- 'LJ Martin' vs 'L.J. Martin'."""
    x, y = norm(a), norm(b)
    if not x or not y:
        return False
    if x == y:
        return True
    return x[-1] == y[-1] and x[0][:1] == y[0][:1]


def as_num(text):
    """ESPN sends stats as strings; some are '5/8' or '--'."""
    if text is None:
        return 0.0
    t = str(text).strip()
    if t in ("", "-", "--"):
        return 0.0
    m = re.match(r"^-?\d+(\.\d+)?", t)
    return float(m.group(0)) if m else 0.0


def read_box(summary, team_id):
    """One game -> {athlete name: {stat: value}} for the team we care about."""
    out = {}
    box = (summary or {}).get("boxscore") or {}
    for group in box.get("players") or []:
        if str(((group.get("team") or {}).get("id")) or "") != str(team_id):
            continue
        for cat in group.get("statistics") or []:
            cat_name = (cat.get("name") or "").lower()
            keys = [str(k) for k in (cat.get("keys") or [])]
            labels = [str(l).upper() for l in (cat.get("labels") or [])]
            for athlete in cat.get("athletes") or []:
                who = (athlete.get("athlete") or {}).get("displayName")
                if not who:
                    continue
                values = athlete.get("stats") or []
                line = out.setdefault(who, {})
                for stat, (want_cat, names, _agg) in STATS.items():
                    if want_cat != cat_name:
                        continue
                    idx = None
                    for n in names:
                        if n in keys:
                            idx = keys.index(n); break
                        if n.upper() in labels:
                            idx = labels.index(n.upper()); break
                    if idx is None or idx >= len(values):
                        continue
                    line[stat] = line.get(stat, []) + [as_num(values[idx])]
    return out


def combine(per_game):
    """Season line per player: sums, except the 'long' stats, which take a max."""
    season = {}
    for who, line in per_game.items():
        row = season.setdefault(who, {})
        for stat, values in line.items():
            agg = STATS[stat][2]
            if agg == "max":
                row[stat] = max(row.get(stat, 0), max(values) if values else 0)
            else:
                row[stat] = row.get(stat, 0) + sum(values)
    return season


def tidy(v):
    """Yards and touchdowns are whole; sacks come in halves."""
    return int(v) if float(v).is_integer() else round(float(v), 1)


def main():
    season = int(os.environ.get("SEASON") or football_season())
    print(f"BYU player stats for {season}" + ("  (dry run)" if DRY_RUN else ""))

    props = get(f"b12_props?select=*&season=eq.{season}&auto=not.is.null")
    wanted = [p for p in props
              if p["auto"] in STATS or p["auto"] in LEADERS or p["auto"] in TEAM_TOTALS]
    if not wanted:
        print("No props are asking for player stats. Nothing to do.")
        return

    games = get(f"pickem_games?select=id,week,status,home_id,home_abbr,away_id,away_abbr"
                f"&season=eq.{season}&limit=1000")
    byu = None
    for g in games:
        if (g.get("home_abbr") or "").upper() == "BYU":
            byu = g["home_id"]
        elif (g.get("away_abbr") or "").upper() == "BYU":
            byu = g["away_id"]
        if byu:
            break
    if not byu:
        print("!! No BYU game found in pickem_games. Run the pick'em sync first.")
        sys.exit(1)

    finals = [g for g in games
              if g.get("status") == "final" and byu in (g.get("home_id"), g.get("away_id"))]
    finals.sort(key=lambda g: g.get("week") or 0)
    print(f"BYU is team {byu}; {len(finals)} finished games to read.")
    if not finals:
        print("Nothing has been played yet.")
        return

    per_game = {}
    for g in finals:
        data = espn(f"{SUMMARY}?event={g['id']}")
        box = read_box(data, byu)
        if not box:
            print(f"  week {g['week']:>2}: no box score yet")
            continue
        print(f"  week {g['week']:>2}: {len(box)} players")
        for who, line in box.items():
            dest = per_game.setdefault(who, {})
            for stat, values in line.items():
                dest[stat] = dest.get(stat, []) + values

    season_line = combine(per_game)
    if not season_line:
        print("!! No box scores came back. ESPN may have changed shape; nothing written.")
        sys.exit(1)

    def leader(stat):
        best = [(who, row.get(stat, 0)) for who, row in season_line.items() if row.get(stat)]
        best.sort(key=lambda x: -x[1])
        return best[0] if best else (None, 0)

    for stat in ("rush_yds", "rec_yds", "pass_td", "ints", "sacks"):
        who, v = leader(stat)
        if who:
            print(f"  leader {stat:>9}: {who} ({tidy(v)})")

    updates, notes = [], []
    for p in wanted:
        key, target = p["auto"], p.get("auto_player")
        if p.get("settled"):
            notes.append(f"  skipped (settled): {p['question']}")
            continue

        value, choice = None, None
        if key in TEAM_TOTALS:
            stat = TEAM_TOTALS[key]
            value = sum(row.get(stat, 0) for row in season_line.values())
        elif key in LEADERS:
            stat, part = LEADERS[key]
            who, v = leader(stat)
            if who is None:
                notes.append(f"  nobody has a {stat} yet: {p['question']}")
                continue
            if part == "who":
                options = p.get("options") or []
                match = next((o for o in options if same_person(o, who)), None)
                if match is None and options:
                    notes.append(f"  !! {who} leads {stat} and is NOT one of the options on "
                                 f"\"{p['question']}\" -- nobody can win it as written")
                choice = match or who
            else:
                value = v
        else:
            if not target:
                notes.append(f"  no player set on: {p['question']}")
                continue
            who = next((w for w in season_line if same_person(w, target)), None)
            if who is None:
                notes.append(f"  !! no player matching \"{target}\" has appeared in a box "
                             f"score yet: {p['question']}")
                continue
            value = season_line[who].get(key, 0)

        body = {}
        if choice is not None:
            if choice != p.get("actual_choice"):
                body["actual_choice"] = choice
        elif value is not None:
            v = tidy(value)
            if p.get("actual") is None or float(p["actual"]) != float(v):
                body["actual"] = v
        if body:
            updates.append((p, body))

    print()
    for p, body in updates:
        was = p.get("actual_choice") if "actual_choice" in body else p.get("actual")
        now = body.get("actual_choice", body.get("actual"))
        print(f"  {p['question'][:52]:<54} {str(was):>10} -> {now}")
        if not DRY_RUN:
            patch(f"b12_props?id=eq.{p['id']}", body)
    if not updates:
        print("  every automatic prop is already up to date.")
    for n in notes:
        print(n)
    print(f"\n{len(updates)} prop(s) {'would be' if DRY_RUN else ''} updated.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"!! HTTP {exc.code} from Supabase: {exc.read().decode('utf-8', 'replace')[:400]}")
        sys.exit(1)
