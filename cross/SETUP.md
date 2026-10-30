# Take Up My Cross — setup

About five minutes. It uses the same Supabase project as the pick'em and the war room, so there
are no new accounts to open and nothing costs money.

| Piece | Where | What it does |
|---|---|---|
| `cross/index.html` | `https://thill-ships.github.io/cross/` | The phone app: check things off, see the stock |
| `daily/index.html` | `https://thill-ships.github.io/daily/?k=…` | The daily board for the kitchen calendar |
| `cross/core.js` | both | The five habits and the stock math, shared so the two screens always agree |
| `cross/schema.sql` | Supabase | The tables and the two functions the wall uses |

## 1. Run the schema

1. Open the [SQL editor](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/sql/new).
2. Paste in all of `cross/schema.sql` and press **Run**.

Supabase may warn about destructive operations. That is a keyword match on `drop policy`; the
file only drops policies to recreate them, never a table or a row. You should see **Success.
No rows returned.**

## 2. Create the login

1. Open [Auth → Users](https://supabase.com/dashboard/project/yehpygarkxdopdvugifk/auth/users).
2. **Add user → Create new user**.
3. Email: `cross@thill-ships.app` (not a real mailbox; it never gets mail).
4. Password: your choice, six characters or more.
5. Tick **Auto Confirm User**, then **Create user**.

## 3. Open it on your phone

Go to `https://thill-ships.github.io/cross/`, type the password, and you are in. In Safari use
**Share → Add to Home Screen** so it opens like an app.

## 4. Put it on the kitchen wall

1. In the phone app, open **Settings & how the stock works** at the bottom and copy the
   **Kitchen wall link**.
2. Open that link on the calendar (the same way you point the wall app at any page, e.g.
   `adb shell am start -n io.github.thillships.wall/.MainActivity -d "<link>"`).

The wall remembers its key, so after the first time plain `/daily/` works too. If the link
ever leaks, **Make a new link** on the phone; the old one stops working at once.

Habits can be checked off on the wall by tapping them. Changes on either screen show up on the
other within a minute.

## How the stock works

Every day closes at midnight. Each habit done is **+0.25%**, each missed is **−0.30%**, and all
five adds **+0.25%** more. So 5/5 = +1.50%, 4 = +0.70%, 3 = +0.15%, 2 = −0.40%, 1 = −0.95%,
0 = −1.50%. A day with nothing logged counts as 0/5. Today only counts what is done so far;
the misses are charged at the close. It starts at 100.00 on the IPO day (the first day you log,
unless you set one in Settings).

To change the numbers, the names or the meanings, edit the top of `cross/core.js`. Habits are
stored by their `key`, so rename freely but never change a key.
