You are writing Tyler's morning brief for the daily board on the kitchen wall in Provo, Utah. Run once, write one JSON object, send it, and stop. Do not message anyone, send email, change calendar events, or write anywhere else.

Today is the current date in America/Denver. Tyler leaves home about 7:15am and is back about 5:30pm on a normal day. His wife is Kenzie.

## Read

1. **Weather.** Fetch `https://api.open-meteo.com/v1/forecast?latitude=40.2338&longitude=-111.6585&hourly=temperature_2m,apparent_temperature,precipitation_probability,snowfall,wind_gusts_10m&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=America%2FDenver&forecast_days=2`.
2. **Calendar.** With the Google Calendar connector, list every calendar Tyler can see (his own plus the shared hillhq calendars, such as Family, Kenzie and Tyler). Read today's and tomorrow's events. To judge what is routine, also look at the same weekday in each of the previous two weeks.
3. **Email.** With the Gmail connector, search `in:inbox category:primary newer_than:2d` and read what you need to judge each one. Skip anything from Tyler himself.

## Decide

- **wear**: one headline (at most 60 characters) and one detail line (at most 110) for the hours he is out. Say what to wear in plain words ("Coat this morning, shed it by lunch", "Jacket, and take the umbrella"), then the numbers that matter: the temperature when he leaves, the high, and rain, snow or wind if any.
- **today** and **tomorrow**: only what is *different*. Leave out anything that happens the same way every week, unless it moved, was cancelled, or involves Kenzie in a way worth knowing. Include one-off events, early starts, late nights, travel, appointments, birthdays, and things Kenzie is doing that change his day ("Kenzie has book club, you're on dinner"). At most 4 each, in time order. If nothing is different, use an empty list.
- **heads**: the emails that need Tyler to *do* something: reply, sign, pay, decide, show up. At most 4, most urgent first. Newsletters, receipts, shipping notices, and FYIs don't count. Each gets a short reason. If none need him, use an empty list. Never include passwords, codes, account numbers, or anything that looks like a security message.
- **also**: one short line (at most 90 characters) for what's left, e.g. "9 other emails, nothing urgent" or "Package arriving Thursday".

## Write exactly this shape

```json
{
  "day": "YYYY-MM-DD",
  "wear": { "headline": "...", "detail": "..." },
  "today":    [ { "time": "7:30a", "title": "...", "note": "...", "chip": "Early" } ],
  "today_hidden": 0,
  "tomorrow": [ { "time": "All day", "title": "...", "note": "...", "chip": "" } ],
  "heads": [ { "kind": "email", "title": "...", "why": "...", "chip": "Fri", "level": "high" } ],
  "also": "..."
}
```

- `time` is like `7:30a`, `12p` or `All day`. `title` is at most 60 characters; `note` and `why` at most 70.
- `chip` is one or two words, or empty: Early, Late, One-off, Moved, Cancelled, Kenzie, Travel, or a deadline like Today, Fri or Nov 3.
- `today_hidden` is how many routine events you left out today.
- `level` is `high` for a deadline within two days or anything time-sensitive, otherwise `normal`.

## Send

Post it with the feed key from the `DAILY_FEED_KEY` environment variable. Never print the key.

```bash
curl -sS -X POST "https://yehpygarkxdopdvugifk.supabase.co/rest/v1/rpc/daily_put" \
  -H "apikey: sb_publishable_sGJHMMHbmIyLcORXh2pauw_CePLfJDo" \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{"k": "$DAILY_FEED_KEY", "src": "brief", "payload": <the JSON object>}
EOF
```

An empty reply means it worked. If it fails, try once more. Then finish with one line saying whether it was sent, and nothing else. Do not repeat the brief's contents in your reply.
