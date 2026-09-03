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
  PROBE_SEASON           optional, e.g. "2025". Reads that season's real box
                         scores straight from ESPN instead of this season's
                         schedule, prints everything it worked out, and writes
                         NOTHING. The way to find out whether this all works
                         before BYU has played a game.
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
SCHEDULE = ("https://site.api.espn.com/apis/site/v2/sports/football/"
            "college-football/teams/{team}/schedule")
BYU_FALLBACK = "252"

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
DRY_RUN = os.environ.get("DRY_RUN", "") == "1"
PROBE = (os.environ.get("PROBE_SEASON") or "").strip()

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
    # The pieces of a defensive/special-teams touchdown. Kept separate because
    # a pick six lands in BOTH "defensive" and "interceptions" and must not be
    # counted twice -- see derive_def_st_td().
    "def_td":    ("defensive",     ["defensiveTouchdowns", "TD"],     "sum"),
    "int_td":    ("interceptions", ["interceptionTouchdowns", "TD"],  "sum"),
    "kr_td":     ("kickReturns",   ["kickReturnTouchdowns", "TD"],    "sum"),
    "pr_td":     ("puntReturns",   ["puntReturnTouchdowns", "TD"],    "sum"),
    # Not read from any category; built per game from the four above.
    "def_st_td": ("__derived__",   [],                                "sum"),
}
LEADERS = {
    "rec_leader":      ("rec_yds", "who"),
    "rec_leader_yds":  ("rec_yds", "how many"),
    "int_leader":      ("ints",    "who"),
    "int_leader_ints": ("ints",    "how many"),
}
TEAM_TOTALS = {"team_ints": "ints", "team_sacks": "sacks",
               "team_def_st_td": "def_st_td"}


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


def espn_schedule(team_id, year):
    """A past season's finished games, straight from ESPN. Used only by probe
    mode -- normally the schedule comes out of the database like everything
    else."""
    data = espn(f"{SCHEDULE.format(team=team_id)}?season={year}&seasontype=2")
    out = []
    for e in (data or {}).get("events") or []:
        done = False
        for c in e.get("competitions") or []:
            status = (c.get("status") or {}).get("type") or {}
            done = done or bool(status.get("completed"))
        if done and e.get("id"):
            out.append({"id": str(e["id"]),
                        "week": ((e.get("week") or {}).get("number")) or 0})
    out.sort(key=lambda g: g["week"])
    return out


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
                    # cat_name is lowercased; the table spells them as ESPN
                    # does ("kickReturns"), so fold both sides.
                    if want_cat.lower() != cat_name:
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


def derive_def_st_td(box):
    """Defence + special teams touchdowns, for one game, without double counting.

    A pick six is reported in the `defensive` category as a defensive touchdown
    AND in the `interceptions` category as an interception touchdown -- the same
    play, twice. ESPN is not always consistent about filling both, so take the
    larger of the two rather than the sum: it survives either one being blank,
    and never counts a play twice. Return touchdowns live in their own
    categories and cannot overlap with those, so they simply add.

    Kicking is deliberately absent: no extra points, no field goals.
    """
    for line in box.values():
        defensive = sum(line.get("def_td", []))
        picks = sum(line.get("int_td", []))
        returns = sum(line.get("kr_td", [])) + sum(line.get("pr_td", []))
        total = max(defensive, picks) + returns
        if total:
            line["def_st_td"] = [total]
    return box


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
    probe = int(PROBE) if PROBE else None
    dry = DRY_RUN or probe is not None
    if probe:
        print(f"PROBE against the real {probe} season. Nothing will be written.\n"
              f"Props are read from {season}, so you can see how this year's "
              f"questions would resolve against a season that has actually happened.")
    else:
        print(f"BYU player stats for {season}" + ("  (dry run)" if dry else ""))

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
        if not probe:
            print("!! No BYU game found in pickem_games. Run the pick'em sync first.")
            sys.exit(1)
        byu = BYU_FALLBACK
        print(f"No {season} schedule in the database; using BYU = {byu}.")

    if probe:
        finals = espn_schedule(byu, probe)
        print(f"\nBYU is team {byu}; {len(finals)} finished games in {probe}.")
    else:
        finals = [g for g in games
                  if g.get("status") == "final" and byu in (g.get("home_id"), g.get("away_id"))]
        finals.sort(key=lambda g: g.get("week") or 0)
        print(f"BYU is team {byu}; {len(finals)} finished games to read.")
    if not finals:
        print("Nothing has been played yet.")
        if not probe:
            print("\nTo find out whether this works before the season starts, run this "
                  "workflow again with Probe season set to 2025. It reads a season that "
                  "really happened and writes nothing.")
        return

    per_game = {}
    for g in finals:
        data = espn(f"{SUMMARY}?event={g['id']}")
        box = derive_def_st_td(read_box(data, byu))
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
    for key, stat in sorted(TEAM_TOTALS.items()):
        total = sum(row.get(stat, 0) for row in season_line.values())
        print(f"  team {key[5:]:>12}: {tidy(total)}")

    if probe:
        # The whole point of a probe is seeing the raw season line, so print it.
        print(f"\n  Every BYU player with a counting stat in {probe}:")
        print(f"  {'player':<26} {'rush':>6} {'long':>5} {'rec':>6} {'pTD':>4} "
              f"{'rTD':>4} {'INT':>4} {'sack':>5}")
        rows = sorted(season_line.items(),
                      key=lambda kv: -(kv[1].get("rush_yds", 0) + kv[1].get("rec_yds", 0)
                                       + kv[1].get("pass_td", 0) * 40))
        for who, row in rows[:22]:
            print(f"  {who[:26]:<26} {tidy(row.get('rush_yds', 0)):>6} "
                  f"{tidy(row.get('long_rush', 0)):>5} {tidy(row.get('rec_yds', 0)):>6} "
                  f"{tidy(row.get('pass_td', 0)):>4} {tidy(row.get('rush_td', 0)):>4} "
                  f"{tidy(row.get('ints', 0)):>4} {tidy(row.get('sacks', 0)):>5}")

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
        if not dry:
            patch(f"b12_props?id=eq.{p['id']}", body)
    if not updates:
        print("  every automatic prop is already up to date.")
    for n in notes:
        print(n)
    print(f"\n{len(updates)} prop(s) {'would be' if dry else ''} updated.")
    if probe:
        print("Nothing was written -- this was a probe. If those numbers look like a real "
              f"BYU {probe} season, the job works.")
        if any("!!" in n for n in notes):
            print("A name that does not match is not necessarily a bug here: the questions "
                  f"name {season} players, and this ran against {probe}, when some of them "
                  "were somewhere else. Judge the machinery, not the roster.")


if __name__ == "__main__":
    try:
        main()
    except urllib.error.HTTPError as exc:
        print(f"!! HTTP {exc.code} from Supabase: {exc.read().decode('utf-8', 'replace')[:400]}")
        sys.exit(1)
