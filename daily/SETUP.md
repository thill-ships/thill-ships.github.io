# Daily board — setup

The board for the kitchen calendar. Five panels:

| Panel | Comes from | Needs setup? |
|---|---|---|
| What to wear | Open-Meteo forecast for Provo | No: works as soon as the board opens |
| $CROSS | The habit tracker (`cross/`) | Steps 1 and 2 |
| Today, only what's different | Your Google calendars | Step 3 |
| Heads-up | Your Gmail inbox + the life tracker Sheet | Step 3 (the Sheet part once it exists) |
| Body | Garmin | Step 4 |

Each panel says "not connected yet" until its feed has reported in, and turns its corner text
amber if a feed stops syncing. Nothing private is ever stored in this repo or on the public site.
The feeds send short summaries to the database, and only the wall's link can read them.

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

## 3. Calendar, inbox and upkeep (Google, about 5 minutes)

Do this signed in to your **personal** Google account. The hillhq calendars come along because
they're shared to it.

1. Go to [script.google.com](https://script.google.com) → **New project**. Name it "Daily board".
2. Replace everything in `Code.gs` with `daily/google/Code.gs`.
3. **Project Settings** (gear) → tick **Show "appsscript.json" manifest file** → back in the
   editor, replace `appsscript.json` with `daily/google/appsscript.json`. This limits the script
   to read-only access to your calendar, mail and Sheets.
4. **Project Settings** → **Script properties** → add `FEED_KEY` = the feed key from the phone.
5. Back in the editor, pick `setup` in the function menu and press **Run**. Google asks you to
   allow access. Because it's your own unpublished script, it shows "Google hasn't verified this
   app": click **Advanced → Go to Daily board**. After that it runs every 10 minutes by itself.

Within a minute the calendar and inbox panels fill in on the wall.

**Tuning it** (top of `Code.gs`):
- `SKIP_CALENDARS`: calendars to leave off entirely.
- `ALWAYS_SHOW`: recurring events are treated as routine and hidden, except titles matching this.
  It starts with Kenzie, date night, anniversaries and birthdays.

**When the life tracker Sheet exists:** add a second script property, `TRACKER_SHEET_ID` (the long
id in the Sheet's URL). The script reads its `status` and `items` tabs exactly as the brief lays
them out, and the upkeep items join the Heads-up list.

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
