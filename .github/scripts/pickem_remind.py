#!/usr/bin/env python3
"""
Email everyone who still has picks outstanding for the upcoming week.

Runs daily from .github/workflows/pickem-remind.yml, but only actually sends
inside a window before the weekly lock, and never more than twice per person
per week (tracked in pickem_reminders).

Env:
  SUPABASE_URL           https://xxxx.supabase.co
  SUPABASE_SERVICE_KEY   service_role key
  GMAIL_USER             the Gmail address sending the mail
  GMAIL_APP_PASSWORD     a Google App Password (not your normal password)
  APP_URL                where the pick'em lives
  LEAGUE_NAME            optional, used in the subject line
"""

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from zoneinfo import ZoneInfo

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SERVICE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
GMAIL_USER = os.environ["GMAIL_USER"]
GMAIL_APP_PASSWORD = os.environ["GMAIL_APP_PASSWORD"]
APP_URL = os.environ.get("APP_URL", "https://thill-ships.github.io/pickem/")
LEAGUE_NAME = os.environ.get("LEAGUE_NAME", "Big 12 Pick'em")

LOCAL_TZ = ZoneInfo("America/Denver")
SEND_WINDOW_HOURS = 48      # start nagging this far out
MAX_PER_WEEK = 2            # never more than this many nudges per person


# --------------------------------------------------------------------------
# Supabase REST helpers (service_role -> bypasses RLS)
# --------------------------------------------------------------------------

def sb(path, params=None, method="GET", body=None):
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
    }
    if method == "POST":
        headers["Prefer"] = "return=minimal"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw.strip() else []
    except urllib.error.HTTPError as exc:
        print(f"!! Supabase {method} {path} failed ({exc.code}): "
              f"{exc.read().decode('utf-8', 'replace')[:400]}")
        raise


def parse_ts(value):
    """Postgres timestamptz -> aware datetime."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------
# Email
# --------------------------------------------------------------------------

def build_email(name, missing, total, deadline_local, game_lines):
    when = deadline_local.strftime("%A at %-I:%M %p").replace(" 0", " ")
    plural = "pick" if missing == 1 else "picks"

    text = (
        f"Hey {name},\n\n"
        f"You've still got {missing} {plural} to make before this week's slate "
        f"locks {when} Mountain.\n\n"
        f"You've made {total - missing} of {total}.\n\n"
        f"Make them here: {APP_URL}\n\n"
        f"This week's games:\n" + "\n".join(f"  - {g}" for g in game_lines) +
        "\n\nEverything locks at the first kickoff, so once it starts you're "
        "stuck with what you've got.\n"
    )

    rows = "".join(
        f'<tr><td style="padding:6px 0;border-bottom:1px solid #E4E6EA;'
        f'font-size:14px;color:#111315">{g}</td></tr>' for g in game_lines
    )
    html = f"""<!doctype html>
<html><body style="margin:0;background:#EFEFEF;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
  <div style="max-width:520px;margin:0 auto;padding:28px 20px">
    <div style="background:#fff;border-radius:20px;padding:26px;box-shadow:0 1px 3px rgba(16,24,40,.06)">
      <div style="font-size:12px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#6B7280">{LEAGUE_NAME}</div>
      <h1 style="margin:8px 0 4px;font-size:26px;letter-spacing:-.02em;color:#111315">
        {missing} {plural} to go, {name}
      </h1>
      <p style="margin:0 0 18px;color:#6B7280;font-size:15px;line-height:1.5">
        Everything locks <strong style="color:#111315">{when} Mountain</strong> &mdash;
        the first kickoff of the week. You're at {total - missing} of {total}.
      </p>
      <a href="{APP_URL}" style="display:inline-block;background:#002E5D;color:#fff;
         text-decoration:none;font-weight:700;font-size:15px;padding:13px 22px;border-radius:12px">
        Make my picks
      </a>
      <table style="width:100%;border-collapse:collapse;margin-top:22px">{rows}</table>
    </div>
    <p style="color:#9AA3AF;font-size:12px;text-align:center;margin-top:16px">
      Sent automatically. Turn these off on your profile in the app.
    </p>
  </div>
