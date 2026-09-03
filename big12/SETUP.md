# Big 12 War Room — setup

About twenty minutes, most of it waiting. Everything rides on the same Supabase project and
the same schedule sync the [pick'em](../pickem/SETUP.md) app already uses, so there are no new
accounts to open, no keys to paste, and nothing here costs money.

**Follow the numbered steps in order.** Steps 1 to 4 are the whole setup.

| Piece | Where it runs | What it does |
|---|---|---|
| `big12/index.html` | GitHub Pages | The board the two of you use |
| `props/index.html` | GitHub Pages | Season props — the one piece with real accounts |
| Supabase | Free tier (the existing project) | Your predictions, your settings, the season's history |
| `Pick'em — sync games` | GitHub Actions | Already running. Feeds this app the schedule, scores and betting lines |
| `War Room — weekly snapshot` | GitHub Actions | Freezes the board every Monday at 6am Mountain |
| `War Room — BYU player stats` | GitHub Actions | Reads BYU's box scores and answers the player props |

---

## Before you start

Everything below happens in three places. These links go straight to yours:

- **Supabase** — [SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new)
  · [Auth providers](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/providers)
  · [Users](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/users)
- **GitHub Actions** — [the repo's Actions tab](https://github.com/thill-ships/thill-ships.github.io/actions)
- **The apps** — `https://thill-ships.github.io/big12/` and `https://thill-ships.github.io/props/`

**There is nothing to edit in any file.** The Supabase keys and the shared account address are
already filled in and already match each other. Skip to step 1.

---

## 1. Run the schema

1. Open the [SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new).
2. Open `big12/schema.sql` from this repo, select all of it, copy it.
3. Paste it into the query box and press **Run** (bottom right, or Ctrl/Cmd+Enter).

Supabase will warn that the query contains destructive operations. That warning is a keyword
match on `drop policy`; the file drops policies only so it can recreate them, and never drops a
table, a column, or a row. Say yes.

You should see **Success. No rows returned**. If you see an error instead, copy it and stop
here — everything else depends on this step.

> **Re-run this whole file after pulling updates.** It is written to be safe to run repeatedly,
> and that is how new columns and rules get applied. It has changed several times already.

## 2. Check that sign-up doesn't need email confirmation

This one matters more than it looks: a dozen people are about to create accounts on the props
app, and if Supabase is waiting on confirmation emails, every one of them gets stuck.

1. Open [Auth → Providers](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/providers).
2. Click **Email**.
3. **Confirm email** must be **off**. If it is on, turn it off and **Save**.

With it off, creating an account is instant and no email is ever sent. (You very likely did
this already when you set up the pick'em — check anyway.)

## 3. Create the War Room login

The board has one shared password. Both of you use it; there are no separate accounts. The
address it signs in with is **`warroom@thill-ships.app`** — already set in the code, in both
places it needs to be. **It does not need to be a real mailbox.** No mail is ever sent to it.
It exists only because Supabase wants sign-ins to look like an email address.

Do it in the dashboard — it takes 30 seconds and avoids any chance of a stranger claiming the
password first:

1. Open [Auth → Users](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/users).
2. Click **Add user** (top right) → **Create new user**.
3. **Email address:** `warroom@thill-ships.app`
4. **Password:** whatever you two will use. Six characters minimum.
5. Tick **Auto Confirm User**. This matters — without it the account cannot sign in.
6. Click **Create user**.

Then go to `https://thill-ships.github.io/big12/`, type that password, and hit **Open the
board**. You are in, and that browser stays signed in all season.

<details>
<summary>The other way, if you would rather not touch the dashboard</summary>

Go to `https://thill-ships.github.io/big12/`, type the password you want, and hit **Open the
board**. It will tell you the password did not work and offer a button reading **set this as
the password**. Click that and the account is created with whatever you typed.

This only works once, and only while nobody has claimed it — so do it immediately, not next
week.
</details>

**To change the password later:** [Auth → Users](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/users),
find the row, use the "..." menu on the right → **Reset password** or **Send magic link**.

## 4. Run the three jobs once

Open [the Actions tab](https://github.com/thill-ships/thill-ships.github.io/actions). Each of
these is in the left-hand list; click it, then **Run workflow** on the right, then **Run
workflow** again in the little panel that drops down.

| Run this | What to expect in the log |
|---|---|
| **Pick'em — sync games** | A line per week with a game count. This loads the season. It was probably already running for the pick'em; run it anyway so you know it is current. |
| **War Room — BYU player stats** — set **Dry run** to `1` | How many BYU games it read, who it thinks leads each category, and which prop it would set to what. **It writes nothing.** |
| **War Room — weekly snapshot** | "Snapshot saved…" or a line saying why it skipped. |

**Read the dry-run log properly.** It is the one chance to catch a misspelled player name
before anybody locks in. It will say things like:

```
  leader   rec_yds: Kyler Kasper (237)
  !! no player matching "LJ Martin" has appeared in a box score yet: LJ Martin rushing yards
```

The first is fine. The second means the name in the prop does not match how ESPN spells it —
fix it in the War Room under **Season props → Edit → Which player?**. (Early in the season
"has not appeared yet" may simply be true, if they have not played.)

When the log looks right, run **War Room — BYU player stats** again with **Dry run** left at
`0` so it actually writes.

After this, all three run on their own: the sync every two hours, the stats every six, the
snapshot every Monday at 6am Mountain.

## 5. Put up the questions

The season props — *how many yards will LJ Martin run for*, *how many games do they win* — are
a separate app at `props/`, and it is the one part of this system with **individual accounts**.
That is deliberate. The board is two people arguing at one screen, so a shared password is
right for it. The props are a group of people each committing to their own number, so they each
need their own login.

Nothing extra to set up: it uses the same Supabase project, and `schema.sql` already created its
tables. Two things to know:

- **Anyone can create an account** at `https://thill-ships.github.io/props/` with an email and
  a password. No confirmation email, same as the pick'em. Sign-up asks for the **name everyone
  else sees**, changeable any time from the button in the top right — and if somebody ends up
  with a name derived from their email, the app nags them to fix it before they lock in.
- **You write the questions, they answer them.** In the War Room, open **Season props**, and
  hit **Put up the thirteen** to post the agreed set:

  | # | Question | Answered by |
  |---|---|---|
  | 1 | How many regular-season games does BYU win? | **the schedule** |
  | 2 | How many Big 12 games does BYU win? | **the schedule** |
  | 3 | How many games does BYU win by 14 or more? | **the schedule** |
  | 4 | Does BYU make the Big 12 championship game? | you, in December |
  | 5 | Does BYU make the College Football Playoff? | you, in December |
  | 6 | Bear Bachmeier passing touchdowns | **box scores** |
  | 7 | Bear Bachmeier rushing touchdowns | **box scores** |
  | 8 | LJ Martin rushing yards | **box scores** |
  | 9 | LJ Martin's longest run of the season | **box scores** |
  | 10 | Who leads BYU in receiving yards? | **box scores** |
  | 11 | How many receiving yards does the leader finish with? | **box scores** |
  | 12 | Who leads BYU in interceptions? | **box scores** |
  | 13 | How many interceptions does the leader finish with? | **box scores** |

  Eleven of the thirteen keep themselves. Only the two December yes-or-nos are yours.

  **Read the wording once before you send anyone the link.** Editing a question after people
  have locked in does not change the answers they already gave, so the time to fix a name or
  tighten a definition is now. **Add a prop** and **Edit** are there for exactly that.

### Two screens, on purpose

**Before you lock in**, the app is a form and nothing else. No actuals, no standings, nobody
else's numbers, nothing to browse. One job: put a number on every question. Each box knows
what a sane answer looks like — nobody wins 14 Big 12 games, and letters don't go in a yards
box — and it says so rather than silently accepting nonsense. An answer that fails its check
is never saved, and the **Lock in** button stays dead until all thirteen pass.

**After you lock in**, it flips into a dashboard. Every question shows your number, where the
real one stands, and how the whole room split:

- **Yes/no and pick-a-player questions** get a bar per option with a headcount. Tap one to see
  exactly who.
- **Number questions** get a dot for every player on one line, yours darkest, with the real
  number marked. Underneath: lowest, average, highest, and where you sit. Tap *All 12 answers*
  for the list.

The scale on those dot strips is the spread of the *guesses*, not the actual — in September the
real number is nowhere near anybody's answer, and letting it set the scale would squash every
guess into one corner. When it falls outside, its marker pins to the edge with an arrow.

### How locking in works

Answer every question, then hit **Lock in**. That is irreversible, and it is what buys you the
sight of everyone else's numbers — you only ever see people who have also locked in. Nobody
can read the room while their own numbers are still soft.

The database enforces all of it, not the honour system: a policy refuses picks from anyone
already locked in, refuses a lock with any question blank, and returns other people's answers
only once both of you are locked.

**One exception, worth knowing.** The shared War Room login can read any answer that has been
locked in, because it is the scoreboard. So if you are playing too, lock your own numbers in
before you go looking at the window.

### Keeping score

**Eleven of the thirteen answer themselves.** Nobody types a yardage total.

- **Three come off the schedule** — wins, Big 12 wins, and wins by 14 or more — worked out in
  the browser from the games already syncing.
- **Eight come off BYU's box scores.** `War Room — BYU player stats` walks every finished BYU
  game, adds each player up, and writes the answer into the prop: Bachmeier's passing and
  rushing touchdowns, Martin's rushing yards and longest run, and both leader races with the
  numbers that go with them. It runs every six hours.

Only the two postseason yes-or-nos are left by hand, and those are one click each in December.

**Run it once by hand first, with *Dry run* set to `1`.** It writes nothing and prints exactly
what it found — how many games it read, who it thinks leads each category, and which prop it
would set to what. That is where you catch a misspelled player name.

Players are matched forgivingly: `LJ Martin` finds `L.J. Martin`, and suffixes like `III` are
ignored. If nobody matches, the log says so by name rather than silently writing a zero.

**Settling stops the clock.** The job never touches a settled prop, so **Settle** is how you
freeze a final number. Closest answer takes the prop; a tie splits it.

If ESPN ever gets one wrong, open the prop in **Edit**, set *Can the app score it?* back to
"we keep this one by hand", and the *Where it stands* box becomes typeable again.

## 6. Send everyone the link

`https://thill-ships.github.io/props/` — that is the only link the wider group needs. They
create an account, answer thirteen questions, lock in.

Tell them two things: **locking in is final**, and it is what lets them see everyone else's
numbers.

## 7. Choose your contenders

The board opens on **BYU, Arizona State, Texas Tech, Utah, Arizona and Houston**. Hit
**Contenders** to change it: add a team, drop one, or move a row up and down. Eight rows is
the cap. Everyone else in the league still plays in the simulation — this only decides whose
schedule you are predicting week to week, so dropping a team that has fallen out of the race
costs you nothing.

---

## Are you live?

Run through this once and you are done.

- [ ] `schema.sql` ran clean (step 1)
- [ ] **Confirm email** is off in Supabase (step 2)
- [ ] The War Room password gets you into `/big12/` (step 3)
- [ ] The board has games on it — if it says "No 2026 Big 12 schedule", the sync has not run
- [ ] The stats dry run named the right players, and you re-ran it for real (step 4)
- [ ] **Season props** shows thirteen questions
- [ ] `/props/` lets you create a test account and answer them
- [ ] You sent the props link round

## The BYU tab

Everything about our team on one screen: the record and where it is heading, the next game,
the whole schedule (clickable, same as the board), and the props at a glance.

The piece worth the price of admission is **What it takes** — finish the conference season on
each record, and here is how often that is actually enough for the championship game, counting
everything else that would plausibly be going on around them. It is the honest version of
"so what do we need to do?", and it is usually more forgiving than it feels in October.

## The Monday routine

1. Open the board. The weekend's results are already on it, in green and red, because the
   sync job pulled them overnight.
2. Read **This week** first: it lists the games with the most riding on them, biggest swing
   first, and tells you which side to root for.
3. Argue. Move games on the **Board** as you change your minds. Clicking walks a game down
   the scale and shift-clicking walks it back up:

   *the line stands → should win → lean win → coin flip → lean loss → should lose → back*

   Right-click for the same five in a list, with the percentage each one is worth and a box
   for a note. A game between two tracked teams moves on both rows at once — one side's
   *should win* is the other's *should lose*, so the board can never contradict itself.
4. Hit **Save this week** when you are done. That is the entry in the history.

Step 4 is optional insurance: a snapshot is taken automatically at 6am Monday whether or not
anybody opens the page, so a skipped week still gets recorded. Saving by hand just adds a
second, post-argument entry with your notes on it.

## How the numbers work

**Every undecided game has a win probability.** In order of preference:

1. **Your call**, on a five-point scale:

   | Call | The team wins |
   |---|---|
   | Should win | 80% |
   | Lean win | 65% |
   | Coin flip | 50% |
   | Lean loss | 35% |
   | Should lose | 20% |

   Only two of those are settings — *should win* and *lean*. A coin flip is always 50%, and
   the bottom two are the mirror images of the top two, which is what keeps a shared game
   consistent from both sides. Change either dial at Standings → *change*; 80% is about a
   12-point favourite and 65% about a 6-point one.
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
| `b12_settings` | Your contenders, in board order, and what *should win* and *lean* are worth. One row per season. |
| `b12_predictions` | One row per game you have an opinion about, stored **per game** as a direction plus a strength — so BYU–Utah can never be "BYU should win" on one row and "Utah should win" on the other. |
| `b12_snapshots` | One row per saved week. Self-contained: the predictions *and* the results as they stood, so a week can be re-scored later exactly as you saw it. |
| `b12_props` | The season-prop questions. Written in the War Room, answered in the props app. |
| `b12_prop_players` / `b12_prop_picks` / `b12_prop_locks` | Who is playing, their answers, and who has locked in. These belong to the props app; the War Room only reads them. |

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
| A call won't save, "violates check constraint" | `schema.sql` is the three-level version. Re-run the current file; it widens the allowed strengths. |
| No automatic snapshots | Actions → *War Room — weekly snapshot* → check the log; it prints why it skipped. |
| A player prop stays blank | Actions → *War Room — BYU player stats*. The log names any player it could not find — usually a spelling difference. Fix it in **Edit → Which player?**. |
| A leader prop names somebody who isn't an option | The log flags this loudly. The question is broken as written and nobody can win it: add the option, or settle it as a void. |
| Props tab shows a headcount but no numbers | Those people have not locked in yet. Nothing shows until they do. |
| Somebody says their answer won't save | It is failing its bounds check — the app shows why under the box. Widen the range in **Edit** if the bound is wrong. |
| "Lock in" stays greyed out | A question is still blank. The database refuses a lock with blanks, so the button does too. |
