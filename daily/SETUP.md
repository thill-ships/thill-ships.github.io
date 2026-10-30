# Daily board — setup

The board for the kitchen calendar. Five panels:

| Panel | Comes from | How often | Needs setup? |
|---|---|---|---|
| What to wear | Open-Meteo for Provo, with the morning brief's wording on top | Every 30 min | No: the numbers work as soon as the board opens |
| $CROSS | The habit tracker (`cross/`) | Live | Steps 1 and 2 |
| Today, only what's different | The Claude morning brief, from your calendars | Once a day | Step 3 |
| Heads-up | The Claude morning brief, from your inbox | Once a day | Step 3 |
| Body | Garmin | Every 30 min | Step 4 |

From 7pm the board looks ahead: tomorrow's weather and tomorrow's calendar.

The brief is written once a day by a Claude scheduled task that reads your calendar and Gmail
through the connectors you've already approved in Claude. The weather keeps working without it:
if a morning run fails, "What to wear" falls back to the board's own rules, and the brief panels
say when they last heard from it. Nothing private is stored in this repo or on the public site;
the summaries go to the database, and only the wall's link can read them.

## 1. The habit tracker

Follow `cross/SETUP.md` (schema, login, phone). If you ran `cross/schema.sql` before, **run it
again**: it has gained columns for the feeds.

## 2. The board's schema

[SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new) → paste all
of `daily/schema.sql` → **Run**. Then open the phone app → **Settings**:

- **Kitchen wall link**: open it on the calendar. The board remembers its key, so plain `/daily/`
  works after that.
- **Feed key**: you'll paste this into steps 3 and 4. It can only *send* summaries; it cannot
  read anything.

## 3. The morning brief (Claude, about 5 minutes)

A Claude scheduled task runs at about 4:37am Mountain. It reads the forecast, today's and
tomorrow's events on every calendar your personal Google account can see (including the hillhq
calendars shared to it), and the last two days of Primary mail. It decides what's different and
what needs you, and sends one short summary to the board. Its instructions are in
`daily/brief/PROMPT.md`; change them there and update the task to match.

It runs in a Claude cloud environment, which needs two settings (the environment menu in the
session's title bar → **Edit**):

1. **Network access → Allowed domains:** add `yehpygarkxdopdvugifk.supabase.co` and
   `api.open-meteo.com`.
2. **Environment variables:** `DAILY_FEED_KEY` = the feed key from the phone app.

Then ask Claude to create the task. It's a routine that starts a fresh session each morning with
the Gmail and Google Calendar connectors. You'll see each run in your routines list.

**The life tracker:** once its Sheet exists, the same task can read the `status` tab through the
Google Drive connector and put due and overdue upkeep into Heads-up. That's one line in the
prompt plus the Drive connector on the task.

## 4. Garmin (about 10 minutes)

Garmin has no official way for one person to read their own data. This uses `garminconnect`, the
widely used community library. It can break when Garmin changes things; if it does, the Body panel
shows when it last synced instead of old numbers.

Because this repo is public, **and so are its Action logs**, the sync runs from a separate
private repo:

1. Create a private repo on GitHub, e.g. `thill-ships/garmin-sync`.
2. Put `daily/garmin/sync.py` and `daily/garmin/requirements.txt` at its root, and
   `daily/garmin/garmin-sync.yml` at `.github/workflows/garmin-sync.yml`.
3. On your own computer: `pip install garminconnect`, then `python make_tokens.py`. Sign in, and
   it prints one long string. Your password isn't saved anywhere; the tokens last about a year.
4. In the private repo: **Settings → Secrets and variables → Actions** → add `GARMIN_TOKENS`
   (that string) and `FEED_KEY` (from the phone).
5. **Actions → Garmin sync → Run workflow** to try it. After that it runs every 30 minutes from
   5am to 11pm.

**Sweat:** any activity Garmin logs today (or yesterday, for a late one) checks Sweat off. You can
still check it yourself on the phone or the wall. If you uncheck it by hand, Garmin leaves it
unchecked for that day.

## Settings on the board itself

At the top of the script in `daily/index.html`:
- `place`: the weather location (Provo).
- `leave` / `home`: a normal day's hours out (7:15 to 5:30). "What to wear" is read for those hours.
- `QUOTES`: one a day, in order. Add, remove or reorder freely.
