# Big 12 War Room — setup

About ten minutes, and most of the work is already done: this app rides on the same
Supabase project and the same schedule sync the [pick'em](../pickem/SETUP.md) app uses. It
adds three tables and one weekly job. Nothing here costs money.

| Piece | Where it runs | What it does |
|---|---|---|
| `big12/index.html` | GitHub Pages | The board the two of you use |
| Supabase | Free tier (the existing project) | Your predictions, your settings, the season's history |
| `Pick'em — sync games` | GitHub Actions | Already running. Feeds this app the schedule, scores and betting lines |
| `War Room — weekly snapshot` | GitHub Actions | Freezes the board every Monday at 6am Mountain |

---

## 1. Pick the shared password's address

There are no individual accounts. You both sign in with **one** email and password, and
that one address is the entire access rule.

Open **`big12/schema.sql`** and look at the top:

```sql
create or replace function b12_is_editor()
...
    'warroom@thill-ships.app'          -- <-- the shared account
```

It does **not** need to be a real mailbox — no confirmation email is ever sent — but it does
need to look like an email address. Use whatever you like, or leave it as it is. If you want
your own personal login to work too, add it to the array as a second entry.

Then open **`big12/index.html`**, find the `CFG` block, and make `account` match:

```js
const CFG = {
  url:     'https://yehpygarkxdopdvugifk.supabase.co',
  key:     'sb_publishable_...',
  account: 'warroom@thill-ships.app'   // <-- same address as schema.sql
};
```

The URL and key are the pick'em app's, already filled in. The publishable key is *meant* to
be public; Row Level Security is what actually protects the data.

## 2. Run the schema

Supabase → **SQL Editor → New query** → paste the whole of `big12/schema.sql` → **Run**.

Supabase will warn that the query contains destructive operations. That is a keyword match on
`drop policy`; the file drops policies only so it can recreate them, and never drops a table,
a column, or a row. **Re-run the whole file after pulling updates** — it is written to be safe
to run repeatedly, and that is how new columns and rules get applied.

## 3. Claim the password

Open `https://thill-ships.github.io/big12/`, type the password you want, and hit
**Open the board**. It will tell you no account exists yet and offer to set that password.
Do it once, tell your boss the password, and you are both in — that browser stays signed in
all season.

> Do this promptly after step 2. Until the password is claimed, anyone who found the URL
> could claim it. Afterwards the page is just a wrong-password box. If you would rather not
> race anyone, create the user yourself first in Supabase under
> **Authentication → Users → Add user** (email + password, "auto confirm" on), and skip the
> claim.

If you ever need to change it: **Authentication → Users**, find the account, and set a new
password from the row menu.

## 4. Turn on the weekly snapshot

Nothing to configure — `War Room — weekly snapshot` uses the same `SUPABASE_URL` and
`SUPABASE_SERVICE_KEY` secrets the pick'em jobs already use. Go to the **Actions** tab, find
it, and **Run workflow** once by hand to confirm it works. After that it runs itself every
Monday at 6am Mountain.

If the log says *"Nobody has opened the board yet"*, open the app once first — the first
visit writes the settings row.

## 5. Choose your contenders

Open the board and hit **Contenders**. Six rows is the sweet spot; eight is the cap. Everyone
else in the league still plays in the simulation — this only decides who gets a row.

---

## The Monday routine

1. Open the board. The weekend's results are already on it, in green and red, because the
   sync job pulled them overnight.
2. Read **This week** first: it lists the games with the most riding on them, biggest swing
   first, and tells you which side to root for.
3. Argue. Flip games on the **Board** as you change your minds — click cycles
   *the line stands → likely W → 50-50 → likely L → back*, and right-click adds a note.
4. Hit **Save this week** when you are done. That is the entry in the history.

Step 4 is optional insurance: a snapshot is taken automatically at 6am Monday whether or not
anybody opens the page, so a skipped week still gets recorded. Saving by hand just adds a
second, post-argument entry with your notes on it.

## How the numbers work

**Every undecided game has a win probability.** In order of preference:

1. **Your call.** "Likely" means the team wins 75% of the time; a 50-50 is a coin flip. That
   75% is adjustable — Standings → *change*.
2. **The betting line**, when you haven't made a call. A spread is converted through a normal
   curve with a 16-point standard deviation, which is about right for college football: a
   7-point favorite wins ~67% of the time, a 21-point favorite ~90%.
3. **A coin flip**, if there's no line either (rare, and mostly FCS games).

That second step is the reason an untouched board is already worth reading. You start the
season with the market's opinion of all 72 conference games and overrule it one game at a
time, which is a much better starting point than a blank spreadsheet.

**The odds come from replaying the season 20,000 times.** Each run plays every undecided
conference game at its probability, then ranks the league. "Reaches the title game" is how
often a team finishes in the top two, because the top two play for it. Ties are broken head
to head *inside that simulated season*, then at random — a simplification of the real
multi-team tiebreaker, but exactly right for the two-team case, which is most of them.

The run is seeded, so the same board always gives the same number. Odds that wiggle when you
switch tabs are odds nobody trusts.

**Swing** on the *This week* tab is the honest version of "does this game matter": the
difference between your team's title-game odds if the home team wins and if the away team
wins. A game where both answers are 34% doesn't matter, however good it looks on TV.

**Non-conference games never move it.** They can't change anybody's conference record, so
their swing is zero by construction. They're listed for completeness and for the polls.

## What is stored

| Table | What's in it |
|---|---|
| `b12_settings` | Your contenders and what "likely" is worth. One row per season. |
| `b12_predictions` | One row per game you have an opinion about, stored **per game** — so BYU–Utah can never be "BYU likely" on one row and "Utah likely" on the other. |
| `b12_snapshots` | One row per saved week. Self-contained: the predictions *and* the results as they stood, so a week can be re-scored later exactly as you saw it. |

The schedule itself is not duplicated — it's `pickem_games`, kept current by the job that was
already running.

## Things worth knowing

- **GitHub pauses scheduled workflows after 60 days without a commit.** If the repo goes
  quiet over the summer, re-enable them in the Actions tab before Week 1.
- **Snapshots are append-only.** There is no UPDATE policy on the table, so a saved week
  can't be quietly rewritten in November. You can delete an obvious mistake.
- **Both screens stay in sync.** Predictions and settings are on Supabase Realtime, so if you
  flip a game it moves on his screen too.

## If something breaks

| Symptom | Look at |
|---|---|
| "Could not load the schedule… relation does not exist" | `schema.sql` hasn't been run. |
| Sign-in says the password is wrong, and always did | The `account` in `CFG` doesn't match the address in `b12_is_editor()`. |
| Predictions won't save | Same mismatch — you're signed in as somebody the policy doesn't recognise. |
| The board is empty | The pick'em sync hasn't loaded this season yet. Actions → *Pick'em — sync games* → Run workflow. |
| Every untouched game says "PK" or shows no line | ESPN returned no odds. Check the sync log's odds coverage line. |
| No automatic snapshots | Actions → *War Room — weekly snapshot* → check the log; it prints why it skipped. |
