# Big 12 War Room — setup

About ten minutes, and most of the work is already done: this app rides on the same
Supabase project and the same schedule sync the [pick'em](../pickem/SETUP.md) app uses. It
adds three tables and one weekly job. Nothing here costs money.

| Piece | Where it runs | What it does |
|---|---|---|
| `big12/index.html` | GitHub Pages | The board the two of you use |
| `props/index.html` | GitHub Pages | Season props — the one piece with real accounts |
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

## 5. Set up the season props

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

  | # | Question | Type |
  |---|---|---|
  | 1 | Who leads BYU in receiving yards? | Kasper · Phillips · Bachmeier · Glasker |
  | 2 | How many receiving yards does the leader finish with? | number |
  | 3 | Who leads BYU in interceptions? | Uluave · Glasker · Satuala · Johnson · Alexander · DeVries |
  | 4 | How many interceptions does the leader finish with? | number |
  | 5 | How many regular-season games does BYU win? | **scored automatically** |
  | 6 | How many Big 12 games does BYU win? | **scored automatically** |
  | 7 | How many games does BYU win by 14 or more? | **scored automatically** |
  | 8 | Bear Bachmeier rushing touchdowns | number |
  | 9 | Bear Bachmeier passing touchdowns | number |
  | 10 | LJ Martin rushing yards | number |
  | 11 | LJ Martin's longest run of the season | number |
  | 12 | Does BYU make the Big 12 championship game? | Yes / No |
  | 13 | Does BYU make the College Football Playoff? | Yes / No |

  Each number question also carries a **lowest** and **highest allowed**, set in the same
  editor. That is what stops a fat finger putting 140 in the Big 12 wins box.

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

Five questions the app answers for itself off the schedule — wins, losses, Big 12 wins, Big 12
losses, and wins by 14 or more. For the rest, type the running number into the *Where it stands* column in the War Room
whenever you feel like it, and hit **Settle** when a number is final. Closest answer takes the
prop; a tie splits it.

## 6. Choose your contenders

The board opens on **BYU, Arizona State, Texas Tech, Utah, Arizona and Houston**. Hit
**Contenders** to change it: add a team, drop one, or move a row up and down. Eight rows is
the cap. Everyone else in the league still plays in the simulation — this only decides whose
schedule you are predicting week to week, so dropping a team that has fallen out of the race
costs you nothing.

---

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
| Props tab shows a headcount but no numbers | Those people have not locked in yet. Nothing shows until they do. |
| Somebody says their answer won't save | It is failing its bounds check — the app shows why under the box. Widen the range in **Edit** if the bound is wrong. |
| "Lock in" stays greyed out | A question is still blank. The database refuses a lock with blanks, so the button does too. |