</body></html>"""
    return text, html


def send_all(messages):
    """One SMTP connection for the whole batch."""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        for msg in messages:
            server.send_message(msg)


# --------------------------------------------------------------------------

def main():
    now = datetime.now(timezone.utc)

    weeks = sb("pickem_weeks", {"select": "*", "order": "lock_at.asc"})
    upcoming = [w for w in weeks if w.get("lock_at") and parse_ts(w["lock_at"]) > now]
    if not upcoming:
        print("No upcoming week with a future lock time. Nothing to do.")
        return

    week = upcoming[0]
    season, week_no = week["season"], week["week"]
    lock_at = parse_ts(week["lock_at"])
    hours_out = (lock_at - now).total_seconds() / 3600

    print(f"Next lock: {season} week {week_no} at {lock_at.isoformat()} "
          f"({hours_out:.1f}h out)")
    if hours_out > SEND_WINDOW_HOURS:
        print(f"More than {SEND_WINDOW_HOURS}h away -- too early to nag.")
        return

    games = sb("pickem_games", {
        "select": "id,away_abbr,home_abbr,away_name,home_name,kickoff",
        "season": f"eq.{season}", "week": f"eq.{week_no}",
        "order": "kickoff.asc",
    })
    if not games:
        print("Week has no games. Nothing to do.")
        return

    game_ids = {g["id"] for g in games}
    game_lines = [
        f'{g["away_name"] or g["away_abbr"]} at {g["home_name"] or g["home_abbr"]}'
        for g in games
    ]

    players = sb("pickem_players", {"select": "user_id,display_name,email,notify",
                                    "notify": "is.true"})
    picks = sb("pickem_picks", {
        "select": "user_id,game_id",
        "game_id": "in.(" + ",".join(f'"{gid}"' for gid in sorted(game_ids)) + ")",
    })

    made = {}
    for p in picks:
        made.setdefault(p["user_id"], set()).add(p["game_id"])

    sent_rows = sb("pickem_reminders", {
        "select": "user_id", "season": f"eq.{season}", "week": f"eq.{week_no}",
    })
    sent_counts = {}
    for r in sent_rows:
        sent_counts[r["user_id"]] = sent_counts.get(r["user_id"], 0) + 1

    # Don't fire the two nudges back to back -- space them out.
    recent_cutoff = now - timedelta(hours=20)
    recent = sb("pickem_reminders", {
        "select": "user_id", "season": f"eq.{season}", "week": f"eq.{week_no}",
        "sent_at": f"gte.{recent_cutoff.isoformat()}",
    })
    recently_nudged = {r["user_id"] for r in recent}

    deadline_local = lock_at.astimezone(LOCAL_TZ)
    messages, logged = [], []

    for player in players:
        uid, email = player["user_id"], (player.get("email") or "").strip()
        name = player.get("display_name") or "there"
        if not email:
            continue
        missing = len(game_ids - made.get(uid, set()))
        if missing == 0:
            print(f"  {name}: all set")
            continue
        if sent_counts.get(uid, 0) >= MAX_PER_WEEK:
            print(f"  {name}: {missing} missing, but already nudged "
                  f"{MAX_PER_WEEK}x this week")
            continue
        if uid in recently_nudged:
            print(f"  {name}: {missing} missing, nudged in the last 20h")
            continue

        text, html = build_email(name, missing, len(game_ids),
                                 deadline_local, game_lines)
        msg = EmailMessage()
        msg["Subject"] = (f"{LEAGUE_NAME}: {missing} pick"
                          f"{'' if missing == 1 else 's'} left for Week {week_no}")
        msg["From"] = f"{LEAGUE_NAME} <{GMAIL_USER}>"
        msg["To"] = email
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
        messages.append(msg)
        logged.append({"user_id": uid, "season": season, "week": week_no,
                       "sent_at": now.isoformat()})
        print(f"  {name}: emailing ({missing} missing)")

    if not messages:
        print("Nobody to remind.")
        return

    send_all(messages)
    sb("pickem_reminders", method="POST", body=logged)
    print(f"\nSent {len(messages)} reminder(s).")


if __name__ == "__main__":
    main()
