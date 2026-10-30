"""Daily board -- the Garmin feed.

Reads today's numbers from Garmin Connect and sends a short summary to the
daily board. Any activity today (or yesterday, for a late workout) checks off
Sweat, unless it was unchecked by hand that day.

Garmin has no official API for individuals, so this uses the community
`garminconnect` library, signed in with saved tokens (see make_tokens.py).
Meant to run from a PRIVATE repo's GitHub Actions (see garmin-sync.yml), so
nothing it does shows up in a public log. It prints only counts, never data.

Environment:
  GARMIN_TOKENS  the long string make_tokens.py printed
  FEED_KEY       from the phone app's Settings
"""
import datetime as dt
import json
import os
import sys
import urllib.request

from garminconnect import Garmin

SUPABASE_URL = "https://yehpygarkxdopdvugifk.supabase.co"
SUPABASE_KEY = "sb_publishable_sGJHMMHbmIyLcORXh2pauw_CePLfJDo"  # public by design
TZ = dt.timezone(dt.timedelta(hours=-6))  # replaced below with America/Denver when available
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("America/Denver")
except Exception:
    pass


def safe(fn, *args):
    """One missing metric should never sink the rest."""
    try:
        return fn(*args)
    except Exception as e:  # noqa: BLE001
        print(f"  skipped {fn.__name__}: {type(e).__name__}")
        return None


def dig(d, *path):
    for p in path:
        if d is None:
            return None
        d = d[p] if isinstance(d, list) and isinstance(p, int) and len(d) > p else d.get(p) if isinstance(d, dict) else None
    return d


def main():
    api = Garmin()
    api.login(os.environ["GARMIN_TOKENS"])

    today = dt.datetime.now(TZ).date()
    monday = today - dt.timedelta(days=today.weekday())
    t = today.isoformat()

    stats = safe(api.get_stats, t) or {}
    sleep = safe(api.get_sleep_data, t) or {}
    hrv = safe(api.get_hrv_data, t) or {}
    ready = safe(api.get_training_readiness, t)
    acts = safe(api.get_activities_by_date, monday.isoformat(), t) or []

    # Intensity minutes this week, Monday on, the way Garmin counts them.
    intensity = 0
    d = monday
    while d <= today:
        s = stats if d == today else (safe(api.get_stats, d.isoformat()) or {})
        intensity += (s.get("moderateIntensityMinutes") or 0) + 2 * (s.get("vigorousIntensityMinutes") or 0)
        d += dt.timedelta(days=1)

    acts = sorted(acts, key=lambda a: a.get("startTimeLocal") or "", reverse=True)
    last = None
    if acts:
        a = acts[0]
        last = {
            "type": dig(a, "activityType", "typeKey"),
            "name": (a.get("activityName") or "")[:60],
            "start": (a.get("startTimeLocal") or "").replace(" ", "T"),
            "seconds": round(a.get("duration") or 0),
            "miles": round((a.get("distance") or 0) / 1609.344, 2) or None,
            "avg_hr": round(a["averageHR"]) if a.get("averageHR") else None,
        }
    yesterday = (today - dt.timedelta(days=1)).isoformat()
    active_days = sorted({(a.get("startTimeLocal") or "")[:10] for a in acts} & {t, yesterday})

    r = ready[0] if isinstance(ready, list) and ready else ready if isinstance(ready, dict) else {}
    payload = {
        "day": t,
        "battery": {"now": stats.get("bodyBatteryMostRecentValue"), "charged": stats.get("bodyBatteryChargedValue")},
        "sleep": {"seconds": dig(sleep, "dailySleepDTO", "sleepTimeSeconds"),
                  "score": dig(sleep, "dailySleepDTO", "sleepScores", "overall", "value")},
        "rhr": stats.get("restingHeartRate"),
        "hrv": {"status": dig(hrv, "hrvSummary", "status")},
        "readiness": {"score": r.get("score"), "level": r.get("level")} if r else {},
        "last": last,
        "week": {"intensity": intensity, "goal": stats.get("intensityMinutesGoal") or 150, "workouts": len(acts)},
        "active_days": active_days,
    }

    req = urllib.request.Request(
        SUPABASE_URL + "/rest/v1/rpc/daily_put",
        data=json.dumps({"k": os.environ["FEED_KEY"], "src": "garmin", "payload": payload}).encode(),
        headers={"apikey": SUPABASE_KEY, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as res:
        if res.status >= 300:
            sys.exit(f"daily_put HTTP {res.status}")
    print(f"ok: {len(acts)} activities this week, {len(active_days)} active day(s) sent")


if __name__ == "__main__":
    main()
