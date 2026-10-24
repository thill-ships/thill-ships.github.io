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

## 8. Make yourself the commissioner

One thing the app can't do for you, because it is the thing that decides who is allowed
to do anything: tell the database that you're in charge. Sign in to the app once first so
your account exists, then run this in the Supabase
[SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new), with
your own email in place of the one here:

```sql
insert into pickem_admins (user_id)
select id from auth.users where email = 'you@example.com'
on conflict do nothing;
```

Reload the app and a **Catch-up window** section appears at the bottom of your profile
sheet. Nobody else sees it, and there is deliberately no way to grant it from the browser —
promoting someone needs the SQL editor, which needs your Supabase login.

---

## Catch-up windows

Someone forgets a week. The deadline has passed, the games are being played, and they're
sitting out through no real fault of their own. Open your profile, pick their name, choose
15 minutes to 2 hours, and open a window. For as long as it runs, that one person can pick
**every game that week — including games already finished**.

That sounds like a cheat, and it would be, except for three things the database enforces:

- **Everyone sees the window is open.** A banner on the picks screen names the person and
  counts down. There is no quiet grant.
- **They can't see anyone else's picks while it's open.** Normally the week goes public at
  the deadline. For somebody still owing picks, it stays shut — otherwise the window would
  be worth more than the picks, because they'd be choosing with the answers in front of them.
- **Every pick made after a kickoff is stamped `Late`.** It shows on the card and it's
  counted on the leaderboard next to their name, for the rest of the season.

Two things a window deliberately does *not* do. It can't reach a week whose lines aren't
out yet, because picks against numbers nobody else has seen would be a real edge. And it
can't undo a lock-in: once you've locked yourself in you may have seen other people's
picks, so reopening yours would let you answer them.

Picks made during a window score normally. If you'd rather they didn't, say so and that's
a one-line change — but think about whether the `Late` stamp is already enough, given
everybody can see it.

To cut a window short, open your profile and hit **Close it**. Picks already made stand.

---

## Scoring

Every pick is worth at least 1 point. Correctly calling an underdog is worth more:

| The team you picked is | Points if they win |
|---|---|
| favored, or within 3 points | 1 |
| a +3 to +9.5 underdog | 2 |
| a +10 to +17.5 underdog | 3 |
| a +18 or bigger underdog | 4 |

A wrong pick is always 0, so swinging for an upset never costs you anything. Games with no
posted line — FCS opponents, or lines not out yet — are worth 1 either way.

## The pick window

**Picks open Sunday at 6:00am Mountain and close when the week's first game kicks off**,
which is normally Thursday evening. Same opening time every week.

**The lines freeze the moment the window opens.** Spreads come from ESPN alongside the
schedule and move freely up until Sunday 6am; after that a game's number never changes. That
is deliberate: if the line kept moving, the sharpest number would always be Thursday's, and
everyone would be pushed into picking at the last minute. Freezing at the open means whatever
a game pays when you first see it is what it pays all week.

One exception, and it only ever adds information: a game with **no** line at Sunday 6am can
still receive its first one later. That turns "unknown" into a value; it never moves a value
that already exists.

The sync job prints the state of every week on each run:

```
Odds: 14 of 16 games have a line; 9 frozen, 7 still open to change.
  week  3: picks open, opened Sun Aug 30 06:00 MT
  week  4: picks not yet open, opened Sun Sep 06 06:00 MT
```

so it's obvious in the Actions log if ESPN stops supplying odds.

## Locking in early

Once you've picked every game in a week you can lock in before the deadline. Your picks go
final immediately, and in exchange you can see the picks of **everyone else who has also
locked in** — and only them. Someone still deciding stays hidden, so nobody's tentative picks
leak while they could still change them.

If you never lock in, nothing happens to you: the weekly deadline locks everyone
automatically and all picks become public at that point.

## How the rules are enforced

Not by the honor system — by the database.

- **Picks only work inside the window.** A Row Level Security policy rejects any insert or
  update before Sunday 6am or after `min(kickoff)` for that week. Someone poking at the API
  directly can't pick early against an unset line, or backdate a pick afterwards. The one
  exception is a catch-up window, and it is the same policy that grants it — not a bypass.
- **Only a commissioner opens a catch-up window.** `pickem_admins` has no insert, update or
  delete policy at all, so nobody can promote themselves from the browser, and the grant
  policy checks `pickem_is_admin()` and caps any window at 24 hours.
- **The `Late` stamp is not the client's to set.** A trigger decides it, by comparing the
  write against that game's kickoff. Nothing the browser sends can clear it, and a routine
  update that doesn't change the pick leaves it alone, so on-time picks can't be
  retroactively branded.
- **Nobody sees anyone else's picks until the lock.** The read policy returns only your
  own rows until the deadline passes — and it keeps returning only your own, deadline or
  not, for as long as your own catch-up window is open.
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
