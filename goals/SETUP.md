# Daily Goals — setup

About five minutes. It uses the same Supabase project as the pick'em and the war room, so there
are no new accounts to open and nothing costs money.

| Piece | Where | What it does |
|---|---|---|
| `goals/index.html` | `https://thill-ships.github.io/goals/` | The phone app: check goals off (today or any earlier day), see the stock |
| `daily/index.html` | `https://thill-ships.github.io/daily/?k=…` | The kitchen wall board (see `daily/SETUP.md`) |
| `goals/core.js` | both | The five goals and the stock math, shared so the two screens always agree |
| `goals/schema.sql` | Supabase | The tables, and the functions the wall and the feeds use |

## 1. Run the schema

1. Open the [SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new).
2. Paste in all of `goals/schema.sql` and press **Run**.

Supabase may warn about destructive operations. That's a keyword match on `drop policy`: the file
only drops policies to recreate them, never a table or a row. You should see **Success. No rows
returned.** It's safe to run again after an update.

## 2. Create the login

1. Open [Auth → Users](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/users).
2. **Add user → Create new user**.
3. Email: `tyler@thill-ships.app` (not a real mailbox; it never gets mail).
4. Password: your choice, six characters or more.
5. Tick **Auto Confirm User**, then **Create user**.

## 3. Open it on your phone

Go to `https://thill-ships.github.io/goals/`, type the password, and you're in. In Safari use
**Share → Add to Home Screen** so it opens like an app.

To check something off for an earlier day, use the arrows next to the day's name, or tap the day
in **The last four weeks**.

## The goals and the stock

| Goal | How often |
|---|---|
| Gym | 4 times a week |
| Prayer + scriptures | Every day |
| Brush + floss | Every day |
| Clean the apartment | Once a week |
| Third stream | Every day |

Weeks run Monday to Sunday. The stock went public at 100.00:

- Each daily goal done is **+0.25%**, each one missed **−0.30%**, charged at midnight.
- All three daily goals in one day adds another **+0.25%**.
- Each gym or cleaning session is **+0.25%** on the day, up to the week's target. Each session
  short of the target is **−0.30%** when the week closes Sunday at midnight. Days off are never
  charged on their own.
- Today only counts what's done so far. The phone and the wall both show what today would add if it
  ended now.
- The first week after the IPO is prorated, so starting midweek doesn't cost you the days before.
- Checking something off late still counts in full: the price is worked out from the whole
  history every time.

To change the names, how often, or the numbers, edit the top of `goals/core.js`. Goals are stored
by their `key`, so rename freely but never change a key.
