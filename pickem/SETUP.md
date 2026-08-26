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

   Supabase will warn that the query contains destructive operations. That warning is a
   keyword match on `drop policy` and `alter table`; the file drops policies only so it can
   recreate them, and never drops a table, a column, or any data. **Re-run this whole file
   after pulling updates** — it is written to be safe to run repeatedly, and that is how new
   columns and rules get applied.

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

## 3. Configure sign-in (email + password)

In Supabase → **Authentication**:

1. **Providers → Email**: make sure Email is enabled, and turn **Confirm email OFF**.

   That last part is the point. With confirmation off, creating an account is instant and
   **no email is sent at all**, so sign-in cannot be broken by spam filters, rate limits, or
   a mail provider having a bad day. It's the right trade for a family league: the worst case
   is a stranger who guesses the URL making a useless account, and you can see and delete any
   account from the Supabase dashboard.

2. **URL Configuration → Site URL**: `https://thill-ships.github.io/pickem/`

3. Nothing else. No SMTP is needed for sign-in.

### Delete the old magic-link accounts

Accounts created during magic-link testing have no password, so they can't sign in any more.
Go to **Authentication → Users**, delete them, and sign up again from the app. Deleting a
user also removes their picks, which is what you want for throwaway test accounts.

### About password resets

With confirmation email off, there is no self-service password reset. For a family league
that's fine — you're the admin. If someone forgets their password, open
**Authentication → Users**, find them, and use the row menu to send a recovery link or set a
new password directly. If that ever becomes annoying, configuring custom SMTP (step 4's Gmail
credentials work) turns on self-service resets.

## 4. Create a Gmail app password

This is **only for the weekly reminder emails** — sign-in no longer needs email at all. The
reminder job talks to Gmail directly through Python, which is not affected by any of the
Supabase SMTP issues. It is **not** your normal Google password.

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

Send them `https://thill-ships.github.io/pickem/`. They tap **Create an account**, enter an email
and any password, and set a display name. No confirmation email, no waiting. That browser
stays signed in all season.

---

## Scoring

Every pick is worth at least 1 point. Correctly calling an underdog is worth more:

| The team you picked is | Points if they win |
|---|---|
| favored, or within 3 points | 1 |
| a +3 to +9.5 underdog | 2 |
| a +10 to +17.5 underdog | 3 |
| a +18 or bigger underdog | 4 |

A wrong pick is always 0, so swinging for an upset never costs you anything. Spreads come
from ESPN alongside the schedule. **A game's line stops updating once it kicks off**, so
everyone is scored on the same number, and a line moving during the week can't change what
your pick was worth after the fact. Games with no posted line — FCS opponents, or lines not
out yet — are worth 1 either way.

The sync job prints odds coverage on every run (`Odds: 14 of 16 upcoming games have a line`),
so it's obvious in the Actions log if ESPN stops supplying them.

## Locking in early

Once you've picked every game in a week you can lock in before the deadline. Your picks go
final immediately, and in exchange you can see the picks of **everyone else who has also
locked in** — and only them. Someone still deciding stays hidden, so nobody's tentative picks
leak while they could still change them.

If you never lock in, nothing happens to you: the weekly deadline locks everyone
automatically and all picks become public at that point.

## How the rules are enforced

Not by the honor system — by the database.

- **Picks lock at the week's first kickoff.** A Row Level Security policy rejects any
  insert or update after `min(kickoff)` for that week. Even someone poking at the API
  directly can't backdate a pick.
- **Nobody sees anyone else's picks until the lock.** The read policy returns only your
  own rows until the deadline passes.
- **Only the sync job writes games.** It uses the service_role key, which bypasses RLS.
  Nothing in the browser can touch scores, spreads, or point values.
- **Locking in is irreversible.** There is no update or delete policy on the locks table, so
  nobody can quietly un-lock after seeing what everyone else picked.
- **You can't lock in with blank picks.** The insert policy counts your picks against that
  week's games and refuses if any are missing.

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
| "Invalid login credentials" | No account yet — tap Create an account. Or a leftover magic-link account with no password; delete it in Authentication → Users. |
| Every pick is worth 1 point | ESPN returned no lines. Check the sync log's odds coverage line. |
| Picks won't save | The week already locked, or `schema.sql` wasn't run. |
| Leaderboard is empty | Nothing is `final` yet — scores fill in as games end. |
| Reminders never send | Check the workflow log: it prints why it skipped each person. |
