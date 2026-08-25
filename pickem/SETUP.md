# Big 12 Pick'em — setup

One-time setup, about 20 minutes. Nothing here costs money.

Three pieces:

| Piece | Where it runs | What it does |
|---|---|---|
| `pickem/index.html` | GitHub Pages | The app everyone uses |
| Supabase | Free tier | Logins, picks, leaderboard |
| GitHub Actions | This repo | Adds each week's games, scores finals, emails reminders |

---

## 1. Create the Supabase project

1. Go to [supabase.com](https://supabase.com) → **New project**. Any name; pick the region
   closest to you. Save the database password somewhere — you won't need it for this, but
   you'll want it later.
2. Wait for it to finish provisioning (~2 min).
3. Go to **SQL Editor → New query**, paste in the entire contents of
   [`schema.sql`](./schema.sql), and hit **Run**. It creates the tables, the security
   rules, and the leaderboard view.

## 2. Point the app at it

In Supabase, go to **Project Settings → API** and copy two values:

- **Project URL** — looks like `https://abcdefgh.supabase.co`
- **Publishable key** (also labeled `anon`) — a long string

Open `pickem/index.html`, find the `CFG` block near the bottom, and paste them in:

```js
const CFG = {
  url: 'https://abcdefgh.supabase.co',
  key: 'sb_publishable_...'
};
```

The publishable key is *meant* to be public — it's in the page source of every Supabase
app. Row Level Security in `schema.sql` is what actually protects the data. The
**service_role** key is the dangerous one; that goes in GitHub Secrets and nowhere else.

## 3. Turn on magic-link sign-in

In Supabase → **Authentication**:

1. **Providers → Email**: make sure Email is enabled, and turn **Confirm email** ON.
2. **URL Configuration**:
   - Site URL: `https://thill-ships.github.io/pickem/`
   - Redirect URLs: add `https://thill-ships.github.io/pickem/`

   Sign-in links won't work without that second one.

> **Do this part or sign-in will break on day one.** Supabase's built-in email sender is
> rate limited to a handful of messages per hour — fine for you testing, useless when
> eight relatives all sign up during the same commercial break. Go to
> **Project Settings → Authentication → SMTP Settings**, turn on **Enable Custom SMTP**,
> and enter the same Gmail credentials you set up in step 4:
>
> | Field | Value |
> |---|---|
> | Host | `smtp.gmail.com` |
> | Port | `465` |
> | Username | your Gmail address |
> | Password | the app password from step 4 |
> | Sender email | your Gmail address |
> | Sender name | `Big 12 Pick'em` |

## 4. Create a Gmail app password

This lets the reminder job send mail as you. It is **not** your normal Google password.

1. Your Google account needs 2-Step Verification turned on.
2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
3. Create one named `Pick'em`. Google shows you a 16-character password **once** — copy it.

## 5. Add the GitHub secrets

In this repo: **Settings → Secrets and variables → Actions → New repository secret**.
Add four:

| Secret | Value |
|---|---|
| `SUPABASE_URL` | Your project URL from step 2 |
| `SUPABASE_SERVICE_KEY` | The **service_role** key (Settings → API). Not the publishable one. |
| `GMAIL_USER` | The Gmail address sending reminders |
| `GMAIL_APP_PASSWORD` | The 16-character password from step 4 |

## 6. Load the schedule

Go to the **Actions** tab → **Pick'em — sync games** → **Run workflow**.

It pulls every Big 12 game for the season from ESPN and writes them to Supabase. The log
shows a line per week. After that it runs itself every 2 hours — new weeks appear on their
own, and final scores flow in so the leaderboard scores itself.

## 7. Invite everyone

Send them `https://thill-ships.github.io/pickem/`. They enter their email, tap the link,
set a display name. That browser stays signed in all season.

---

## How the rules are enforced

Not by the honor system — by the database.

- **Picks lock at the week's first kickoff.** A Row Level Security policy rejects any
  insert or update after `min(kickoff)` for that week. Even someone poking at the API
  directly can't backdate a pick.
- **Nobody sees anyone else's picks until the lock.** The read policy returns only your
  own rows until the deadline passes.
- **Only the sync job writes games.** It uses the service_role key, which bypasses RLS.
  Nothing in the browser can touch scores.

## Reminders

`Pick'em — remind stragglers` runs daily at 9am Mountain, but only actually sends when:

- the lock is less than 48 hours away, **and**
- that person still has picks missing, **and**
- they haven't been nudged in the last 20 hours, **and**
- they've had fewer than 2 nudges this week.

Anyone can turn reminders off for themselves in the app's profile sheet.

## Things worth knowing

- **GitHub pauses scheduled workflows after 60 days without a commit.** If the repo goes
  quiet over the summer, re-enable them in the Actions tab before Week 1.
- **Cron times are UTC.** `0 15 * * *` is 9am Mountain during football season (MDT). It
  drifts to 8am after daylight saving ends in November.
- **Testing before the season?** Run the sync workflow with a past season year to load a
  finished season and confirm scoring works end to end.

## If something breaks

| Symptom | Look at |
|---|---|
| "No games yet" in the app | Actions → did the sync run? Check its log. |
| Sign-in link never arrives | Custom SMTP in step 3. Check spam. |
| Picks won't save | The week already locked, or `schema.sql` wasn't run. |
| Leaderboard is empty | Nothing is `final` yet — scores fill in as games end. |
| Reminders never send | Check the workflow log: it prints why it skipped each person. |
